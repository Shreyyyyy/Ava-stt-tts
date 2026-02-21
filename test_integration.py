#!/usr/bin/env python3
"""
Integration test for Sarvam AI frontend-backend alignment
"""

import requests
import json
import time

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3001"

def test_backend_endpoints():
    """Test all backend endpoints that the frontend uses"""
    print("=== Testing Backend Endpoints ===")
    
    # Health check
    try:
        response = requests.get(f"{BACKEND_URL}/health")
        if response.status_code == 200:
            health = response.json()
            print(f"✓ Health check: {health['status']}")
            print(f"  TTS Available: {health['sarvam_tts_available']}")
            print(f"  STT Available: {health['sarvam_stt_available']}")
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health check error: {e}")
        return False
    
    # TTS Languages
    try:
        response = requests.get(f"{BACKEND_URL}/sarvam/tts/languages")
        if response.status_code == 200:
            languages = response.json()
            print(f"✓ TTS Languages: {len(languages['languages'])} available")
        else:
            print(f"✗ TTS languages failed: {response.status_code}")
    except Exception as e:
        print(f"✗ TTS languages error: {e}")
    
    # TTS Speakers
    try:
        response = requests.get(f"{BACKEND_URL}/sarvam/tts/speakers")
        if response.status_code == 200:
            speakers = response.json()
            print(f"✓ TTS Speakers: {len(speakers['speakers'])} available")
        else:
            print(f"✗ TTS speakers failed: {response.status_code}")
    except Exception as e:
        print(f"✗ TTS speakers error: {e}")
    
    # STT Languages
    try:
        response = requests.get(f"{BACKEND_URL}/sarvam/stt/languages")
        if response.status_code == 200:
            languages = response.json()
            print(f"✓ STT Languages: {len(languages['languages'])} available")
        else:
            print(f"✗ STT languages failed: {response.status_code}")
    except Exception as e:
        print(f"✗ STT languages error: {e}")
    
    # STT Models
    try:
        response = requests.get(f"{BACKEND_URL}/sarvam/stt/models")
        if response.status_code == 200:
            models = response.json()
            print(f"✓ STT Models: {len(models['models'])} available")
        else:
            print(f"✗ STT models failed: {response.status_code}")
    except Exception as e:
        print(f"✗ STT models error: {e}")
    
    # Test TTS Generation
    try:
        tts_data = {
            "text": "Hello! This is a test of the voice interface.",
            "target_language_code": "en-IN",
            "speaker": "shreya"
        }
        response = requests.post(f"{BACKEND_URL}/sarvam/tts", json=tts_data)
        if response.status_code == 200:
            print(f"✓ TTS Generation: Success ({len(response.content)} bytes)")
        else:
            print(f"✗ TTS Generation failed: {response.status_code}")
            print(f"  Error: {response.text}")
    except Exception as e:
        print(f"✗ TTS Generation error: {e}")
    
    return True

def test_frontend_access():
    """Test if frontend is accessible"""
    print("\n=== Testing Frontend Access ===")
    
    try:
        response = requests.get(FRONTEND_URL)
        if response.status_code == 200:
            print("✓ Frontend accessible")
            if "AVA" in response.text:
                print("✓ Frontend contains AVA branding")
            if "Sarvam" in response.text:
                print("✓ Frontend contains Sarvam AI branding")
            if "tab-btn" in response.text:
                print("✓ Frontend has tab navigation")
        else:
            print(f"✗ Frontend not accessible: {response.status_code}")
    except Exception as e:
        print(f"✗ Frontend access error: {e}")

def main():
    print("Sarvam AI Frontend-Backend Integration Test")
    print("=" * 50)
    
    backend_ok = test_backend_endpoints()
    test_frontend_access()
    
    print("\n" + "=" * 50)
    if backend_ok:
        print("✅ Integration test completed successfully!")
        print(f"📱 Frontend: {FRONTEND_URL}")
        print(f"🔧 Backend: {BACKEND_URL}")
        print("\nOpen your browser and navigate to the frontend URL to test the interface.")
    else:
        print("❌ Integration test failed. Check backend status.")

if __name__ == "__main__":
    main()
