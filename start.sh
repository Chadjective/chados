#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load .env if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# Ensure node and local tools are available
export PATH="$HOME/.local/node/bin:$HOME/.local/bin:$PATH"
if command -v fnm &> /dev/null; then
    eval "$(fnm env)"
fi

echo "=================================="
echo "  Personal Google Archive"
echo "=================================="
echo ""

# Set up Python virtual environment if needed
if [ ! -d "$SCRIPT_DIR/backend/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$SCRIPT_DIR/backend/venv"
    source "$SCRIPT_DIR/backend/venv/bin/activate"
    pip install -r "$SCRIPT_DIR/backend/requirements.txt"
else
    source "$SCRIPT_DIR/backend/venv/bin/activate"
fi

# Install frontend deps if needed
if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd "$SCRIPT_DIR/frontend" && npm install
fi

# Kill any existing instances
pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "vite.*5173" 2>/dev/null || true
sleep 1

# Start backend
echo "Starting backend on http://localhost:8000 ..."
cd "$SCRIPT_DIR/backend"
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend dev server
echo "Starting frontend on http://localhost:5173 ..."
cd "$SCRIPT_DIR/frontend"
npm run dev -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!

# Wait for servers to be ready
echo "Waiting for servers..."
sleep 3

# Open browser
echo "Opening browser..."
open "http://localhost:5173" 2>/dev/null || xdg-open "http://localhost:5173" 2>/dev/null || true

echo ""
echo "╔══════════════════════════════════════╗"
echo "║    Personal Google Archive is up!    ║"
echo "╠══════════════════════════════════════╣"
echo "║  Frontend: http://localhost:5173     ║"
echo "║  Backend:  http://localhost:8000     ║"
echo "║  API docs: http://localhost:8000/docs║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Also accessible from other devices on your network."
echo "Press Ctrl+C to stop."

# Trap Ctrl+C to clean up both processes
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait 2>/dev/null
    echo "Done."
}
trap cleanup SIGINT SIGTERM

# Wait for either to exit
wait
