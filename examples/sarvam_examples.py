#!/usr/bin/env python3
"""
Examples of using Sarvam AI TTS and STT services
"""

import os
import requests
import json
from pathlib import Path

# API base URL (assuming backend is running on localhost:8000)
BASE_URL = "http://localhost:8000"

def test_tts():
    """Test text-to-speech conversion"""
    print("=== Testing Sarvam TTS ===")
    
    # Test with Hindi text
    tts_data = {
        "text": "नमस्ते! यह एक परीक्षण है। मैं आपकी क्या सहायता कर सकती हूँ?",
        "target_language_code": "hi-IN",
        "speaker": "shreya",
        "model": "bulbul:v3",
        "pace": 1.1
    }
    
    try:
        response = requests.post(f"{BASE_URL}/sarvam/tts", json=tts_data)
        
        if response.status_code == 200:
            # Save audio file
            with open("tts_output.mp3", "wb") as f:
                f.write(response.content)
            print(f"✓ TTS successful! Audio saved to tts_output.mp3")
            print(f"  Content-Type: {response.headers.get('content-type')}")
            print(f"  Language: {response.headers.get('X-Language')}")
            print(f"  Speaker: {response.headers.get('X-Speaker')}")
        else:
            print(f"✗ TTS failed: {response.status_code}")
            print(f"  Error: {response.text}")
            
    except Exception as e:
        print(f"✗ TTS error: {e}")

def test_tts_languages():
    """Test getting supported TTS languages"""
    print("\n=== Testing TTS Languages ===")
    
    try:
        response = requests.get(f"{BASE_URL}/sarvam/tts/languages")
        
        if response.status_code == 200:
            languages = response.json()
            print("✓ Supported TTS languages:")
            for code, name in languages["languages"].items():
                print(f"  {code}: {name}")
        else:
            print(f"✗ Failed to get TTS languages: {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error getting TTS languages: {e}")

def test_tts_speakers():
    """Test getting available TTS speakers"""
    print("\n=== Testing TTS Speakers ===")
    
    try:
        response = requests.get(f"{BASE_URL}/sarvam/tts/speakers")
        
        if response.status_code == 200:
            speakers = response.json()
            print("✓ Available TTS speakers:")
            for speaker, description in speakers["speakers"].items():
                print(f"  {speaker}: {description}")
        else:
            print(f"✗ Failed to get TTS speakers: {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error getting TTS speakers: {e}")

def test_stt():
    """Test speech-to-text conversion"""
    print("\n=== Testing Sarvam STT ===")
    
    # Create a dummy audio file path (you'll need to replace with actual audio)
    audio_file = "sample_audio.mp3"
    
    if not os.path.exists(audio_file):
        print(f"✗ Audio file not found: {audio_file}")
        print("  Please provide a valid audio file path to test STT")
        return
    
    stt_data = {
        "audio_paths": [audio_file],
        "model": "saaras:v3",
        "mode": "transcribe",
        "language_code": "hi-IN",
        "with_diarization": True,
        "num_speakers": 1,
        "output_dir": "./stt_output"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/sarvam/stt", json=stt_data)
        
        if response.status_code == 200:
            result = response.json()
            print("✓ STT successful!")
            print(f"  Job ID: {result['job_id']}")
            print(f"  Total files: {result['total_files']}")
            print(f"  Successful: {result['successful']}")
            print(f"  Failed: {result['failed']}")
            print(f"  Output directory: {result['output_dir']}")
        else:
            print(f"✗ STT failed: {response.status_code}")
            print(f"  Error: {response.text}")
            
    except Exception as e:
        print(f"✗ STT error: {e}")

def test_stt_languages():
    """Test getting supported STT languages"""
    print("\n=== Testing STT Languages ===")
    
    try:
        response = requests.get(f"{BASE_URL}/sarvam/stt/languages")
        
        if response.status_code == 200:
            languages = response.json()
            print("✓ Supported STT languages:")
            for code, name in languages["languages"].items():
                print(f"  {code}: {name}")
        else:
            print(f"✗ Failed to get STT languages: {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error getting STT languages: {e}")

def test_stt_models():
    """Test getting available STT models"""
    print("\n=== Testing STT Models ===")
    
    try:
        response = requests.get(f"{BASE_URL}/sarvam/stt/models")
        
        if response.status_code == 200:
            models = response.json()
            print("✓ Available STT models:")
            for model, description in models["models"].items():
                print(f"  {model}: {description}")
        else:
            print(f"✗ Failed to get STT models: {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error getting STT models: {e}")

def check_backend_health():
    """Check if backend is running"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print("✓ Backend is running!")
            print(f"  Status: {health.get('status')}")
            return True
        else:
            print(f"✗ Backend health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Cannot connect to backend: {e}")
        print("  Make sure the backend is running on http://localhost:8000")
        return False

if __name__ == "__main__":
    print("Sarvam AI API Examples")
    print("=" * 50)
    
    # Check if backend is running
    if not check_backend_health():
        exit(1)
    
    # Test TTS endpoints
    test_tts_languages()
    test_tts_speakers()
    test_tts()
    
    # Test STT endpoints
    test_stt_languages()
    test_stt_models()
    test_stt()
    
    print("\n" + "=" * 50)
    print("Example tests completed!")
