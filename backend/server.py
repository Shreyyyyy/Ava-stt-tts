"""
FastAPI backend for AVA – Digital AI Avatar.

Endpoints:
  POST /chat                 – send a message, get a response
  POST /feedback             – submit feedback on a conversation turn
  GET  /memory               – retrieve recent conversations
  GET  /memory/search        – semantic search over memory
  GET  /memory/profile       – personality profile
  POST /training/trigger     – kick off LoRA fine-tuning
  GET  /training/history     – list past training runs
  GET  /health               – system health check
  GET  /models               – list available Ollama models
  POST /tts                  – Deepgram Aura-2 text-to-speech (returns MP3)
  GET  /stt/token            – return Deepgram API key for browser WS auth
  WS   /stt/proxy            – WebSocket: browser PCM → Deepgram → transcripts
"""

import uuid
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
import websockets

from memory.database import (
    init_db,
    save_conversation,
    update_feedback,
    get_recent_conversations,
    get_style_profile,
    get_training_history,
)
from memory.vector_store import get_vector_store
from memory.style_analyzer import update_profile_from_message, get_personality_profile
from backend.llm_client import chat, is_ollama_running, list_local_models
from backend.deepgram_client import (
    tts_speak,
    DEEPGRAM_API_KEY,
    DEEPGRAM_WS_URL,
    DEEPGRAM_STT_DEFAULTS,
    DEEPGRAM_AGENT_URL,
    AGENT_SETTINGS,
)

# ── optional training import (graceful if heavy deps missing) ────────────────
try:
    from training.train_adapter import run_training_pipeline
    TRAINING_AVAILABLE = True
except ImportError:
    TRAINING_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# App bootstrap
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AVA – Digital AI Avatar",
    description="Self-improving conversational AI that learns your communication style.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("AVA backend started ✓")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message:    str          = Field(..., min_length=1, max_length=4096)
    session_id: str          = Field(default_factory=lambda: str(uuid.uuid4()))
    model:      str          = Field(default="llama3.2")
    history:    List[dict]   = Field(default=[])
    temperature: float       = Field(default=0.7, ge=0.0, le=2.0)
    use_memory:  bool        = Field(default=True)
    use_style:   bool        = Field(default=True)


class ChatResponse(BaseModel):
    conversation_id: int
    session_id:      str
    response:        str
    style_metrics:   dict
    memory_hits:     int
    timestamp:       str


class FeedbackRequest(BaseModel):
    conversation_id: int
    feedback_label:  str   # "sounds_like_me" | "too_verbose" | "too_soft"
                           # | "wrong_reasoning" | "rewrite"
    user_correction: Optional[str] = None


class FeedbackResponse(BaseModel):
    status:  str
    message: str

FEEDBACK_SCORES = {
    "sounds_like_me":  1.0,
    "too_verbose":     0.3,
    "too_soft":        0.4,
    "wrong_reasoning": 0.1,
    "rewrite":         0.2,
}


class TrainingRequest(BaseModel):
    model:       str   = Field(default="llama3.2")
    min_score:   float = Field(default=0.7, ge=0.0, le=1.0)
    max_examples: int  = Field(default=500, ge=10, le=5000)
    notes:       str   = Field(default="")


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status":             "ok",
        "ollama_running":     is_ollama_running(),
        "training_enabled":   TRAINING_AVAILABLE,
        "deepgram_key_set":   bool(DEEPGRAM_API_KEY),
        "timestamp":          datetime.utcnow().isoformat(),
    }


@app.get("/models")
async def models():
    return {"models": list_local_models()}


# ── Deepgram TTS ──────────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text:  str = Field(..., min_length=1, max_length=4096)
    model: str = Field(default="aura-2-thalia-en")


@app.post("/tts")
async def tts_endpoint(req: TTSRequest):
    """
    Convert text to speech via Deepgram Aura-2.
    Returns raw MP3 audio so the browser can play it with the Audio() API.
    """
    try:
        audio_bytes = tts_speak(text=req.text, model=req.model)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-cache"},
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Deepgram STT – safe key delivery ─────────────────────────────────────────

@app.get("/stt/token")
async def stt_token():
    """
    Return the Deepgram API key + WS connection params for the browser.
    The key never appears in frontend source code — fetched at runtime.
    """
    return {
        "api_key": DEEPGRAM_API_KEY,
        "ws_url":  DEEPGRAM_WS_URL,
        "params":  DEEPGRAM_STT_DEFAULTS,
    }


# ── Deepgram STT – WebSocket proxy ───────────────────────────────────────────

@app.websocket("/stt/proxy")
async def stt_proxy(ws: WebSocket):
    """
    Bidirectional proxy: browser <──PCM──> this server <──PCM──> Deepgram

    Browser sends raw PCM audio chunks as binary frames.
    This server forwards them to Deepgram and sends Deepgram's JSON
    transcript events back to the browser.
    """
    await ws.accept()

    # Build Deepgram WS URL with query params
    params = "&".join(f"{k}={v}" for k, v in DEEPGRAM_STT_DEFAULTS.items())
    dg_url = f"{DEEPGRAM_WS_URL}?{params}"
    dg_headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}

    try:
        async with websockets.connect(dg_url, additional_headers=dg_headers) as dg_ws:

            async def forward_to_deepgram():
                """Browser → Deepgram: raw PCM audio chunks."""
                try:
                    while True:
                        data = await ws.receive_bytes()
                        await dg_ws.send(data)
                except (WebSocketDisconnect, Exception):
                    await dg_ws.close()

            async def forward_to_browser():
                """Deepgram → Browser: JSON transcript events."""
                try:
                    async for message in dg_ws:
                        await ws.send_text(message)
                except Exception:
                    pass

            await asyncio.gather(
                forward_to_deepgram(),
                forward_to_browser(),
            )

    except WebSocketDisconnect:
        logger.info("STT proxy: browser disconnected")
    except Exception as e:
        logger.error(f"STT proxy error: {e}")
        try:
            await ws.close(code=1011, reason=str(e))
        except Exception:
            pass


# ── Chat ─────────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    # 1. Style profile
    style_profile = get_personality_profile() if req.use_style else None

    # 2. Semantic memory retrieval
    vector_store = get_vector_store()
    memory_hits  = 0
    memory_context = ""
    if req.use_memory and vector_store.count() > 0:
        results = vector_store.search(req.message, k=3)
        if results:
            snippets = [m.get("text_snippet", "") for _, m in results if _ < 1.5]
            if snippets:
                memory_context = (
                    "\n\n[Memory context – past conversations you may reference]\n"
                    + "\n---\n".join(snippets)
                )
                memory_hits = len(snippets)

    # 3. Build message list
    messages = list(req.history)
    if memory_context:
        # Append memory as a system note at the end of history
        messages.append({"role": "system", "content": memory_context})
    messages.append({"role": "user", "content": req.message})

    # 4. LLM call
    try:
        reply = chat(
            messages=messages,
            model=req.model,
            style_profile=style_profile,
            temperature=req.temperature,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # 5. Persist conversation
    style_metrics = update_profile_from_message(req.message)
    conv_id = save_conversation(
        session_id=req.session_id,
        user_message=req.message,
        model_response=reply,
        style_tags=list(style_metrics.keys()),
    )

    # 6. Add to vector store
    vector_store.add(
        conversation_id=conv_id,
        text=f"User: {req.message}\nAva: {reply}",
    )

    return ChatResponse(
        conversation_id=conv_id,
        session_id=req.session_id,
        response=reply,
        style_metrics=style_metrics,
        memory_hits=memory_hits,
        timestamp=datetime.utcnow().isoformat(),
    )


# ── Feedback ─────────────────────────────────────────────────────────────────

@app.post("/feedback", response_model=FeedbackResponse)
async def feedback_endpoint(req: FeedbackRequest):
    score = FEEDBACK_SCORES.get(req.feedback_label, 0.5)
    update_feedback(
        conversation_id=req.conversation_id,
        feedback_label=req.feedback_label,
        feedback_score=score,
        user_correction=req.user_correction,
    )
    return FeedbackResponse(
        status="ok",
        message=f"Feedback '{req.feedback_label}' recorded (score={score}).",
    )


# ── Memory ───────────────────────────────────────────────────────────────────

@app.get("/memory")
async def memory_endpoint(limit: int = 20, session_id: Optional[str] = None):
    convs = get_recent_conversations(limit=limit, session_id=session_id)
    return {"conversations": convs, "count": len(convs)}


@app.get("/memory/search")
async def memory_search(q: str, k: int = 5):
    vector_store = get_vector_store()
    results = vector_store.search(q, k=k)
    return {
        "query":   q,
        "results": [{"distance": d, "metadata": m} for d, m in results],
    }


@app.get("/memory/profile")
async def memory_profile():
    return get_personality_profile()


# ── Training ─────────────────────────────────────────────────────────────────

@app.post("/training/trigger")
async def training_trigger(req: TrainingRequest, bg: BackgroundTasks):
    if not TRAINING_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Training dependencies not installed. Run: pip install -r requirements-training.txt",
        )
    bg.add_task(
        run_training_pipeline,
        base_model=req.model,
        min_score=req.min_score,
        max_examples=req.max_examples,
        notes=req.notes,
    )
    return {"status": "queued", "message": "Fine-tuning started in the background."}


@app.get("/training/history")
async def training_history():
    return {"runs": get_training_history()}


# ── Deepgram Voice Agent proxy ────────────────────────────────────────────────────

@app.websocket("/agent/proxy")
async def agent_proxy(ws: WebSocket):
    """
    Bidirectional proxy between the browser and Deepgram Voice Agent API.

    Protocol:
      1. Backend connects to Deepgram with the API key in headers.
      2. Backend sends the Settings JSON as the very first message.
      3. Browser sends raw Int16 PCM @ 48 kHz as binary frames.
      4. Deepgram sends back:
           - Binary frames  → raw Int16 PCM @24 kHz (agent speech)
           - Text frames    → JSON events (SettingsApplied, UserStartedSpeaking, …)
    """
    await ws.accept()
    logger.info("Voice Agent proxy: browser connected")

    try:
        async with websockets.connect(
            DEEPGRAM_AGENT_URL,
            additional_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"},
        ) as dg_ws:
            # ① Handshake — Settings must be the first message
            await dg_ws.send(json.dumps(AGENT_SETTINGS))
            logger.info("Voice Agent proxy: Settings sent to Deepgram")

            async def browser_to_dg():
                """Forward browser audio (binary) and control messages (text) to Deepgram."""
                try:
                    while True:
                        data = await ws.receive()
                        if data.get("bytes"):
                            await dg_ws.send(data["bytes"])
                        elif data.get("text"):
                            await dg_ws.send(data["text"])
                except (WebSocketDisconnect, Exception) as e:
                    logger.info(f"Voice Agent proxy: browser disconnected ({e})")
                    try:
                        await dg_ws.close()
                    except Exception:
                        pass

            async def dg_to_browser():
                """Forward Deepgram audio + events back to the browser."""
                try:
                    async for msg in dg_ws:
                        if isinstance(msg, bytes):
                            await ws.send_bytes(msg)
                        else:
                            # Log every text frame so we can see Deepgram events
                            try:
                                evt = json.loads(msg)
                                evt_type = evt.get("type", "unknown")
                                if evt_type == "Error":
                                    logger.error(
                                        f"Deepgram Error event: {json.dumps(evt)}"
                                    )
                                else:
                                    logger.info(
                                        f"Deepgram → browser [{evt_type}]: {msg[:200]}"
                                    )
                            except Exception:
                                logger.info(f"Deepgram → browser (raw): {msg[:200]}")
                            await ws.send_text(msg)
                except websockets.exceptions.ConnectionClosedError as e:
                    logger.error(
                        f"Voice Agent proxy: Deepgram closed with code={e.code} reason={e.reason!r}"
                    )
                except websockets.exceptions.ConnectionClosedOK as e:
                    logger.info(
                        f"Voice Agent proxy: Deepgram closed cleanly code={e.code} reason={e.reason!r}"
                    )
                except Exception as e:
                    logger.error(f"Voice Agent proxy: Deepgram recv error: {e}")

            await asyncio.gather(browser_to_dg(), dg_to_browser())

    except WebSocketDisconnect:
        logger.info("Voice Agent proxy: browser disconnected before Deepgram connect")
    except Exception as e:
        logger.error(f"Voice Agent proxy error: {e}")
        try:
            await ws.close(code=1011, reason=str(e))
        except Exception:
            pass
