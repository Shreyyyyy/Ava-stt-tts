#!/usr/bin/env python3
"""
AVA – Application entry-point.
Starts the FastAPI backend with Uvicorn.
"""

import sys
import logging
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/ava.log"),
    ],
)

logger = logging.getLogger("ava.main")


def main():
    from pathlib import Path
    Path("logs").mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("   AVA – Digital AI Avatar v1.0")
    logger.info("=" * 60)

    # Verify Ollama
    from backend.llm_client import is_ollama_running, list_local_models
    if not is_ollama_running():
        logger.warning(
            "⚠  Ollama is NOT running. Start it with: ollama serve\n"
            "   Chat will fail until Ollama is available."
        )
    else:
        models = list_local_models()
        names  = [m.get("name") for m in models]
        logger.info(f"✓  Ollama running. Available models: {names}")
        if not names:
            logger.warning(
                "⚠  No models pulled. Run: ollama pull llama3.2"
            )

    logger.info("Starting API server on http://0.0.0.0:8000")
    uvicorn.run(
        "backend.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
