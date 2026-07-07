#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-3000}

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID $CELERY_PID 2>/dev/null || true
    wait 2>/dev/null || true
    echo "All services stopped."
}
trap cleanup EXIT INT TERM

# Start backend
echo "Starting backend on port $BACKEND_PORT..."
source "$VENV/bin/activate"
cd "$ROOT/backend"
uvicorn main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!
cd "$ROOT"

sleep 2

# Start Celery worker
echo "Starting Celery worker..."
celery -A backend.src.worker.celery_app worker \
  -Q default,audio,transcription,llm,tts,pptx,priority_high \
  -l WARNING \
  --concurrency=2 &
CELERY_PID=$!

sleep 1

# Start frontend
echo "Starting frontend on port $FRONTEND_PORT..."
cd "$ROOT/frontend"
npx next start --port "$FRONTEND_PORT" --hostname 0.0.0.0 &
FRONTEND_PID=$!
cd "$ROOT"

echo ""
echo "==========================================="
echo " Backend:  http://localhost:$BACKEND_PORT"
echo " Frontend: http://localhost:$FRONTEND_PORT"
echo "==========================================="
echo "Press Ctrl+C to stop all services."
echo ""

wait
