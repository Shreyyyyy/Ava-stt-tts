# AVA — Sarvam AI Voice Interface
## Indian language text-to-speech and speech-to-text

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green)](https://fastapi.tiangolo.com)
[![Sarvam AI](https://img.shields.io/badge/Sarvam%20AI-Indian%20Languages-orange)](https://sarvam.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎤 What is AVA?

AVA is a **voice interface** powered by **Sarvam AI** that provides:
- **Text-to-Speech** in 10+ Indian languages
- **Speech-to-Text** transcription with speaker diarization
- **Multiple voice options** for different personas
- **Web-based interface** for easy access

Perfect for applications requiring Indian language voice capabilities with natural, high-quality synthesis.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Sarvam AI API key (get from [sarvam.ai](https://sarvam.ai))

### Installation

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables**
   ```bash
   # Edit .env and add your Sarvam AI API key
   SARVAM_API_KEY=your_api_key_here
   ```

### Running the Application

**Option 1: Use the startup script (Recommended)**
```bash
python start.py
```

**Option 2: Manual startup**
```bash
# Terminal 1: Start backend
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000

# Terminal 2: Start frontend  
python serve_frontend.py
```

3. **Access the application**
   - Frontend: http://localhost:3001
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

---

## 🎛️ Features

### Text-to-Speech (TTS)
- **10 Indian Languages**: Hindi, Bengali, Gujarati, Kannada, Malayalam, Marathi, Punjabi, Tamil, Telugu, English (Indian)
- **4 Voice Options**: Shreya (female), Meera (female), Arvind (male), Kavita (female)
- **Customizable**: Speech pace, sample rate, audio codec

### Speech-to-Text (STT)
- **11 Languages**: Auto-detect + 10 Indian languages
- **Speaker Diarization**: Identify different speakers in audio
- **Batch Processing**: Handle multiple audio files

---

## 📝 API Usage

### Text-to-Speech
```bash
curl -X POST "http://localhost:8000/sarvam/tts" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "नमस्ते! यह एक परीक्षण है।",
    "target_language_code": "hi-IN",
    "speaker": "shreya"
  }' \
  --output speech.mp3
```

### Speech-to-Text
```bash
curl -X POST "http://localhost:8000/sarvam/stt" \
  -H "Content-Type: application/json" \
  -d '{
    "audio_paths": ["audio.mp3"],
    "language_code": "hi-IN",
    "with_diarization": true
  }'
```

---

## 🗂️ Project Structure

```
Ava/
├── backend/                    # Sarvam AI backend
│   ├── server.py              # FastAPI with Sarvam endpoints
│   ├── sarvam_tts_client.py   # TTS client
│   └── sarvam_stt_client.py   # STT client
├── frontend/                   # Web interface
│   ├── index.html             # Main UI
│   ├── app.js                # Frontend logic
│   └── style.css             # Styling
├── examples/
│   └── sarvam_examples.py    # API usage examples
├── .env                       # API key configuration
├── .gitignore                 # Git ignore file
├── requirements.txt            # Python dependencies
├── serve_frontend.py          # Frontend server
├── start.py                  # Startup script (recommended)
├── test_integration.py        # Integration tests
└── README.md                 # This file
```

---

## 🔧 Configuration

### Environment Variables
Create a `.env` file with:
```env
SARVAM_API_KEY=your_sarvam_api_key_here
```

### Supported Languages

**TTS Languages:**
- `hi-IN` - Hindi
- `bn-IN` - Bengali  
- `gu-IN` - Gujarati
- `kn-IN` - Kannada
- `ml-IN` - Malayalam
- `mr-IN` - Marathi
- `pa-IN` - Punjabi
- `ta-IN` - Tamil
- `te-IN` - Telugu
- `en-IN` - English (Indian)

**Voice Speakers:**
- `shreya` - Female voice (Hindi)
- `meera` - Female voice (Hindi)
- `arvind` - Male voice (Hindi)
- `kavita` - Female voice (Hindi)

---

## 🧪 Testing

Run the integration test to verify everything works:
```bash
python test_integration.py
```

---

## 📄 License

This project is licensed under the MIT License.
