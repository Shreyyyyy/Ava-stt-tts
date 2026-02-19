#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# AVA Setup Script — Run once after cloning
# ═══════════════════════════════════════════════════════════════════════════
set -e

echo ""
echo "  █████╗ ██╗   ██╗ █████╗ "
echo " ██╔══██╗██║   ██║██╔══██╗"
echo " ███████║██║   ██║███████║"
echo " ██╔══██║╚██╗ ██╔╝██╔══██║"
echo " ██║  ██║ ╚████╔╝ ██║  ██║"
echo " ╚═╝  ╚═╝  ╚═══╝  ╚═╝  ╚═╝"
echo ""
echo "  Digital AI Avatar — Setup"
echo "════════════════════════════════════════"

# ── 1. Python virtual environment ────────────────────────────────────────
echo ""
echo "▶ Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip --quiet

# ── 2. Core dependencies ─────────────────────────────────────────────────
echo ""
echo "▶ Installing core dependencies..."
pip install -r requirements.txt --quiet
echo "  ✓ Core dependencies installed"

# ── 3. Ollama check ──────────────────────────────────────────────────────
echo ""
echo "▶ Checking Ollama..."
if command -v ollama &> /dev/null; then
    echo "  ✓ Ollama is installed"
else
    echo "  ✗ Ollama not found."
    echo "  Install from: https://ollama.com"
    echo "  Then run: ollama pull llama3.2"
fi

# ── 4. Create required directories ───────────────────────────────────────
echo ""
echo "▶ Creating directories..."
mkdir -p memory/vectors adapters training/datasets logs models
echo "  ✓ Directories created"

# ── 5. Initialise DB ─────────────────────────────────────────────────────
echo ""
echo "▶ Initialising database..."
python3 -c "
import sys; sys.path.insert(0,'.')
from memory.database import init_db
init_db()
print('  ✓ Database initialised')
"

echo ""
echo "════════════════════════════════════════"
echo "✅  Setup complete!"
echo ""
echo "Next steps:"
echo ""
echo "  1. Start Ollama:          ollama serve"
echo "  2. Pull a model:          ollama pull llama3.2"
echo "  3. Activate venv:         source .venv/bin/activate"
echo "  4. Start AVA backend:     python main.py"
echo "  5. Start frontend:        python serve_frontend.py"
echo "  6. Open browser:          http://localhost:3000"
echo ""
echo "Optional (fine-tuning support):"
echo "  pip install -r requirements-training.txt"
echo ""
