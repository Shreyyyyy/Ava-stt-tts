"""
Ollama client – wraps the local Ollama HTTP API.
Supports standard chat completions with optional system prompt injection
derived from the user's evolving style profile.
"""

import json
import logging
import httpx
from typing import Optional, Iterator

logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2.2"          # swap to 'mistral' or any pulled model


def _style_system_prompt(profile: dict) -> str:
    """Synthesise a system prompt from the personality profile."""
    style = profile.get("style_metrics", {})
    interp = profile.get("interpretations", {})

    directness   = interp.get("communication_style", "Balanced")
    register     = interp.get("register", "Semi-formal")
    emotion      = interp.get("emotional_tone", "Moderately expressive")
    avg_len      = style.get("avg_sentence_length_normalised", 0.5)
    sentence_hint = (
        "Keep responses concise – short sentences preferred."
        if avg_len < 0.4 else
        "You may use medium-length, well-structured sentences."
        if avg_len < 0.7 else
        "Detailed, long-form responses are acceptable."
    )

    return (
        f"You are Ava, the user's Personal AI Avatar. "
        f"Mirror their communication style precisely.\n\n"
        f"Style profile:\n"
        f"- Communication style: {directness}\n"
        f"- Register: {register}\n"
        f"- Emotional tone: {emotion}\n"
        f"- {sentence_hint}\n\n"
        f"Always respond as if you are thinking the way the user thinks. "
        f"Adapt your vocabulary, depth, and tone to match their patterns."
    )


def chat(
    messages: list,
    model: str = DEFAULT_MODEL,
    style_profile: Optional[dict] = None,
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """
    Send a chat completion to the local Ollama instance.

    Args:
        messages:       List of {"role": ..., "content": ...} dicts.
        model:          Ollama model name.
        style_profile:  If provided, injects a style-aware system prompt.
        stream:         If True, yields tokens (not yet wired into REST layer).
        temperature:    Sampling temperature.
        max_tokens:     Maximum generation tokens.

    Returns:
        The assistant's reply as a string.
    """
    # Inject style system prompt as first system message if not already present
    if style_profile:
        system_prompt = _style_system_prompt(style_profile)
        if not messages or messages[0].get("role") != "system":
            messages = [{"role": "system", "content": system_prompt}] + messages
        else:
            messages[0]["content"] = system_prompt + "\n\n" + messages[0]["content"]

    payload = {
        "model":  model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature":   temperature,
            "num_predict":   max_tokens,
        },
    }

    try:
        response = httpx.post(
            f"{OLLAMA_BASE}/api/chat",
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]
    except httpx.ConnectError:
        logger.error("Cannot connect to Ollama. Is it running? Run: ollama serve")
        raise RuntimeError(
            "Ollama is not running. Start it with: ollama serve"
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Ollama HTTP error: {e.response.status_code} – {e.response.text}")
        raise


def list_local_models() -> list:
    """Return list of models pulled into Ollama."""
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=10.0)
        r.raise_for_status()
        return r.json().get("models", [])
    except Exception as e:
        logger.warning(f"Could not list Ollama models: {e}")
        return []


def is_ollama_running() -> bool:
    try:
        r = httpx.get(f"{OLLAMA_BASE}/", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False
