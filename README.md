# AVA — Digital AI Avatar
## A fully local, self-improving AI that learns how you think

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green)](https://fastapi.tiangolo.com)
[![Ollama](https://img.shields.io/badge/Ollama-local-purple)](https://ollama.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🧠 What is AVA?

AVA is a **fully local**, **self-improving** digital AI avatar that you talk to every day. Over time, it learns your:
- Communication style (directness, formality, emotional tone)
- Vocabulary and sentence patterns
- Reasoning preferences
- Domain interests

All learning happens on your machine — **no cloud, no paid APIs, zero data leaves your device**.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         YOU (via Browser/Phone)                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │  HTTP (localhost:3000)
                               ▼
┌──────────────────── Frontend (Vanilla JS) ──────────────────────┐
│  • Chat UI        • Voice Input/Output   • Feedback Buttons      │
│  • Memory Panel   • Profile Dashboard    • Training Controls     │
└──────────────────────────────┬──────────────────────────────────┘
                               │  REST API (localhost:8000)
                               ▼
┌──────────────────── Backend (FastAPI) ──────────────────────────┐
│                                                                   │
│  POST /chat          ──► LLM Client ──► Ollama (llama3.2/mistral)  │
│  POST /feedback      ──► Feedback storage + scoring              │
│  GET  /memory        ──► SQLite conversation history             │
│  GET  /memory/search ──► FAISS vector search                     │
│  GET  /memory/profile──► Personality profile JSON                │
│  POST /training/trigger ► LoRA fine-tuning pipeline              │
│                                                                   │
└──────┬────────────────────┬────────────────────┬────────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌────────────┐    ┌─────────────────┐   ┌──────────────────────┐
│   SQLite   │    │  FAISS Vector   │   │  Style Analyzer      │
│  database  │    │  Store (disk)   │   │  (EMA profile)       │
│            │    │  + all-MiniLM   │   │                      │
│ • convs    │    │  embeddings     │   │  personality_profile │
│ • feedback │    │                 │   │  .json (human-       │
│ • style    │    │                 │   │  readable)           │
│ • training │    │                 │   │                      │
└────────────┘    └─────────────────┘   └──────────────────────┘
                                                   │
                                                   ▼
                                    ┌──────────────────────────┐
                                    │  Training Pipeline       │
                                    │  (QLoRA + PEFT + TRL)    │
                                    │                          │
                                    │  • Filter high-quality   │
                                    │    examples from SQLite  │
                                    │  • Build JSONL dataset   │
                                    │  • Fine-tune LoRA        │
                                    │  • Save /adapters/<ver>/ │
                                    │  • Symlink "latest"      │
                                    └──────────────────────────┘
```

---

## 📁 Project Structure

```
/Ava
├── main.py                     ← Application entry-point
├── serve_frontend.py           ← Static file server for UI
├── setup.sh                    ← One-shot setup script
├── requirements.txt            ← Core dependencies
├── requirements-training.txt   ← Heavy ML deps (optional)
│
├── /backend
│   ├── server.py               ← FastAPI app + all endpoints
│   └── llm_client.py           ← Ollama HTTP client
│
├── /memory
│   ├── database.py             ← SQLite schema + CRUD
│   ├── vector_store.py         ← FAISS vector store
│   ├── style_analyzer.py       ← Style metric extractor
│   └── personality_profile.json← Evolving human-readable profile
│
├── /training
│   ├── train_adapter.py        ← QLoRA fine-tuning pipeline
│   └── /datasets/              ← Versioned JSONL training files
│
├── /adapters
│   ├── /20240219_123456/       ← Versioned LoRA adapter
│   └── latest → symlink        ← Points to newest adapter
│
├── /frontend
│   ├── index.html              ← App shell
│   ├── style.css               ← Dark glassmorphism UI
│   └── app.js                  ← All UI logic
│
├── /memory
│   ├── ava_memory.db           ← SQLite database
│   └── /vectors/               ← FAISS index + metadata
│
├── /logs
│   ├── ava.log                 ← Application logs
│   └── training.log            ← Training run logs
│
└── /models                     ← Place HF model weights here
                                   (for offline fine-tuning)
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) installed

### 1. Setup
```bash
cd /path/to/Ava
chmod +x setup.sh && ./setup.sh
```

### 2. Start Ollama + pull a model
```bash
ollama serve                    # in terminal 1
ollama pull llama3.2              # or: ollama pull mistral
```

### 3. Start AVA backend
```bash
source .venv/bin/activate
python main.py                  # starts on http://localhost:8000
```

### 4. Start the UI
```bash
python serve_frontend.py        # serves on http://localhost:3000
```

Open `http://localhost:3000` on your phone's browser — it's fully mobile responsive.

---

## 🎯 Feedback System

After each response, tap one of these buttons:

| Button | Score | Effect |
|---|---|---|
| 👍 **Sounds like me** | 1.0 | Positive reinforcement |
| 📝 **Too verbose** | 0.3 | Teaches brevity |
| 🌸 **Too soft** | 0.4 | Teaches assertiveness |
| ❌ **Wrong reasoning** | 0.1 | Flags logical errors |
| ✏️ **Rewrite** | 0.2 | You provide the correct response |

---

## 🧠 The Self-Improvement Loop

```
Daily Conversation
       │
       ▼
Feedback + Corrections stored in SQLite
       │
       ▼ (weekly or on-demand)
High-quality examples extracted (score ≥ 0.7)
       │
       ▼
QLoRA fine-tuning run (on your GPU)
       │
       ▼
New LoRA adapter saved to /adapters/<timestamp>/
       │
       ▼
"latest" symlink updated
       │
       ▼           (future: attach adapter to Ollama via Modelfile)
AVA is smarter
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/chat` | Send a message, get a response |
| POST | `/feedback` | Submit feedback on a conversation turn |
| GET | `/memory` | Retrieve recent conversations |
| GET | `/memory/search?q=...` | Semantic search over memory |
| GET | `/memory/profile` | Current personality profile |
| POST | `/training/trigger` | Kick off LoRA fine-tuning |
| GET | `/training/history` | List past training runs |
| GET | `/health` | System health (Ollama status, etc.) |
| GET | `/models` | Available Ollama models |

Swagger UI: `http://localhost:8000/docs`

---

## 🏋️ Training Pipeline

### Manual trigger
```bash
python training/train_adapter.py \
  --model llama3.2 \
  --min-score 0.7 \
  --max-examples 500 \
  --epochs 3 \
  --hf-model-name meta-llama/Meta-Llama-3-8B
```

### Requirements
```bash
pip install -r requirements-training.txt
```

> **VRAM:** ~10 GB for Llama 3 8B with 4-bit QLoRA. For Mistral 7B, similar.

### Adapter versioning
Each run creates `/adapters/YYYYMMDD_HHMMSS/` with:
- LoRA adapter weights
- Tokenizer config
- `manifest.json` (version, dataset size, config)

---

## 🎙️ Voice (Phone Access)

1. **Access from phone:** Open `http://<your-local-ip>:3000`
2. **Microphone:** Tap the mic button — uses Web Speech API
3. **Audio output:** Tap 🔊 Speak to hear AVA's last response

> Add `?model=mistral` to the URL to switch models dynamically.

---

## 🔒 Privacy

- **100% local** — no data sent to any server
- SQLite database stored at `memory/ava_memory.db`
- FAISS index at `memory/vectors/`
- Personality profile at `memory/personality_profile.json`

---

## 🛣️ Roadmap

- [ ] Attach trained LoRA adapter via Ollama Modelfile
- [ ] Automatic weekly training scheduler
- [ ] Export/import memory backup
- [ ] Multi-user profiles
- [ ] Whisper.cpp for offline speech recognition
- [ ] Piper TTS for offline voice synthesis

---

## 📜 License

MIT — free to use, modify, and distribute.
