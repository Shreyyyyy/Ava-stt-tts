"""
Deepgram integration for Ava.

- Text-to-Speech (TTS): Deepgram Aura-2  → returns raw audio bytes
- Speech-to-Text config constants used by the frontend WebSocket proxy
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEEPGRAM_API_KEY = "8e35f5c21d1ba75039349cbf0afa13e4b50637ee"

# ─────────────────────────────────────────────────────────────────────────────
# TTS  (server-side, returns bytes)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_TTS_MODEL    = "aura-2-thalia-en"
DEFAULT_TTS_ENCODING = "linear16"   # raw PCM – browser plays fine via Audio()
DEFAULT_TTS_FORMAT   = "mp3"        # we'll use mp3 for broad browser support


def tts_speak(
    text: str,
    model: str = DEFAULT_TTS_MODEL,
    save_path: Optional[Path] = None,
) -> bytes:
    """
    Convert text → audio bytes using Deepgram Aura-2 REST API.

    Args:
        text:      The text to synthesise.
        model:     Deepgram TTS voice model name.
        save_path: If set, also write the audio to this path.

    Returns:
        Raw MP3 bytes ready to stream to the browser.
    """
    import httpx

    url = "https://api.deepgram.com/v1/speak"
    params = {"model": model}
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"text": text}

    try:
        response = httpx.post(
            url,
            params=params,
            headers=headers,
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        audio_bytes = response.content

        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(audio_bytes)
            logger.info(f"TTS audio saved → {save_path}")

        return audio_bytes

    except httpx.HTTPStatusError as e:
        logger.error(f"Deepgram TTS error {e.response.status_code}: {e.response.text}")
        raise RuntimeError(f"Deepgram TTS failed: {e.response.status_code}") from e
    except httpx.ConnectError as e:
        logger.error(f"Cannot reach Deepgram API: {e}")
        raise RuntimeError("Cannot connect to Deepgram — check internet/firewall") from e


# ─────────────────────────────────────────────────────────────────────────────
# STT WebSocket proxy helpers
# ─────────────────────────────────────────────────────────────────────────────

# These are the Deepgram LiveTranscription query params the frontend WS proxy
# will add when it opens a Deepgram socket on behalf of the browser.
DEEPGRAM_STT_DEFAULTS = {
    "model":           "nova-3",
    "language":        "en-IN",          # Indian English; change to "en-US" etc.
    "punctuate":       "true",
    "smart_format":    "true",
    "interim_results": "true",
    "encoding":        "linear16",
    "channels":        "1",
    "sample_rate":     "16000",
}

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"

# ─────────────────────────────────────────────────────────────────────────────
# Voice Agent  (wss://agent.deepgram.com/agent)
# ─────────────────────────────────────────────────────────────────────────────

DEEPGRAM_AGENT_URL = "wss://agent.deepgram.com/v1/agent/converse"

# ── API keys for LLM providers ────────────────────────────────────────────────
GEMINI_API_KEY   = "AIzaSyC1gmFTe7qo-Tfu5i9SGfOneAafGCefJZ4"
DEEPSEEK_API_KEY = "sk-b23d8a17a60a43eabdd5683a0090029d"

_AGENT_PROMPT = (
    "You are Ava, a warm and intelligent personal AI voice assistant. "
    "Have natural, helpful conversations with the user.\n\n"
    "Guidelines:\n"
    "- Be warm, friendly, and concise.\n"
    "- Keep responses under 2 sentences unless asked for detail.\n"
    "- Speak naturally — your responses will be spoken aloud.\n"
    "- No markdown, bullet points, or code blocks.\n"
    "- Ask one short clarifying question if unclear.\n\n"
    "Always ask if there is anything else you can help with before ending."
)

# ── Primary: Google Gemini 2.5 Flash (BYO key via endpoint header) ────────────
# Deepgram spec requires the Gemini API key to be passed as an endpoint header
# (x-goog-api-key), NOT as a "key" field inside provider — that field is invalid
# and causes UNPARSABLE_CLIENT_MESSAGE. The "temperature" field is also required
# for all 3rd-party providers (google, groq).
AGENT_SETTINGS = {
    "type": "Settings",
    "audio": {
        "input":  {"encoding": "linear16", "sample_rate": 48000},
        "output": {"encoding": "linear16", "sample_rate": 24000, "container": "none"},
    },
    "agent": {
        "language": "en",
        "speak": {
            "provider": {"type": "deepgram", "model": "aura-2-thalia-en"}
        },
        "listen": {
            "provider": {"type": "deepgram", "version": "v2", "model": "flux-general-en"}
        },
        "think": {
            "provider": {
                "type": "google",
                "temperature": 0.7,         # Required for 3rd-party providers
            },
            "endpoint": {
                "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse",
                "headers": {
                    "x-goog-api-key": GEMINI_API_KEY,
                },
            },
            "prompt": _AGENT_PROMPT,
        },
        "greeting": "Hello! I'm Ava, your personal AI assistant. How can I help you today?",
    },
}

# ── Backup: DeepSeek via OpenAI-compatible endpoint ───────────────────────────
# Uses agent.think.endpoint with Authorization header (BYO LLM pattern)
AGENT_SETTINGS_DEEPSEEK = {
    "type": "Settings",
    "audio": {
        "input":  {"encoding": "linear16", "sample_rate": 48000},
        "output": {"encoding": "linear16", "sample_rate": 24000, "container": "none"},
    },
    "agent": {
        "language": "en",
        "speak": {
            "provider": {"type": "deepgram", "model": "aura-2-odysseus-en"}
        },
        "listen": {
            "provider": {"type": "deepgram", "version": "v2", "model": "flux-general-en"}
        },
        "think": {
            "provider": {
                "type": "open_ai",
                "model": "deepseek-chat",
                "temperature": 0.7,
            },
            "endpoint": {
                "url": "https://api.deepseek.com/v1/chat/completions",
                "headers": {
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                },
            },
            "prompt": _AGENT_PROMPT,
        },
        "greeting": "Hello! I'm Ava, your personal AI assistant. How can I help you today?",
    },
}
