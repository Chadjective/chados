#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════╗"
echo "║     Personal Google Archive — Setup      ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Check Python ──
echo "Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found."
    echo "   Install it from https://www.python.org/downloads/"
    echo "   or run: xcode-select --install"
    exit 1
fi
PY_VERSION=$(python3 --version 2>&1)
echo "   ✅ $PY_VERSION"

# ── 2. Check/Install Node.js ──
echo "Checking Node.js..."
NODE_BIN=""
if command -v node &> /dev/null; then
    NODE_BIN="node"
elif [ -f "$HOME/.local/node/bin/node" ]; then
    NODE_BIN="$HOME/.local/node/bin/node"
    export PATH="$HOME/.local/node/bin:$PATH"
fi

if [ -z "$NODE_BIN" ]; then
    echo "   Node.js not found. Installing..."
    ARCH=$(uname -m)
    if [ "$ARCH" = "arm64" ]; then
        NODE_URL="https://nodejs.org/dist/v20.11.0/node-v20.11.0-darwin-arm64.tar.xz"
    else
        NODE_URL="https://nodejs.org/dist/v20.11.0/node-v20.11.0-darwin-x64.tar.xz"
    fi
    mkdir -p "$HOME/.local/node"
    curl -fsSL "$NODE_URL" | tar -xJ --strip-components=1 -C "$HOME/.local/node"
    export PATH="$HOME/.local/node/bin:$PATH"
    NODE_BIN="$HOME/.local/node/bin/node"
    echo "   ✅ Node.js installed to ~/.local/node/"
else
    echo "   ✅ $(${NODE_BIN} --version)"
fi

# ── 3. Set up Python virtual environment ──
echo "Setting up Python environment..."
if [ ! -d "$SCRIPT_DIR/backend/venv" ]; then
    python3 -m venv "$SCRIPT_DIR/backend/venv"
fi
source "$SCRIPT_DIR/backend/venv/bin/activate"
pip install -q -r "$SCRIPT_DIR/backend/requirements.txt"
echo "   ✅ Python dependencies installed"

# ── 3b. Optional AI features ──
echo ""
echo "── AI Features (Optional) ──"
echo ""
echo "AI features add semantic search (meaning-based, not just keywords)"
echo "and an AI chat that can answer questions about your archive."
echo "Requires ~6GB disk for models + Ollama (free, local AI runtime)."
echo ""
read -p "Install AI features? [y/N]: " INSTALL_AI
if [ "$INSTALL_AI" = "y" ] || [ "$INSTALL_AI" = "Y" ]; then
    echo "   Installing AI dependencies..."
    pip install -q -r "$SCRIPT_DIR/backend/requirements-ai.txt"
    ENABLE_AI="true"
    echo "   ✅ AI dependencies installed"

    # Check/install Ollama
    if ! command -v ollama &> /dev/null && [ ! -f "$HOME/.local/bin/ollama" ]; then
        echo ""
        echo "   Ollama (local AI runtime) not found."
        echo "   Downloading Ollama..."
        curl -fsSL https://ollama.com/download/Ollama-darwin.zip -o /tmp/Ollama.zip
        unzip -q -o /tmp/Ollama.zip -d /tmp/OllamaApp
        cp -R /tmp/OllamaApp/Ollama.app /Applications/ 2>/dev/null || true
        mkdir -p "$HOME/.local/bin"
        ln -sf /Applications/Ollama.app/Contents/Resources/ollama "$HOME/.local/bin/ollama"
        rm -rf /tmp/Ollama.zip /tmp/OllamaApp
        echo "   ✅ Ollama installed"
        echo ""
        echo "   Starting Ollama and downloading models..."
        open /Applications/Ollama.app
        sleep 3
        "$HOME/.local/bin/ollama" pull nomic-embed-text
        "$HOME/.local/bin/ollama" pull llama3.1:8b
        echo "   ✅ AI models downloaded"
    else
        echo "   ✅ Ollama already installed"
    fi
else
    ENABLE_AI="false"
    echo "   Skipped. You can add AI later by running:"
    echo "   pip install -r backend/requirements-ai.txt"
fi

# ── 4. Install frontend dependencies ──
echo "Setting up frontend..."
cd "$SCRIPT_DIR/frontend"
npm install --silent 2>/dev/null
echo "   ✅ Frontend dependencies installed"

# ── 5. Configure data directory ──
echo ""
echo "── Data Configuration ──"
echo ""
DEFAULT_DATA_DIR="$HOME/personal-archive-data"

if [ -n "$ARCHIVE_DB_DIR" ]; then
    DATA_DIR="$ARCHIVE_DB_DIR"
    echo "Using ARCHIVE_DB_DIR: $DATA_DIR"
else
    echo "Where should the database and thumbnails be stored?"
    echo "This should be on a fast drive (internal SSD recommended)."
    echo ""
    read -p "Data directory [$DEFAULT_DATA_DIR]: " DATA_DIR
    DATA_DIR="${DATA_DIR:-$DEFAULT_DATA_DIR}"
fi

mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/thumbnails"
mkdir -p "$DATA_DIR/attachments"

# Write a local .env file for convenience
cat > "$SCRIPT_DIR/.env" << EOF
ARCHIVE_DB_DIR=$DATA_DIR
ARCHIVE_ATTACHMENTS_DIR=$DATA_DIR/attachments
ARCHIVE_ENABLE_AI=$ENABLE_AI
EOF

echo "   ✅ Data directory: $DATA_DIR"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║           Setup Complete! ✅             ║"
echo "╠══════════════════════════════════════════╣"
echo "║                                          ║"
echo "║  Next steps:                             ║"
echo "║                                          ║"
echo "║  1. Import your data:                    ║"
echo "║     ./import.sh /path/to/Takeout         ║"
echo "║                                          ║"
echo "║  2. Start the app:                       ║"
echo "║     ./start.sh                           ║"
echo "║                                          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
