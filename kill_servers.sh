#!/bin/bash
# Quick script to kill AVA servers
echo "🛑 Killing AVA servers..."

# Kill backend (port 8000)
lsof -ti:8000 | xargs kill -9 2>/dev/null || echo "No backend process on port 8000"

# Kill frontend (port 3001)  
lsof -ti:3001 | xargs kill -9 2>/dev/null || echo "No frontend process on port 3001"

# Kill by name as backup
pkill -f "uvicorn" 2>/dev/null || echo "No uvicorn processes"
pkill -f "serve_frontend.py" 2>/dev/null || echo "No frontend script processes"

echo "✅ Done! All AVA servers should be stopped."
