"""
FastAPI backend for AVA – Sarvam AI Voice Services.

Endpoints:
  POST /sarvam/tts           – Sarvam AI text-to-speech (Indian languages)
  GET  /sarvam/tts/languages – Get supported TTS languages
  GET  /sarvam/tts/speakers  – Get available TTS speakers
  POST /sarvam/stt           – Sarvam AI speech-to-text (Indian languages)
  GET  /sarvam/stt/languages – Get supported STT languages
  GET  /sarvam/stt/models    – Get available STT models
  GET  /health               – System health check
"""

import uuid
import logging
import os
import tempfile
import time
from typing import Optional, List

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import aiofiles

from backend.sarvam_tts_client import SarvamTTSClient
from backend.sarvam_stt_client import SarvamSTTClient
from backend.ollama_client import OllamaClient
import logger_config

# Setup logging
logger = logger_config.setup_logging(
    log_level=logging.INFO,
    log_file="logs/backend.log"
)

# ─────────────────────────────────────────────────────────────────────────────
# App bootstrap
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AVA – Sarvam AI Voice Services",
    description="Indian language text-to-speech and speech-to-text using Sarvam AI.",
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
    logger.info("=== AVA Sarvam Backend Starting ===")
    
    # Initialize Sarvam AI clients
    try:
        logger.info("Initializing Sarvam AI clients...")
        app.state.sarvam_tts = SarvamTTSClient()
        app.state.sarvam_stt = SarvamSTTClient()
        logger.info("✓ Sarvam AI clients initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize Sarvam AI clients: {e}")
        app.state.sarvam_tts = None
        app.state.sarvam_stt = None
    
    # Initialize Ollama client
    try:
        logger.info("Initializing Ollama client...")
        app.state.ollama = OllamaClient()
        if app.state.ollama.is_available():
            logger.info("✓ Ollama client initialized successfully")
        else:
            logger.warning("⚠ Ollama not available. Voice assistant responses will be limited.")
            app.state.ollama = None
    except Exception as e:
        logger.warning(f"⚠ Failed to initialize Ollama client: {e}")
        app.state.ollama = None
    
    logger.info("✓ AVA Sarvam backend started successfully")
    logger.info("Available endpoints:")
    logger.info("  - POST /sarvam/tts")
    logger.info("  - GET  /sarvam/tts/languages")
    logger.info("  - GET  /sarvam/tts/speakers")
    logger.info("  - POST /sarvam/stt")
    logger.info("  - GET  /sarvam/stt/languages")
    logger.info("  - GET  /sarvam/stt/models")
    logger.info("  - POST /sarvam/stt/upload")
    logger.info("  - POST /ava/chat")
    logger.info("  - GET  /health")
    logger.info("=== Backend Startup Complete ===")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────────────────

class SarvamTTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096)
    target_language_code: str = Field(default="hi-IN")
    speaker: str = Field(default="shreya")
    model: str = Field(default="bulbul:v3")
    pace: float = Field(default=1.1, ge=0.5, le=2.0)
    speech_sample_rate: int = Field(default=22050)
    output_audio_codec: str = Field(default="mp3")
    enable_preprocessing: bool = Field(default=True)


class SarvamSTTRequest(BaseModel):
    audio_paths: List[str] = Field(..., min_items=1)
    model: str = Field(default="saaras:v3")
    mode: str = Field(default="async")
    language_code: str = Field(default="hi-IN")
    with_diarization: bool = Field(default=False)
    num_speakers: Optional[int] = Field(None)
    output_dir: str = Field(default="./output")


class AVAChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    language_code: str = Field(default="hi-IN")
    speaker: str = Field(default="shreya")
    model: str = Field(default="bulbul:v3")
    pace: float = Field(default=1.0, ge=0.5, le=2.0)


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    logger.info("Health check requested")
    health_status = {
        "status": "ok",
        "sarvam_tts_available": app.state.sarvam_tts is not None,
        "sarvam_stt_available": app.state.sarvam_stt is not None,
        "ollama_available": app.state.ollama is not None,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    logger.info(f"Health status: {health_status}")
    return health_status


# ── Sarvam AI Text-to-Speech ─────────────────────────────────────────────────────

@app.post("/sarvam/tts")
async def sarvam_tts(req: SarvamTTSRequest):
    """Convert text to speech using Sarvam AI"""
    logger.info(f"TTS request received: text='{req.text[:50]}...', language='{req.target_language_code}', speaker='{req.speaker}'")
    
    if not app.state.sarvam_tts:
        logger.error("TTS client not initialized")
        raise HTTPException(
            status_code=503,
            detail="Sarvam TTS client not initialized. Check SARVAM_API_KEY environment variable."
        )
    
    try:
        # Generate unique filename
        temp_dir = tempfile.gettempdir()
        output_file = os.path.join(temp_dir, f"tts_{uuid.uuid4().hex[:8]}.mp3")
        logger.info(f"Generating TTS audio: {output_file}")
        
        # Generate speech
        start_time = time.time()
        result_file = app.state.sarvam_tts.stream_tts(
            text=req.text,
            target_language_code=req.target_language_code,
            speaker=req.speaker,
            model=req.model,
            pace=req.pace,
            speech_sample_rate=req.speech_sample_rate,
            output_audio_codec=req.output_audio_codec,
            enable_preprocessing=req.enable_preprocessing,
            output_file=output_file
        )
        generation_time = time.time() - start_time
        
        # Check file size
        file_size = os.path.getsize(result_file) if os.path.exists(result_file) else 0
        logger.info(f"TTS generated successfully: {file_size} bytes in {generation_time:.2f}s")
        
        # Return audio file
        def iterfile():
            with open(result_file, mode="rb") as file_like:
                while True:
                    chunk = file_like.read(8192)
                    if not chunk:
                        break
                    yield chunk
        
        # Schedule cleanup after streaming
        import asyncio
        async def cleanup():
            await asyncio.sleep(1)  # Give time for streaming to complete
            try:
                os.remove(result_file)
                logger.info(f"Cleaned up temporary file: {output_file}")
            except:
                pass
        
        asyncio.create_task(cleanup())
        
        logger.info("Streaming TTS audio response")
        return StreamingResponse(
            iterfile(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename=tts_output.mp3",
                "X-Audio-Codec": req.output_audio_codec,
                "X-Language": req.target_language_code,
                "X-Speaker": req.speaker,
                "X-Generation-Time": f"{generation_time:.2f}s"
            }
        )
        
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sarvam/tts/languages")
async def sarvam_tts_languages():
    """Get supported languages for TTS"""
    if not app.state.sarvam_tts:
        raise HTTPException(
            status_code=503,
            detail="Sarvam TTS client not initialized"
        )
    
    return {"languages": app.state.sarvam_tts.get_supported_languages()}


@app.get("/sarvam/tts/speakers")
async def sarvam_tts_speakers():
    """Get available speakers for TTS"""
    if not app.state.sarvam_tts:
        raise HTTPException(
            status_code=503,
            detail="Sarvam TTS client not initialized"
        )
    
    return {"speakers": app.state.sarvam_tts.get_available_speakers()}


# ── Sarvam AI Speech-to-Text ─────────────────────────────────────────────────────

@app.post("/sarvam/stt")
async def sarvam_stt(req: SarvamSTTRequest, bg: BackgroundTasks):
    """Transcribe audio files using Sarvam AI"""
    if not app.state.sarvam_stt:
        raise HTTPException(
            status_code=503,
            detail="Sarvam STT client not initialized. Check SARVAM_API_KEY environment variable."
        )
    
    try:
        # Validate audio files exist
        for audio_path in req.audio_paths:
            if not os.path.exists(audio_path):
                raise HTTPException(
                    status_code=404,
                    detail=f"Audio file not found: {audio_path}"
                )
        
        # Start transcription in background
        def run_transcription():
            return app.state.sarvam_stt.transcribe_files(
                audio_paths=req.audio_paths,
                model=req.model,
                mode=req.mode,
                language_code=req.language_code,
                with_diarization=req.with_diarization,
                num_speakers=req.num_speakers,
                output_dir=req.output_dir
            )
        
        # For now, run synchronously (can be made async with proper job tracking)
        result = run_transcription()
        
        return {
            "status": "completed",
            "job_id": result["job_id"],
            "total_files": result["total_files"],
            "successful": result["successful"],
            "failed": result["failed"],
            "output_dir": result["output_dir"],
            "results": result["results"]
        }
        
    except Exception as e:
        logger.error(f"Sarvam STT error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sarvam/stt/languages")
async def sarvam_stt_languages():
    """Get supported languages for STT"""
    if not app.state.sarvam_stt:
        raise HTTPException(
            status_code=503,
            detail="Sarvam STT client not initialized"
        )
    
    return {"languages": app.state.sarvam_stt.get_supported_languages()}


@app.get("/sarvam/stt/models")
async def sarvam_stt_models():
    """Get available STT models"""
    if not app.state.sarvam_stt:
        raise HTTPException(
            status_code=503,
            detail="Sarvam STT client not initialized"
        )
    
    return {"models": app.state.sarvam_stt.get_available_models()}


# ── Sarvam AI STT File Upload ─────────────────────────────────────────────────────

@app.post("/sarvam/stt/upload")
async def sarvam_stt_upload(
    audio_file: UploadFile = File(..., description="Audio file to transcribe"),
    language_code: str = "hi-IN",
    model: str = "saaras:v3",
    with_diarization: bool = True
):
    """Upload and transcribe audio file using Sarvam AI"""
    logger.info(f"STT upload request: file='{audio_file.filename}', language='{language_code}', model='{model}'")
    
    if not app.state.sarvam_stt:
        logger.error("STT client not initialized")
        raise HTTPException(
            status_code=503,
            detail="Sarvam STT client not initialized. Check SARVAM_API_KEY environment variable."
        )
    
    try:
        # Create temporary directory for uploads
        upload_dir = tempfile.mkdtemp(prefix="ava_upload_")
        file_path = os.path.join(upload_dir, audio_file.filename)
        
        # Save uploaded file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await audio_file.read()
            await f.write(content)
        
        file_size = os.path.getsize(file_path)
        logger.info(f"Audio file saved: {file_path} ({file_size} bytes)")
        
        # Transcribe the file
        start_time = time.time()
        result = app.state.sarvam_stt.transcribe_single_file(
            audio_path=file_path,
            model=model,
            language_code=language_code,
            with_diarization=with_diarization,
            output_dir=upload_dir
        )
        transcription_time = time.time() - start_time
        
        # Extract transcript from results
        transcript = "Transcription completed"
        if result.get("results", {}).get("successful"):
            successful_files = result["results"]["successful"]
            if successful_files and len(successful_files) > 0:
                first_result = successful_files[0]
                # Try to read the transcript JSON file
                transcript_file = os.path.join(upload_dir, f"{audio_file.filename}.json")
                if os.path.exists(transcript_file):
                    import json
                    with open(transcript_file, 'r') as f:
                        transcript_data = json.load(f)
                        transcript = transcript_data.get("transcript", "Transcription completed")
        
        logger.info(f"Transcription completed in {transcription_time:.2f}s: '{transcript[:100]}...'")
        
        # Clean up temporary files
        import shutil
        try:
            shutil.rmtree(upload_dir)
            logger.info(f"Cleaned up temporary directory: {upload_dir}")
        except:
            pass
        
        return JSONResponse({
            "status": "completed",
            "transcript": transcript,
            "processing_time": f"{transcription_time:.2f}s",
            "file_size": file_size
        })
        
    except Exception as e:
        logger.error(f"STT upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── AVA Voice Assistant ─────────────────────────────────────────────────────

@app.post("/ava/chat")
async def ava_chat(req: AVAChatRequest):
    """Complete voice assistant workflow: STT -> LLM -> TTS"""
    logger.info(f"AVA chat request: message='{req.message[:50]}...'")
    
    if not app.state.sarvam_tts:
        logger.error("TTS client not initialized")
        raise HTTPException(
            status_code=503,
            detail="Sarvam TTS client not initialized"
        )
    
    if not app.state.ollama:
        logger.warning("Ollama not available, using simple response")
        # Fallback response when Ollama is not available
        fallback_response = "I'm AVA, your voice assistant. I can help you with text-to-speech and speech-to-text in Indian languages. Please ensure Ollama is running with llama3.2 model for full conversational capabilities."
        
        # Generate speech from fallback response
        try:
            temp_dir = tempfile.gettempdir()
            output_file = os.path.join(temp_dir, f"ava_response_{uuid.uuid4().hex[:8]}.mp3")
            
            result_file = app.state.sarvam_tts.stream_tts(
                text=fallback_response,
                target_language_code=req.language_code,
                speaker=req.speaker,
                model=req.model,
                pace=req.pace,
                output_file=output_file
            )
            
            # Return audio file
            def iterfile():
                with open(result_file, mode="rb") as file_like:
                    while True:
                        chunk = file_like.read(8192)
                        if not chunk:
                            break
                        yield chunk
            
            # Schedule cleanup
            import asyncio
            async def cleanup():
                await asyncio.sleep(1)
                try:
                    os.remove(result_file)
                except:
                    pass
            
            asyncio.create_task(cleanup())
            
            logger.info("Returning fallback audio response")
            return StreamingResponse(
                iterfile(),
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": "attachment; filename=ava_response.mp3",
                    "X-Audio-Codec": "mp3",
                    "X-Language": req.language_code,
                    "X-Speaker": req.speaker,
                    "X-Response-Type": "fallback"
                }
            )
            
        except Exception as e:
            logger.error(f"Fallback TTS failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    try:
        # Generate LLM response
        logger.info("Generating LLM response...")
        llm_response = app.state.ollama.generate_response(
            prompt=req.message,
            system_prompt="You are AVA, a helpful AI voice assistant specializing in Indian languages and culture.",
            max_tokens=300,
            temperature=0.7
        )
        
        logger.info(f"LLM response: '{llm_response[:100]}...'")
        
        # Generate speech from LLM response
        logger.info("Generating speech from LLM response...")
        temp_dir = tempfile.gettempdir()
        output_file = os.path.join(temp_dir, f"ava_response_{uuid.uuid4().hex[:8]}.mp3")
        
        start_time = time.time()
        result_file = app.state.sarvam_tts.stream_tts(
            text=llm_response,
            target_language_code=req.language_code,
            speaker=req.speaker,
            model=req.model,
            pace=req.pace,
            output_file=output_file
        )
        generation_time = time.time() - start_time
        
        # Return audio file
        def iterfile():
            with open(result_file, mode="rb") as file_like:
                while True:
                    chunk = file_like.read(8192)
                    if not chunk:
                        break
                    yield chunk
        
        # Schedule cleanup
        import asyncio
        async def cleanup():
            await asyncio.sleep(1)
            try:
                os.remove(result_file)
            except:
                pass
        
        asyncio.create_task(cleanup())
        
        logger.info(f"AVA chat completed in {generation_time:.2f}s")
        return StreamingResponse(
            iterfile(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=ava_response.mp3",
                "X-Audio-Codec": "mp3",
                "X-Language": req.language_code,
                "X-Speaker": req.speaker,
                "X-Response-Type": "llm_generated",
                "X-Generation-Time": f"{generation_time:.2f}s",
                "X-LLM-Model": app.state.ollama.model_name
            }
        )
        
    except Exception as e:
        logger.error(f"AVA chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
