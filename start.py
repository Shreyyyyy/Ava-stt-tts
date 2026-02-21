#!/usr/bin/env python3
"""
Start AVA Sarvam AI Voice Interface
Runs both backend and frontend servers
"""

import subprocess
import sys
import time
import os
from pathlib import Path

def check_requirements():
    """Check if required files exist"""
    required_files = [
        "backend/server.py",
        "frontend/index.html",
        "frontend/app.js",
        "frontend/style.css",
        ".env"
    ]
    
    missing = []
    for file in required_files:
        if not Path(file).exists():
            missing.append(file)
    
    if missing:
        print("❌ Missing required files:")
        for file in missing:
            print(f"   - {file}")
        print("\nPlease ensure you're in the project root directory.")
        return False
    
    return True

def check_env():
    """Check if .env file has API key"""
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found!")
        print("Please create a .env file with your Sarvam AI API key:")
        print("SARVAM_API_KEY=your_api_key_here")
        return False
    
    content = env_file.read_text().strip()
    if "SARVAM_API_KEY" not in content or "your_api_key_here" in content:
        print("❌ SARVAM_API_KEY not configured in .env file!")
        print("Please add your Sarvam AI API key to the .env file.")
        return False
    
    return True

def start_backend():
    """Start the backend server"""
    print("🔧 Starting backend server...")
    backend_cmd = [
        sys.executable, "-m", "uvicorn", 
        "backend.server:app", 
        "--host", "0.0.0.0", 
        "--port", "8000"
    ]
    
    return subprocess.Popen(
        backend_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )

def start_frontend():
    """Start the frontend server"""
    print("🌐 Starting frontend server...")
    frontend_cmd = [sys.executable, "serve_frontend.py"]
    
    return subprocess.Popen(
        frontend_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )

def main():
    print("🎤 AVA Sarvam AI Voice Interface")
    print("=" * 40)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check environment
    if not check_env():
        sys.exit(1)
    
    try:
        # Start backend
        backend_process = start_backend()
        time.sleep(2)  # Give backend time to start
        
        # Start frontend
        frontend_process = start_frontend()
        time.sleep(1)
        
        print("\n✅ Services started successfully!")
        print("🌐 Frontend: http://localhost:3001")
        print("🔧 Backend:  http://localhost:8000")
        print("📚 API Docs: http://localhost:8000/docs")
        print("\nPress Ctrl+C to stop both servers")
        print("=" * 40)
        
        # Monitor processes
        while True:
            # Check if processes are still running
            if backend_process.poll() is not None:
                print("❌ Backend server stopped unexpectedly")
                break
                
            if frontend_process.poll() is not None:
                print("❌ Frontend server stopped unexpectedly")
                break
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping servers...")
        
        # Terminate processes
        if 'backend_process' in locals():
            backend_process.terminate()
            backend_process.wait()
            
        if 'frontend_process' in locals():
            frontend_process.terminate()
            frontend_process.wait()
            
        print("✅ Servers stopped successfully")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
