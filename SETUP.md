# AI Lecture Narration Platform — Setup Guide

> **Last Updated:** 2026-07-04  
> **Environment:** Development / Staging / Production  
> **Stack:** Python 3.11+, FastAPI, Next.js 14, PostgreSQL 16, Redis 7, Celery

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Architecture Overview](#2-architecture-overview)
3. [Quick Start (Development)](#3-quick-start-development)
4. [Backend Setup](#4-backend-setup)
5. [Frontend Setup](#5-frontend-setup)
6. [Database Setup](#6-database-setup)
7. [GPU Server Setup](#7-gpu-server-setup)
8. [Running the Pipeline](#8-running-the-pipeline)
9. [Running Tests](#9-running-tests)
10. [Docker Deployment](#10-docker-deployment)
11. [Configuration Reference](#11-configuration-reference)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. System Requirements

### Minimum (Development)

| Component | Specification |
|-----------|---------------|
| **CPU** | 4+ cores (Intel i7 / AMD Ryzen 7) |
| **RAM** | 8 GB |
| **Storage** | 20 GB free |
| **OS** | Ubuntu 24.04 / macOS 14+ / Windows 11 |
| **Python** | 3.11 or 3.12 |
| **Node.js** | 20 LTS or later |
| **PostgreSQL** | 15 or 16 |
| **Redis** | 7.x |
| **FFmpeg** | Latest stable |

### Production (Application Server — Machine A)

| Component | Specification |
|-----------|---------------|
| **CPU** | Intel i7-14700 or equivalent |
| **RAM** | 8 GB minimum, 16 GB recommended |
| **Storage** | 100 GB+ SSD |
| **OS** | Ubuntu 24.04 LTS |
| **Docker** | 24+ with Compose v2 |
| **Network** | Low-latency connection to GPU server |

### Production (GPU Server — Machine B)

| Component | Specification |
|-----------|---------------|
| **GPU** | NVIDIA Blackwell 24GB+ VRAM |
| **CPU** | 8+ cores |
| **RAM** | 32 GB |
| **Storage** | 200 GB+ SSD |
| **OS** | Ubuntu 24.04 LTS |
| **Docker** | 24+ with Compose v2 |
| **NVIDIA Driver** | 550+ |
| **NVIDIA Container Toolkit** | Latest |

---

## 2. Architecture Overview

```
┌──────────────────────────────────────┐     ┌──────────────────────────────┐
│        APPLICATION SERVER (A)        │     │       GPU SERVER (B)         │
│                                      │     │                              │
│  ┌─────────┐  ┌──────────┐          │     │  ┌──────────────────────┐    │
│  │  Nginx   │  │ Frontend │          │     │  ┌──────────────────────────────────┐
│  │ (80/443) │◀─┤ Next.js  │          │     │  │     gpu-service (Port 8001)      │
│  └────┬─────┘  └──────────┘          │     │  │  ┌────────┐ ┌──────┐ ┌───────┐ │
│       │                              │     │  │  │ Whisper│ │BGE-M3│ │F5-TTS │ │
│  ┌────▼─────────────────────────┐    │     │  │  └────────┘ └──────┘ └───────┘ │
│  │      Backend (FastAPI)       │    │     │  │  POST /transcribe /embed /tts   │
│  │      Port 8000               │──────────▶│  │  POST /align /generate-narr.    │
│  │                              │    │     │  └──────────────┬───────────────────┘
│  │  ┌────────────────────────┐  │    │     │                 │ HTTP
│  │  │  API Routes            │  │    │     │  ┌──────────────▼───────────────────┐
│  │  │  Auth / Projects /     │  │    │     │  │  SGLang (Port 8000) — Qwen3-8B    │
│  │  │  Lectures / Files      │  │    │     │  │  Separate container, own CUDA   │
│  │  └────────────────────────┘  │    │     │  └──────────────────────────────────┘
│  │                              │    │     │
│  │  ┌────────────────────────┐  │    │     │
│  │  │  Pipeline Stages       │  │    │     │
│  │  │  1. Extract Audio      │  │    │     │
│  │  │  3. Parse PPTX         │  │    │     │
│  │  │  8. Embed PPTX         │  │    │     │
│  │  └────────────────────────┘  │    │     │
│  │                              │    │     │
│  │  ┌────────────────────────┐  │    │     │
│  │  │  Celery Worker         │  │    │     │
│  │  │  (background tasks)    │  │    │     │
│  │  └────────────────────────┘  │    │     │
│  │                              │    │     └──────────────────────────────┘
│  │  ┌─────────┐  ┌─────────┐   │    │
│  │  │PostgreSQL│  │  Redis  │   │    │
│  │  │ Port 5432│  │ Port 6379│  │    │
│  │  └─────────┘  └─────────┘   │    │
│  └──────────────────────────────┘    │
└──────────────────────────────────────┘
```

### Server Responsibilities

| Server | Responsibilities |
|--------|-----------------|
| **Application (A)** | Next.js frontend, FastAPI backend, PostgreSQL, Redis, file storage, PowerPoint parsing, Celery worker, pipeline orchestration, progress tracking |
| **GPU (B)** | Faster-Whisper transcription, BGE-M3 embeddings, Qwen via SGLang, F5-TTS speech synthesis. No user data stored. |

### Communication

| From | To | Protocol | Purpose |
|------|----|----------|---------|
| Browser | Nginx → Frontend/Backend | HTTP/HTTPS, WSS | UI, API, WebSocket |
| Backend | GPU Server Services | HTTP REST | Transcribe, embed, narrate, TTS |
| Celery Worker | GPU Server Services | HTTP REST | Async pipeline execution |
| Backend | PostgreSQL | SQLAlchemy async | Data persistence |
| Backend/Celery | Redis | TCP | Job queue, pub/sub, cache |

---

## 3. Quick Start (Development)

### 3.1 One-Command Setup

```bash
# Clone the repository
git clone <repo-url>
cd ai-lecture-narrator

# Copy environment file
cp .env.example .env
# Edit .env with your settings (see Section 11)

# Backend setup
cd backend
pip install -r requirements.txt
cd ..

# Frontend setup
cd frontend
npm install
cd ..

# Start databases (using Docker)
cd infrastructure
docker compose up -d postgres redis
cd ..

# Run migrations
cd backend
alembic upgrade head
cd ..

# Start backend
cd backend
uvicorn main:app --reload --port 8000
# In another terminal:

# Start frontend
cd frontend
npm run dev
```

### 3.2 Verify Installation

```bash
# Check backend health
curl http://localhost:8000/api/v1/health

# Check frontend
open http://localhost:3000

# Register a user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test@1234","full_name":"Test User"}'
```

---

## 4. Backend Setup

### 4.1 Prerequisites

```bash
# Python 3.11+
python --version  # Must be 3.11+

# FFmpeg (required for audio extraction)
# Ubuntu/Debian:
sudo apt-get install ffmpeg

# macOS:
brew install ffmpeg

# Windows (using winget):
winget install FFmpeg
# Or download from https://ffmpeg.org/download.html

# Verify:
ffmpeg -version
ffprobe -version
```

### 4.2 Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**All 26 dependencies:**
```
fastapi>=0.115.0          # Web framework
uvicorn[standard]>=0.30.0 # ASGI server
sqlalchemy>=2.0.35        # ORM
asyncpg>=0.30.0           # Async PostgreSQL driver
alembic>=1.13.0           # Database migrations
pydantic>=2.9.0           # Data validation
pydantic-settings>=2.5.0  # Configuration
bcrypt>=4.0.0             # Password hashing
python-multipart>=0.0.12  # File uploads
redis>=5.2.0              # Redis client
celery[redis]>=5.4.0      # Async task queue
aiofiles>=24.1.0          # Async file I/O
python-pptx>=1.0.2        # PowerPoint processing
httpx>=0.27.0             # HTTP client
tenacity>=9.0.0           # Retry logic
structlog>=24.4.0         # Structured logging
PyJWT>=2.9.0              # JWT tokens
aiosqlite>=0.20.0         # SQLite for tests
numpy>=1.24.0             # Numerical computing
# Dev dependencies
pytest, pytest-asyncio, pytest-cov, ruff
```

### 4.3 Environment Configuration

```bash
cp .env.example .env
```

Key settings to configure (see Section 11 for full reference):

```bash
# Critical: Change these secrets
SECRET_KEY=<generate-a-random-64-char-string>
JWT_SECRET_KEY=<generate-another-random-string>
DB_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>
AI_API_KEY=<api-key-for-gpu-server>

# For development without GPU server, set AI URLs to localhost:
AI_TRANSCRIPTION_URL=http://localhost:8001
AI_LLM_URL=http://localhost:8002
AI_TTS_URL=http://localhost:8003
```

### 4.4 Project Structure

```
backend/
├── alembic.ini                  # Alembic configuration
├── alembic/                     # Migration scripts
│   ├── versions/
│   │   └── 0001_initial_schema.py
│   └── env.py
├── src/
│   ├── __init__.py
│   ├── api/                    # Interface Adapters (FastAPI)
│   │   ├── routes/
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── lectures.py
│   │   │   ├── voice.py
│   │   │   ├── files.py
│   │   │   └── health.py
│   │   ├── dependencies/
│   │   │   ├── auth.py
│   │   │   ├── providers.py
│   │   │   └── validation.py
│   │   ├── middleware/
│   │   │   ├── cors.py
│   │   │   ├── auth.py
│   │   │   └── logging.py
│   │   └── errors/
│   │       └── handlers.py
│   ├── core/                   # Business Logic
│   │   ├── domain/
│   │   │   ├── entities/
│   │   │   ├── value_objects.py
│   │   │   └── events.py
│   │   ├── use_cases/
│   │   │   ├── auth/           # register, login, refresh
│   │   │   ├── project/        # CRUD
│   │   │   ├── lecture/        # upload, get, status
│   │   │   └── voice/          # CRUD
│   │   ├── dto/                # Pydantic schemas
│   │   └── ports/              # Interfaces
│   │       ├── storage.py
│   │       └── ai.py
│   ├── infrastructure/         # Adapter implementations
│   │   ├── db/
│   │   │   ├── models/         # 9 SQLAlchemy models
│   │   │   ├── repositories/   # Generic + 7 concrete repos
│   │   │   └── session.py
│   │   ├── auth/
│   │   │   ├── jwt.py
│   │   │   └── password.py
│   │   ├── storage/
│   │   │   └── local_storage.py
│   │   └── ai_client/          # HTTP clients to GPU server
│   │       ├── base.py
│   │       ├── transcription.py
│   │       ├── embedding.py
│   │       ├── llm.py
│   │       └── tts.py
│   ├── worker/                 # Background processing
│   │   ├── celery_app.py
│   │   ├── tasks/
│   │   │   └── lecture_tasks.py
│   │   └── pipeline/           # 8 pipeline stages
│   │       ├── extract_audio.py
│   │       ├── transcribe.py
│   │       ├── parse_pptx.py
│   │       ├── generate_embeddings.py
│   │       ├── align_transcript.py
│   │       ├── generate_narration.py
│   │       ├── generate_tts.py
│   │       ├── embed_narration.py
│   │       └── orchestrator.py
│   └── config/
│       ├── settings.py
│       └── logging.py
├── main.py                     # FastAPI app factory
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

### 4.5 Running the Backend

```bash
# Development (hot reload)
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# With Docker
docker compose -f infrastructure/docker-compose.yml up -d backend
```

The API will be available at `http://localhost:8000`.
Interactive docs at `http://localhost:8000/docs`.

---

## 5. Frontend Setup

### 5.1 Install Dependencies

```bash
cd frontend
npm install
```

**Key dependencies:**
```
next@14           # React framework
react@18          # UI library
lucide-react      # Icons
zustand           # State management
axios             # HTTP client
clsx              # Classnames
tailwind-merge    # Tailwind class merging
class-variance-authority  # Component variants
```

### 5.2 Environment

Create `frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 5.3 Running the Frontend

```bash
# Development
cd frontend
npm run dev

# Production build
npm run build
npm start

# With Docker
docker compose -f infrastructure/docker-compose.yml up -d frontend
```

The frontend will be available at `http://localhost:3000`.

### 5.4 Frontend Pages

| Route | Page | Description |
|-------|------|-------------|
| `/auth/login` | Login | Email + password authentication |
| `/auth/register` | Register | Create new account |
| `/dashboard` | Dashboard | Project stats, list, create |
| `/projects/[id]` | Project Detail | Lectures, settings, delete |
| `/lectures/upload` | Upload | Lecture file upload form |
| `/voice-profiles` | Voice Profiles | Voice cloning management |

---

## 6. Database Setup

### 6.1 PostgreSQL (Direct)

```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql

# Create database and user
sudo -u postgres psql
CREATE DATABASE lecture_narrator;
CREATE USER app_user WITH PASSWORD 'devpassword';
GRANT ALL PRIVILEGES ON DATABASE lecture_narrator TO app_user;
\q

# macOS (Homebrew)
brew install postgresql@16
brew services start postgresql@16
createdb lecture_narrator
createuser app_user -P  # Enter password when prompted
```

### 6.2 PostgreSQL (Docker — Recommended for Development)

```bash
cd infrastructure
docker compose up -d postgres

# Verify
docker compose exec postgres pg_isready -U app_user -d lecture_narrator
```

### 6.3 Redis (Docker — Recommended)

```bash
cd infrastructure
docker compose up -d redis

# Verify
docker compose exec redis redis-cli ping
# Should return: PONG
```

### 6.4 Run Migrations

```bash
cd backend
alembic upgrade head

# Verify tables exist
alembic current

# To create a new migration after model changes:
alembic revision --autogenerate -m "description"
alembic upgrade head

# To rollback:
alembic downgrade -1
```

**Tables created by the initial migration:**
- `users` — User accounts
- `projects` — Lecture projects
- `voice_profiles` — Voice cloning profiles
- `lectures` — Uploaded lecture records
- `slides` — Extracted slide content
- `transcript_segments` — Timestamped transcript
- `narrations` — AI-generated narration scripts + audio
- `jobs` — Pipeline job tracking
- `files` — File metadata + audit trail

### 6.5 Connection Strings

```bash
# Local PostgreSQL
DATABASE_URL=postgresql+asyncpg://app_user:devpassword@localhost:5432/lecture_narrator

# Docker PostgreSQL
DATABASE_URL=postgresql+asyncpg://app_user:devpassword@postgres:5432/lecture_narrator

# Local Redis
REDIS_URL=redis://:devpassword@localhost:6379/0
REDIS_RESULT_URL=redis://:devpassword@localhost:6379/1
```

---

## 7. GPU Server Setup

The GPU server runs on **Machine B** and provides all AI inference capabilities.
It is a separate machine with an NVIDIA GPU and never stores user data.

### 7.1 Prerequisites

```bash
# NVIDIA Driver 550+
nvidia-smi

# NVIDIA Container Toolkit
# Ubuntu/Debian:
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 7.2 GPU Server Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    GPU Server (Machine B)                     │
│                                                              │
│  ┌──────────────┐                                            │
│  │  SGLang         │  Port 8000                                │
│  │  (Qwen3-8B)  │  GPU: ~16GB VRAM                          │
│  │  OpenAI API   │                                            │
│  └──────┬───────┘                                            │
│         │ HTTP                                               │
│  ┌──────▼───────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  LLM Service  │  │Transcription │  │  TTS Service     │   │
│  │  Port 8002    │  │Port 8001     │  │  Port 8003       │   │
│  │  (orchestrates│  │(Whisper)     │  │  (F5-TTS)        │   │
│  │   prompts)    │  │GPU: ~4GB     │  │  GPU: ~4GB       │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│                                                              │
│  ┌──────────────────┐                                        │
│  │  Embedding Svc   │  Port 8004                             │
│  │  (BGE-M3)        │  GPU: ~2GB                             │
│  └──────────────────┘                                        │
└──────────────────────────────────────────────────────────────┘
```

**GPU Memory Budget (Blackwell 24GB):**

All non-SGLang models share a single container and are loaded once at startup.

| Container | Models | VRAM | Notes |
|-----------|--------|------|-------|
| `sglang` | Qwen3-8B (BF16) | ~16GB | Always loaded, separate CUDA context |
| `gpu-service` | Whisper + BGE-M3 + F5-TTS | ~10GB | Loaded once at startup, shared container |

SGLang runs in its own container with its own CUDA context. The unified `gpu-service`
container loads Whisper (~4GB), BGE-M3 (~2GB), and F5-TTS (~4GB) simultaneously
at startup, sharing the remaining ~8GB of VRAM effectively.

### 7.3 Start GPU Server Services

```bash
# On the GPU server, from the project root:
cd infrastructure

# Start all GPU services
docker compose -f docker-compose.ai.yml up -d

# Verify the unified service is healthy
curl http://localhost:8001/ai/v1/health
```

### 7.4 Unified GPU Service (Direct Execution)

The unified GPU service runs all models in a single container. For development without Docker:

```bash
# Install dependencies
cd ai-server/service
pip install -r requirements.txt

# Install ML frameworks (PyTorch + models)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install faster-whisper sentence-transformers

# Start the unified GPU service
uvicorn src.main:app --host 0.0.0.0 --port 8001

# In another terminal, start SGLang for Qwen:
docker run --gpus all -p 30000:30000 \
  lmsysorg/sglang:latest \
  python3 -m sglang.launch_server \
  --model-path Qwen/Qwen3-8B \
  --host 0.0.0.0 \
  --port 30000 \
  --mem-fraction-static 0.90 \
  --context-length 32768

# Or install directly (no Docker):
pip install sglang[all]
python3 -m sglang.launch_server --model-path Qwen/Qwen3-8B --port 30000
```

**Test all endpoints:**

```bash
# Health
curl http://localhost:8001/ai/v1/health

# Transcription
curl -X POST http://localhost:8001/ai/v1/transcribe \
  -F "audio_file=@test.wav" -F "vad_filter=true"

# Embedding
curl -X POST http://localhost:8001/ai/v1/embed \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Hello world", "Test embedding"]}'

# Embedding dimensions
curl http://localhost:8001/ai/v1/dimensions

# Narration
curl -X POST http://localhost:8001/ai/v1/generate-narration \
  -H "Content-Type: application/json" \
  -d '{
    "lecture_title": "Physics 101",
    "slides": [{
      "slide_number": 1,
      "raw_text": "Thermodynamics: First Law",
      "notes": "Explain energy conservation"
    }]
  }'

# TTS
curl -X POST http://localhost:8001/ai/v1/tts \
  -F "text=Hello, welcome to this lecture on thermodynamics." \
  -o output.wav
```

---

## 8. Running the Pipeline

### 8.1 Manual Pipeline Execution

The pipeline runs automatically when a lecture is uploaded.
You can also trigger it manually:

```bash
# 1. Register and login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test@1234"}' | \
  python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Create a project
PROJECT_ID=$(curl -s -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test Project"}' | \
  python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 3. Upload a lecture (video + slides)
curl -X POST http://localhost:8000/api/v1/lectures/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "project_id=$PROJECT_ID" \
  -F "title=Test Lecture" \
  -F "video_file=@lecture.mp4" \
  -F "pptx_file=@slides.pptx"

# 4. Check processing status
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/lectures/{lecture_id}/status

# 5. Get results when complete
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/lectures/{lecture_id}
```

### 8.2 Pipeline Stages

When a lecture is uploaded, the Celery worker executes these stages in order:

| # | Stage | Server | Description | Status Updates |
|---|-------|--------|-------------|----------------|
| 1 | Extract Audio | Backend | FFmpeg extracts 16kHz mono WAV | 10% |
| 2 | Transcribe | GPU | Faster-Whisper generates timestamped transcript | 35% |
| 3 | Parse PPTX | Backend | python-pptx extracts slide content | 45% |
| 4 | Embeddings | GPU | BGE-M3 generates vectors for text | 50% |
| 5 | Align | GPU | Embedding search + LLM verify + temporal constraints | 65% |
| 6 | Narrate | GPU | Qwen generates per-slide narration scripts | 80% |
| 7 | TTS | GPU | F5-TTS generates per-slide audio files | 95% |
| 8 | Embed PPTX | Backend | python-pptx embeds audio into PowerPoint | 100% |

### 8.3 Celery Worker

```bash
# Start the Celery worker (for pipeline processing)
cd backend
celery -A src.worker.celery_app worker \
  -Q default,audio,transcription,llm,tts,pptx,priority_high \
  -l INFO \
  --concurrency=2

# In production, use supervisor or systemd to manage:
celery -A src.worker.celery_app multi start worker \
  -Q default,audio,transcription,llm,tts,pptx,priority_high \
  -l INFO \
  --concurrency=4 \
  --pidfile=/var/run/celery/%n.pid \
  --logfile=/var/log/celery/%n%I.log

# Monitor:
celery -A src.worker.celery_app flower
```

### 8.4 Progress Tracking

Progress is computed as a weighted sum of completed stages:

```python
STAGE_WEIGHTS = {
    "extract_audio": 0.10,
    "transcribe": 0.25,
    "parse_pptx": 0.10,
    "generate_embeddings": 0.05,
    "align_transcript": 0.15,
    "generate_narration": 0.15,
    "generate_tts": 0.15,
    "embed_narration": 0.05,
}
```

Track progress via:

```bash
# REST API:
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/lectures/{id}/status

# WebSocket:
# Connect to ws://localhost:8000/api/v1/ws/lecture/{id}/progress
```

---

## 9. Running Tests

### 9.1 Backend Tests

```bash
cd backend

# Run all tests
pytest -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests (requires database)
pytest tests/integration/ -v

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_auth.py -v

# Run specific test
pytest tests/unit/test_auth.py::TestJWT::test_create_and_decode_access_token -v
```

### 9.2 Test Categories

| Test File | Type | Description |
|-----------|------|-------------|
| `tests/unit/test_auth.py` | Unit | JWT creation/decoding, password hashing |
| `tests/unit/test_entities.py` | Unit | Domain value objects validation |
| `tests/integration/test_health.py` | Integration | Health endpoint |
| `tests/integration/test_auth_api.py` | Integration | Auth flow (register, login, refresh) |
| `tests/integration/test_project_api.py` | Integration | Project CRUD |
| `tests/integration/test_storage.py` | Integration | File storage operations |

### 9.3 Frontend Tests (Future)

```bash
cd frontend
npm test          # When tests are added
npm run lint      # Lint check
```

### 9.4 Pipeline Stage Tests (Manual)

```bash
# Test audio extraction (requires FFmpeg)
cd backend
python -c "
from src.worker.pipeline.extract_audio import extract_audio
result = extract_audio('path/to/test_video.mp4')
print(f'Extracted: {result.audio_path}, duration={result.duration_seconds}s')
"

# Test PPTX parsing
python -c "
from src.worker.pipeline.parse_pptx import parse_pptx
result = parse_pptx('path/to/test.pptx')
print(f'Parsed: {result.total_slides} slides')
"
```

---

## 10. Docker Deployment

### 10.1 Application Server (Machine A)

```bash
cd infrastructure

# Start all web services
docker compose -f docker-compose.yml up -d

# Check status
docker compose -f docker-compose.yml ps

# View logs
docker compose -f docker-compose.yml logs -f

# Run database migrations
docker compose -f docker-compose.yml exec backend alembic upgrade head
```

**Services started:**

| Service | Docker Image | Port |
|---------|-------------|------|
| nginx | nginx:alpine | 80 |
| frontend | Custom (Node.js) | 3000 |
| backend | Custom (Python) | 8000 |
| celery-worker | Custom (Python) | — |
| postgres | postgres:16-alpine | 5432 |
| redis | redis:7-alpine | 6379 |

### 10.2 GPU Server (Machine B)

```bash
# On the GPU server:
cd infrastructure

# Start AI services
docker compose -f docker-compose.ai.yml up -d

# Check GPU availability
docker compose -f docker-compose.ai.yml logs -f transcription

# Verify all services
curl http://localhost:8001/ai/v1/health   # Unified GPU service (all models)
```

**AI Services:**

| Service | GPU | Port | Models |
|---------|-----|------|--------|
| `sglang` | Required | 30000 | Qwen/Qwen3-8B |
| `gpu-service` | Required | 8001 | Whisper large-v3 + BGE-M3 + F5-TTS |

### 10.3 Makefile Commands

```bash
# Available commands (run from infrastructure/):
make up         # docker compose up -d
make down       # docker compose down
make build      # docker compose build
make logs       # docker compose logs -f
make migrate    # alembic upgrade head
make test       # pytest in backend container
make psql       # PostgreSQL CLI
make redis-cli  # Redis CLI
make clean      # docker compose down -v (destroys volumes)
```

### 10.4 Production Considerations

```bash
# Use a proper .env file with strong secrets
# Enable DEBUG=false
# Set up SSL certificates (Let's Encrypt)
# Configure proper logging aggregation
# Set up database backups
# Configure monitoring (Prometheus + Grafana)

# Example production deployment:
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

---

## 11. Configuration Reference

### 11.1 Environment Variables (`.env`)

```bash
# =============================================================================
# APPLICATION
# =============================================================================
APP_NAME="AI Lecture Narrator"
APP_VERSION=1.0.0
ENVIRONMENT=development        # development | staging | production
DEBUG=true                     # Enables hot reload, debug endpoints
SECRET_KEY=<64-char-random>    # Application secret key

# =============================================================================
# DATABASE
# =============================================================================
DATABASE_URL=postgresql+asyncpg://app_user:password@localhost:5432/lecture_narrator
DB_PASSWORD=<password>          # PostgreSQL password
DB_POOL_SIZE=10                 # Connection pool size
DB_MAX_OVERFLOW=20              # Max overflow connections

# =============================================================================
# REDIS
# =============================================================================
REDIS_URL=redis://:password@localhost:6379/0
REDIS_RESULT_URL=redis://:password@localhost:6379/1
REDIS_PASSWORD=<password>

# =============================================================================
# JWT AUTHENTICATION
# =============================================================================
JWT_SECRET_KEY=<64-char-random> # HS256 signing key
JWT_ACCESS_EXPIRE_MINUTES=60    # Access token lifetime
JWT_REFRESH_EXPIRE_DAYS=30      # Refresh token lifetime

# =============================================================================
# AI GPU SERVER (Machine B) — Unified Service
# =============================================================================
AI_SERVICE_URL=http://gpu-service:8001   # Single endpoint for all models
AI_API_KEY=<api-key>                     # Shared secret for GPU server auth

# =============================================================================
# STORAGE
# =============================================================================
STORAGE_BACKEND=local           # local | s3 (future)
STORAGE_ROOT=./storage          # Local storage root path

# =============================================================================
# FILE UPLOAD LIMITS
# =============================================================================
MAX_VIDEO_SIZE_BYTES=2147483648    # 2 GB
MAX_AUDIO_SIZE_BYTES=524288000     # 500 MB
MAX_PPTX_SIZE_BYTES=209715200      # 200 MB

# =============================================================================
# RATE LIMITING
# =============================================================================
RATE_LIMIT_REQUESTS=100            # Max requests per window
RATE_LIMIT_WINDOW_SECONDS=60       # Window duration

# =============================================================================
# CORS
# =============================================================================
CORS_ORIGINS=["http://localhost:3000"]  # Allowed origins

# =============================================================================
# AI MODEL CONFIGURATION
# =============================================================================
WHISPER_MODEL_SIZE=large-v3
LLM_MODEL=Qwen/Qwen3-8B
TTS_SAMPLE_RATE=24000

# =============================================================================
# HUGGING FACE (for model downloads)
# =============================================================================
HF_TOKEN=                        # Optional: for gated models
```

### 11.2 Frontend Environment (`frontend/.env.local`)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 12. Troubleshooting

### 12.1 Common Issues

#### Database Connection Failed

```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Check credentials in .env
# Try connecting manually:
psql -h localhost -U app_user -d lecture_narrator

# With Docker:
docker compose -f infrastructure/docker-compose.yml logs postgres
```

#### Alembic Migration Fails

```bash
# Check migration status
alembic current

# View migration SQL (without executing)
alembic upgrade head --sql

# If migration state is inconsistent:
# Option 1: Stamp to a known revision
alembic stamp 0001

# Option 2: Revert and re-apply
alembic downgrade base
alembic upgrade head
```

#### FFmpeg Not Found

```bash
# Install FFmpeg
# Ubuntu:
sudo apt-get install ffmpeg

# macOS:
brew install ffmpeg

# Windows:
winget install FFmpeg
# Or download from https://ffmpeg.org/download.html

# Verify:
ffmpeg -version
ffprobe -version
```

#### GPU Server Unreachable

```bash
# Check network connectivity
ping <gpu-server-ip>

# Check service health
curl http://<gpu-server>:8001/ai/v1/health
curl http://<gpu-server>:8002/ai/v1/health

# Check if GPU is available (on GPU server):
nvidia-smi

# Check Docker containers (on GPU server):
docker compose -f infrastructure/docker-compose.ai.yml ps
docker compose -f infrastructure/docker-compose.ai.yml logs
```

#### Celery Worker Not Processing Tasks

```bash
# Check Redis is running
redis-cli -a <password> ping

# Check worker logs
celery -A src.worker.celery_app status

# Start worker with debug logging
celery -A src.worker.celery_app worker -l DEBUG

# Check queue contents
redis-cli -a <password> LLEN celery
```

#### Frontend Build Fails

```bash
# Clear Next.js cache
rm -rf .next

# Clear npm cache
npm cache clean --force

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Rebuild
npm run build
```

#### Pipeline Stage Fails

```bash
# Check the lecture status
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/lectures/{id}/status

# Check Celery task logs
docker compose -f infrastructure/docker-compose.yml logs celery-worker

# Check backend logs
docker compose -f infrastructure/docker-compose.yml logs backend

# Common errors:
# - "FFmpeg not found": Install FFmpeg
# - "GPU service unreachable": Check GPU server
# - "Audio file not found": Check storage paths
# - "No audio stream": Video has no audio track
```

### 12.2 Debugging Tips

```bash
# Enable debug logging
export DEBUG=true

# Check all service health
curl http://localhost:8000/api/v1/health

# Check database connection from backend
docker compose exec backend python -c "
from src.infrastructure.db.session import get_session
import asyncio
async def check():
    async for session in get_session():
        result = await session.execute('SELECT 1')
        print(f'DB connected: {result.scalar()}')
asyncio.run(check())
"

# Test GPU service connectivity from backend
docker compose exec backend python -c "
import httpx
resp = httpx.get('http://gpu-service:8001/ai/v1/health')
print(f'GPU Service: {resp.json()}')
"

# Check stored files
ls -la ./storage/
```

### 12.3 Getting Help

If you encounter issues not covered here:

1. Check the logs: `docker compose logs -f [service-name]`
2. Run diagnostics: `python -m src.config.settings` (validates config)
3. Check database state: `psql -U app_user -d lecture_narrator -c "\dt"`
4. Verify GPU availability: `nvidia-smi` (on GPU server)
5. Ensure all services are running: `docker compose ps`

---

## Quick Reference Card

```bash
# ─── Backend ───
cd backend && uvicorn main:app --reload          # Start server
cd backend && pytest -v                           # Run tests
cd backend && alembic upgrade head                # Run migrations

# ─── Frontend ───
cd frontend && npm run dev                        # Start dev server
cd frontend && npm run build                      # Production build

# ─── Infrastructure ───
cd infrastructure && docker compose up -d          # Start all services
cd infrastructure && docker compose down           # Stop all services
cd infrastructure && make migrate                  # Run DB migrations
cd infrastructure && make test                     # Run backend tests

# ─── GPU Server (Machine B) ───
cd infrastructure && docker compose -f docker-compose.ai.yml up -d

# ─── Celery Worker ───
cd backend && celery -A src.worker.celery_app worker -l INFO
```
