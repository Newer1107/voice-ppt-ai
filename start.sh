#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-3000}

# AI server — change AI_SERVICE_HOST to your GPU server's IP
# Docker: http://gpu-service:8001   |   Direct: http://<gpu-server-ip>:8001
AI_SERVICE_HOST=${AI_SERVICE_HOST:-"175.175.0.254"}
export AI_SERVICE_URL="http://${AI_SERVICE_HOST}:8001"

echo "AI_SERVICE_URL=$AI_SERVICE_URL"

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID $CELERY_PID 2>/dev/null || true
    wait 2>/dev/null || true
    echo "All services stopped."
}
trap cleanup EXIT INT TERM

# Start backend (from project root so backend.src.* imports resolve)
echo "Starting backend on port $BACKEND_PORT..."
source "$VENV/bin/activate"
cd "$ROOT"
uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

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
