# AI Lecture Narration Generator — Architecture Blueprint

> **Author:** Principal Software Architect  
> **Status:** Draft v1.0  
> **Last Updated:** 2026-07-02

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Low-Level Architecture](#2-low-level-architecture)
3. [Folder Structure](#3-folder-structure)
4. [Microservice Architecture](#4-microservice-architecture)
5. [Database Schema](#5-database-schema)
6. [Redis Queue Design](#6-redis-queue-design)
7. [API Specifications](#7-api-specifications)
8. [Internal AI Pipeline](#8-internal-ai-pipeline)
9. [Sequence Diagrams](#9-sequence-diagrams)
10. [PowerPoint Parsing Strategy](#10-powerpoint-parsing-strategy)
11. [Transcript-to-Slide Alignment Algorithm](#11-transcript-to-slide-alignment-algorithm)
12. [Prompt Engineering](#12-prompt-engineering)
13. [Voice Cloning Flow](#13-voice-cloning-flow)
14. [File Storage Layout](#14-file-storage-layout)
15. [Docker Compose Architecture](#15-docker-compose-architecture)
16. [Deployment Guide](#16-deployment-guide)
17. [Security](#17-security)
18. [Logging](#18-logging)
19. [Monitoring](#19-monitoring)
20. [Configuration Management](#20-configuration-management)
21. [Environment Variables](#21-environment-variables)
22. [Testing Strategy](#22-testing-strategy)
23. [Scalability Plan](#23-scalability-plan)
24. [Future Architecture](#24-future-architecture)
25. [Development Roadmap](#25-development-roadmap)

---

## 1. High-Level Architecture

### 1.1 System Boundary

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INTERNET / LAN                              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
        ┌───────────────────────┐       ┌───────────────────────┐
        │     MACHINE A         │       │     MACHINE B         │
        │   (Web Server)        │       │    (AI Server)        │
        │                       │       │                       │
        │  Intel i7-14700       │       │   Blackwell GPU       │
        │  8 GB RAM             │       │                       │
        │                       │       │  ┌─────────────────┐  │
        │  ┌─────────────────┐  │       │  │ Transcription   │  │
        │  │ Nginx           │──┼───────┼─▶│ Service          │  │
        │  │ (Reverse Proxy) │  │       │  │ (Faster-Whisper) │  │
        │  └────────┬────────┘  │       │  └─────────────────┘  │
        │           │           │       │                       │
        │  ┌────────▼────────┐  │       │  ┌─────────────────┐  │
        │  │ Next.js         │  │       │  │ LLM Service     │  │
        │  │ (Frontend)      │  │       │  │ (Qwen3 via vLLM)│  │
        │  └────────┬────────┘  │       │  └─────────────────┘  │
        │           │           │       │                       │
        │  ┌────────▼────────┐  │       │  ┌─────────────────┐  │
        │  │ FastAPI         │  │       │  │ TTS Service     │  │
        │  │ (Backend API)   │──┼───────┼─▶│ (F5-TTS)        │  │
        │  └────────┬────────┘  │       │  └─────────────────┘  │
        │           │           │       │                       │
        │  ┌────────▼────────┐  │       └───────────────────────┘
        │  │ PostgreSQL      │  │
        │  └─────────────────┘  │
        │                       │
        │  ┌─────────────────┐  │
        │  │ Redis + Celery  │  │
        │  └─────────────────┘  │
        │                       │
        │  ┌─────────────────┐  │
        │  │ Local Storage   │  │
        │  └─────────────────┘  │
        └───────────────────────┘
```

### 1.2 Communication Flow

| Direction | Protocol | Purpose |
|-----------|----------|---------|
| Browser → Nginx → Next.js | HTTPS | Static assets, SSR pages |
| Browser → Nginx → FastAPI | HTTPS REST | CRUD operations, file upload |
| Browser → Nginx → FastAPI | WSS | Live lecture recording |
| FastAPI → AI Server | HTTP REST | Transcribe, narrate, TTS |
| FastAPI → Redis | TCP | Job queue, result backend |
| Celery Worker → AI Server | HTTP REST | Async job execution |
| FastAPI → PostgreSQL | TCP | Data persistence |

### 1.3 Architectural Decisions & Rationale

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Backend framework** | FastAPI | Async-native, WebSocket support, Pydantic validation, OpenAPI docs generation |
| **Frontend framework** | Next.js | SSR for dashboard performance, API routes for lightweight BFF, React ecosystem |
| **Database** | PostgreSQL | JSONB for flexible slide data, full-text search for transcript queries, mature tooling |
| **Queue** | Redis + Celery | Proven stack for Python async tasks, Redis also serves as cache and WebSocket pub/sub |
| **LLM serving** | vLLM | OpenAI-compatible API, PagedAttention for memory efficiency, continuous batching |
| **AI separation** | Independent services | Each model can be scaled, updated, or replaced independently |
| **Two-machine split** | Web vs AI | GPU costs isolated, web server stays lightweight, independent scaling |
| **Storage** | Local FS (MVP) | Simplifies initial deployment; S3 migration is a storage backend swap |
| **Containerization** | Docker Compose | Single-host orchestration for MVP; k8s migration is a config change |

---

## 2. Low-Level Architecture

### 2.1 Web Server (Machine A) — Layer Breakdown

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          NGINX (Reverse Proxy)                           │
│  /api/* → FastAPI  │  /ws/* → FastAPI  │  /* → Next.js                    │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────────┐
        │   Next.js App     │           │   FastAPI App         │
        │                   │           │                       │
        │  pages/           │           │  api/                  │
        │  components/      │           │  ├── routes/          │
        │  lib/             │           │  ├── dependencies/    │
        │  hooks/           │           │  ├── middleware/      │
        │  stores/          │           │  └── websockets/      │
        └───────────────────┘           │                       │
                                        │  core/                │
                                        │  ├── domain/          │
                                        │  ├── use_cases/       │
                                        │  ├── dto/             │
                                        │  └── ports/           │
                                        │                       │
                                        │  infrastructure/      │
                                        │  ├── db/              │
                                        │  ├── queue/           │
                                        │  ├── storage/         │
                                        │  ├── ai_client/       │
                                        │  └── pptx/            │
                                        │                       │
                                        │  config/              │
                                        │  worker/              │
                                        └───────────────────────┘
```

### 2.2 AI Server (Machine B) — Service Isolation

Each AI capability runs as an independent process/service:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            AI Server (Machine B)                          │
│                                                                          │
│  ┌─────────────────────┐   ┌─────────────────────┐   ┌───────────────┐   │
│  │ Transcription API   │   │ LLM API              │   │ TTS API       │   │
│  │ (FastAPI)           │   │ (FastAPI)            │   │ (FastAPI)     │   │
│  │                     │   │                      │   │               │   │
│  │ POST /transcribe    │   │ POST /generate-narra │   │ POST /tts     │   │
│  │ WS  /ws/transcribe  │   │ POST /align          │   │ POST /clone   │   │
│  │                     │   │ POST /analyze-slides  │   │               │   │
│  │ GPU: Required       │   │                      │   │ GPU: Required │   │
│  └─────────┬───────────┘   │ GPU: Required        │   └───────┬───────┘   │
│            │               └──────────┬───────────┘           │           │
│            ▼                          ▼                       ▼           │
│  ┌─────────────────┐       ┌─────────────────────┐   ┌─────────────────┐ │
│  │ Faster-Whisper   │       │ vLLM (Qwen3)        │   │ F5-TTS          │ │
│  │ (Model)          │       │ (OpenAI-compat API) │   │ (Model)         │ │
│  └─────────────────┘       └─────────────────────┘   └─────────────────┘ │
│                                                                          │
│  Models are loaded ONCE at service startup.                              │
│  Each service has its own health endpoint.                               │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Clean Architecture — Backend Package Structure

```
backend/
├── api/                    # Interface Adapters (FastAPI layer)
│   ├── routes/             # Route handlers (thin controllers)
│   ├── dependencies/       # FastAPI dependency injection
│   ├── middleware/         # Auth, logging, CORS
│   ├── websockets/         # WebSocket handlers
│   └── errors/             # Exception handlers
│
├── core/                   # Business Logic (Use Cases + Domain)
│   ├── domain/             # Enterprise business rules
│   │   ├── entities/       # User, Project, Lecture, Slide, Narration, Job
│   │   ├── value_objects/  # Email, FilePath, Transcript, Timestamp
│   │   └── events/         # Domain events (LectureUploaded, NarrationGenerated)
│   ├── use_cases/          # Application business rules
│   │   ├── auth/           # Register, Login, RefreshToken
│   │   ├── lecture/        # UploadLecture, StartProcessing, GetStatus
│   │   ├── narration/      # GenerateNarration, GetNarration
│   │   ├── voice/          # CloneVoice, GetVoiceProfiles
│   │   └── project/        # CRUD projects
│   ├── dto/                # Data Transfer Objects
│   └── ports/              # Interfaces (driven ports)
│       ├── repositories/   # UserRepository, LectureRepository, ...
│       ├── queue/          # JobQueue interface
│       ├── storage/        # FileStorage interface
│       ├── ai/             # AIService interface
│       └── pptx/           # PptxProcessor interface
│
├── infrastructure/         # Framework & Driver Implementations
│   ├── db/                 # SQLAlchemy models, migrations, repositories
│   ├── queue/              # Celery + Redis implementation
│   ├── storage/            # Local filesystem storage
│   ├── ai_client/          # HTTP clients to AI Server
│   ├── pptx/               # python-pptx wrapper
│   └── auth/               # JWT, password hashing
│
├── config/                 # Configuration
│   ├── settings.py         # Pydantic Settings
│   └── logging.py          # Logging configuration
│
├── worker/                 # Celery Worker
│   ├── tasks/              # Async task definitions
│   ├── pipeline/           # Processing pipeline orchestration
│   └── celery_app.py       # Celery application
│
├── main.py                 # FastAPI application entry
├── Dockerfile
└── requirements.txt
```

---

## 3. Folder Structure

### 3.1 Monorepo Root

```
ai-lecture-narrator/
│
├── frontend/                          # Next.js Application (Machine A)
│   ├── public/
│   │   ├── audio/                     # Recorded audio chunks (temp)
│   │   └── assets/                    # Static assets
│   ├── src/
│   │   ├── app/                       # App Router pages
│   │   │   ├── (auth)/                # Auth group
│   │   │   │   ├── login/
│   │   │   │   ├── register/
│   │   │   │   └── layout.tsx
│   │   │   ├── (dashboard)/           # Dashboard group
│   │   │   │   ├── dashboard/
│   │   │   │   ├── projects/
│   │   │   │   ├── lectures/
│   │   │   │   └── settings/
│   │   │   ├── lecture/               # Live lecture recording
│   │   │   │   └── [id]/
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx               # Landing page
│   │   ├── components/
│   │   │   ├── ui/                    # Shared UI primitives
│   │   │   ├── layout/                # Sidebar, header, etc.
│   │   │   ├── upload/                # File upload components
│   │   │   ├── lecture/               # Live lecture components
│   │   │   ├── player/                # Audio/video player
│   │   │   └── project/               # Project cards, lists
│   │   ├── lib/
│   │   │   ├── api/                   # API client (axios/fetch wrapper)
│   │   │   ├── ws/                    # WebSocket client
│   │   │   └── utils/                 # Utility functions
│   │   ├── hooks/
│   │   │   ├── useAudioRecorder.ts
│   │   │   ├── useWebSocket.ts
│   │   │   └── useLecture.ts
│   │   ├── stores/                    # Zustand stores
│   │   │   ├── authStore.ts
│   │   │   └── lectureStore.ts
│   │   └── types/                     # TypeScript types
│   ├── next.config.js
│   ├── package.json
│   └── Dockerfile
│
├── backend/                           # FastAPI Backend (Machine A)
│   ├── alembic/                       # Database migrations
│   │   ├── versions/
│   │   ├── env.py
│   │   └── alembic.ini
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── e2e/
│   │   └── conftest.py
│   ├── src/
│   │   ├── api/                       # Interface Adapters
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── users.py
│   │   │   │   ├── projects.py
│   │   │   │   ├── lectures.py
│   │   │   │   ├── narrations.py
│   │   │   │   ├── voice.py
│   │   │   │   ├── jobs.py
│   │   │   │   └── health.py
│   │   │   ├── dependencies/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py
│   │   │   │   └── db.py
│   │   │   ├── middleware/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── cors.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── logging.py
│   │   │   │   └── rate_limit.py
│   │   │   ├── websockets/
│   │   │   │   ├── __init__.py
│   │   │   │   └── lecture.py
│   │   │   └── errors/
│   │   │       ├── __init__.py
│   │   │       └── handlers.py
│   │   │
│   │   ├── core/                     # Business Logic
│   │   │   ├── domain/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── entities/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── user.py
│   │   │   │   │   ├── project.py
│   │   │   │   │   ├── lecture.py
│   │   │   │   │   ├── slide.py
│   │   │   │   │   ├── narration.py
│   │   │   │   │   ├── job.py
│   │   │   │   │   ├── voice_profile.py
│   │   │   │   │   └── file_record.py
│   │   │   │   ├── value_objects.py
│   │   │   │   └── events.py
│   │   │   ├── use_cases/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── register.py
│   │   │   │   │   ├── login.py
│   │   │   │   │   └── refresh_token.py
│   │   │   │   ├── lecture/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── upload_lecture.py
│   │   │   │   │   ├── get_lecture.py
│   │   │   │   │   └── start_processing.py
│   │   │   │   ├── narration/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── get_narration.py
│   │   │   │   ├── project/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── create_project.py
│   │   │   │   │   └── list_projects.py
│   │   │   │   └── voice/
│   │   │   │       ├── __init__.py
│   │   │   │       └── clone_voice.py
│   │   │   ├── dto/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── lecture.py
│   │   │   │   ├── project.py
│   │   │   │   └── narration.py
│   │   │   └── ports/
│   │   │       ├── __init__.py
│   │   │       ├── repositories.py
│   │   │       ├── queue.py
│   │   │       ├── storage.py
│   │   │       ├── ai.py
│   │   │       └── pptx.py
│   │   │
│   │   ├── infrastructure/
│   │   │   ├── db/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── models/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── base.py
│   │   │   │   │   ├── user.py
│   │   │   │   │   ├── project.py
│   │   │   │   │   ├── lecture.py
│   │   │   │   │   ├── slide.py
│   │   │   │   │   ├── narration.py
│   │   │   │   │   ├── job.py
│   │   │   │   │   ├── voice_profile.py
│   │   │   │   │   └── file_record.py
│   │   │   │   ├── repositories/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── base.py
│   │   │   │   │   ├── user_repo.py
│   │   │   │   │   ├── project_repo.py
│   │   │   │   │   ├── lecture_repo.py
│   │   │   │   │   ├── slide_repo.py
│   │   │   │   │   └── job_repo.py
│   │   │   │   └── session.py
│   │   │   ├── queue/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── celery_app.py
│   │   │   │   ├── celery_config.py
│   │   │   │   └── task_registry.py
│   │   │   ├── storage/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py
│   │   │   │   ├── local_storage.py
│   │   │   │   └── s3_storage.py           # Future
│   │   │   ├── ai_client/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py
│   │   │   │   ├── transcription.py
│   │   │   │   ├── llm.py
│   │   │   │   └── tts.py
│   │   │   ├── pptx/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── parser.py
│   │   │   │   ├── narration_embedder.py
│   │   │   │   └── models.py
│   │   │   └── auth/
│   │   │       ├── __init__.py
│   │   │       ├── jwt.py
│   │   │       └── password.py
│   │   │
│   │   ├── worker/
│   │   │   ├── __init__.py
│   │   │   ├── tasks/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── lecture_tasks.py
│   │   │   │   └── narration_tasks.py
│   │   │   └── pipeline/
│   │   │       ├── __init__.py
│   │   │       ├── extract_audio.py
│   │   │       ├── transcribe.py
│   │   │       ├── parse_pptx.py
│   │   │       ├── align_transcript.py
│   │   │       ├── generate_narration.py
│   │   │       ├── generate_tts.py
│   │   │       └── embed_narration.py
│   │   │
│   │   └── config/
│   │       ├── __init__.py
│   │       ├── settings.py
│   │       └── logging.py
│   │
│   ├── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
│
├── ai-server/                          # AI Server (Machine B)
│   ├── services/                       # Each is a separate container
│   │   ├── transcription/
│   │   │   ├── src/
│   │   │   │   ├── api/
│   │   │   │   │   ├── routes.py
│   │   │   │   │   └── websocket.py
│   │   │   │   ├── core/
│   │   │   │   │   └── transcriber.py
│   │   │   │   ├── config.py
│   │   │   │   └── main.py
│   │   │   ├── tests/
│   │   │   ├── Dockerfile
│   │   │   └── requirements.txt
│   │   │
│   │   ├── llm/
│   │   │   ├── src/
│   │   │   │   ├── api/
│   │   │   │   │   └── routes.py
│   │   │   │   ├── core/
│   │   │   │   │   ├── narration_generator.py
│   │   │   │   │   └── slide_aligner.py
│   │   │   │   ├── config.py
│   │   │   │   └── main.py
│   │   │   ├── tests/
│   │   │   ├── Dockerfile
│   │   │   └── requirements.txt
│   │   │
│   │   └── tts/
│   │       ├── src/
│   │       │   ├── api/
│   │       │   │   └── routes.py
│   │       │   ├── core/
│   │       │   │   ├── voice_cloner.py
│   │       │   │   └── speech_synthesizer.py
│   │       │   ├── config.py
│   │       │   └── main.py
│   │       ├── tests/
│   │       ├── Dockerfile
│   │       └── requirements.txt
│   │
│   ├── docker-compose.ai.yml           # AI-specific compose
│   └── .env.ai.example
│
├── infrastructure/                     # Deployment configs
│   ├── nginx/
│   │   ├── nginx.conf
│   │   └── sites/
│   ├── monitoring/
│   │   ├── prometheus.yml
│   │   ├── grafana/
│   │   └── loki/
│   ├── docker-compose.yml              # Root compose (all services)
│   ├── docker-compose.monitoring.yml
│   └── Makefile
│
├── docs/
│   ├── api/
│   ├── architecture/
│   └── guides/
│
├── scripts/
│   ├── setup.sh
│   ├── seed.py
│   └── healthcheck.sh
│
├── .env.example
├── .gitignore
├── ARCHITECTURE.md                     # This document
├── ROADMAP.md                          # Development roadmap
└── README.md
```

### 3.2 Key Design Decisions for Folder Structure

| Decision | Rationale |
|----------|-----------|
| **Clean Architecture layers** (`api/`, `core/`, `infrastructure/`) | Dependency inversion: domain never imports infrastructure. Swap DB/storage without touching business logic. |
| **AI server as independent services** | Each service loads only its model. OOM in TTS doesn't crash transcription. Independent scaling. |
| **Monorepo with clear boundaries** | Single repo for atomic commits across stack. Each service has its own Dockerfile for independent build. |
| **Worker separate from API** | Celery workers can scale independently. CPU-intensive PPT parsing doesn't block API requests. |
| **Ports/Adapters pattern** | All external dependencies behind interfaces. Swap S3 ←→ local storage with one implementation change. |

---

## 4. Microservice Architecture

### 4.1 Service Registry

| Service | Machine | Container | Base Image | GPU | Replicas (MVP) |
|---------|---------|-----------|------------|-----|-----------------|
| `nginx` | A | web | nginx:alpine | No | 1 |
| `frontend` | A | web | node:20-alpine | No | 1 |
| `backend` | A | web | python:3.12-slim | No | 1 |
| `celery-worker` | A | web | python:3.12-slim | No | 1 |
| `postgres` | A | web | postgres:16 | No | 1 |
| `redis` | A | web | redis:7-alpine | No | 1 |
| `transcription` | B | ai | python:3.12-slim | Yes | 1 |
| `llm` | B | ai | python:3.12-slim | Yes | 1 |
| `vllm` | B | ai | vllm/vllm-openai | Yes | 1 |
| `tts` | B | ai | python:3.12-slim | Yes | 1 |

### 4.2 Service Communication Matrix

```
                  ┌───────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┐
                  │ Front │ Back  │ Celery│ Post  │ Redis │ Trans │ LLM   │ vLLM  │ TTS   │
┌─────────────────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┤
│ Frontend        │   -   │  REST │   -   │   -   │   -   │   -   │   -   │   -   │   -   │
│                 │       │  WSS  │       │       │       │       │       │       │       │
├─────────────────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┤
│ Backend         │  REST │   -   │ Tasks │  SQL  │  Pub  │ REST  │   -   │   -   │ REST  │
│                 │       │       │       │       │ /Sub  │       │       │       │       │
├─────────────────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┤
│ Celery Worker   │   -   │   -   │   -   │  SQL  │Tasks  │ REST  │   -   │   -   │ REST  │
│                 │       │       │       │       │ /Res  │       │       │       │       │
├─────────────────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┤
│ Transcription   │   -   │   -   │   -   │   -   │   -   │   -   │   -   │   -   │   -   │
├─────────────────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┤
│ LLM             │   -   │   -   │   -   │   -   │   -   │   -   │   -   │OpenAI │   -   │
│                 │       │       │       │       │       │       │       │ API   │       │
├─────────────────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┤
│ TTS             │   -   │   -   │   -   │   -   │   -   │   -   │   -   │   -   │   -   │
└─────────────────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┘
```

**Key:** `-` = not applicable, `REST` = HTTP REST, `WSS` = WebSocket Secure, `SQL` = SQLAlchemy queries, `Tasks` = Celery task messages, `Pub/Sub` = Redis pub/sub

### 4.3 vLLM Integration Detail

The `llm` service does NOT load Qwen3 directly. It uses vLLM's OpenAI-compatible API:

```
┌──────────────┐          ┌──────────────┐          ┌─────────────────────┐
│  LLM Service  │ ──HTTP──▶│   vLLM        │          │  Qwen3-7B/14B       │
│  (orchestrates│          │  (OpenAI API) │ ──load──▶│  (loaded in VRAM)   │
│   prompts)    │          │               │          │                     │
└──────────────┘          └──────────────┘          └─────────────────────┘
```

- vLLM runs as a separate container.
- LLM service builds prompts, sends to `http://vllm:8000/v1/chat/completions`.
- LLM service parses structured JSON output, validates it, returns to caller.

---

## 5. Database Schema

### 5.1 Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────────┐
│    users     │       │    projects       │
│──────────────│       │──────────────────│
│ id (PK)      │◀──────│ id (PK)           │
│ email        │   1:N │ user_id (FK)      │
│ password_hash│       │ title             │
│ full_name    │       │ description       │
│ created_at   │       │ status            │
│ updated_at   │       │ created_at        │
└──────────────┘       │ updated_at        │
       │               └──────────────────┘
       │                       │
       │ 1:N                   │ 1:N
       ▼                       ▼
┌──────────────┐       ┌──────────────────┐
│voice_profiles│       │    lectures       │
│──────────────│       │──────────────────│
│ id (PK)      │◀──────│ id (PK)           │
│ user_id (FK) │   1:N │ project_id (FK)   │
│ name         │       │ title             │
│ audio_path   │       │ input_type        │  # video | audio | live
│ status       │       │ status            │  # pending | processing | done | error
│ created_at   │       │ video_path        │
└──────────────┘       │ audio_path        │
                       │ pptx_path         │
                       │ narrated_pptx_path│
                       │ duration_seconds  │
                       │ error_message     │
                       │ created_at        │
                       │ updated_at        │
                       └──────────┬───────┘
                                  │ 1:N
                                  ▼
                          ┌──────────────────┐        ┌──────────────────┐
                          │     slides        │        │   transcript_segments
                          │──────────────────│        │──────────────────│
                          │ id (PK)           │        │ id (PK)           │
                          │ lecture_id (FK)   │◀───────│ lecture_id (FK)   │
                          │ slide_number      │   1:N  │ slide_id (FK)     │
                          │ pptx_content      │        │ segment_number    │
                          │ notes             │        │ start_time        │
                          │ image_path        │        │ end_time          │
                          │ raw_text          │        │ text              │
                          │ created_at        │        │ confidence        │
                          └────────┬─────────┘        │ speaker           │
                                   │                   │ created_at        │
                                   │ 1:1               └──────────────────┘
                                   ▼
                          ┌──────────────────┐
                          │   narrations      │
                          │──────────────────│
                          │ id (PK)           │
                          │ slide_id (FK)     │
                          │ lecture_id (FK)   │
                          │ script_text       │
                          │ audio_path        │
                          │ duration_seconds  │
                          │ status            │
                          │ model_used        │
                          │ created_at        │
                          │ updated_at        │
                          └──────────────────┘

┌──────────────┐       ┌──────────────────┐
│     jobs      │       │    files          │
│──────────────│       │──────────────────│
│ id (PK)      │       │ id (PK)           │
│ lecture_id   │       │ user_id (FK)      │
│ job_type     │       │ lecture_id (FK)   │
│ status       │       │ file_type         │
│ progress     │       │ original_name     │
│ payload      │       │ storage_path      │
│ result       │       │ mime_type         │
│ error_message│       │ file_size_bytes   │
│ celery_id    │       │ checksum_sha256   │
│ created_at   │       │ created_at        │
│ started_at   │       └──────────────────┘
│ completed_at │
└──────────────┘
```

### 5.2 Table Definitions

#### `users`

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

#### `projects`

```sql
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_user_id ON projects(user_id);
```

#### `lectures`

```sql
CREATE TYPE input_type_enum AS ENUM ('video', 'audio', 'live');
CREATE TYPE lecture_status_enum AS ENUM ('pending', 'processing', 'completed', 'failed');

CREATE TABLE lectures (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title             VARCHAR(255) NOT NULL,
    input_type        input_type_enum NOT NULL,
    status            lecture_status_enum NOT NULL DEFAULT 'pending',
    video_path        TEXT,
    audio_path        TEXT,
    pptx_path         TEXT,
    narrated_pptx_path TEXT,
    duration_seconds  INTEGER,
    error_message     TEXT,
    voice_profile_id  UUID REFERENCES voice_profiles(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lectures_project_id ON lectures(project_id);
CREATE INDEX idx_lectures_status ON lectures(status);
```

#### `voice_profiles`

```sql
CREATE TYPE voice_status_enum AS ENUM ('pending', 'cloning', 'ready', 'failed');

CREATE TABLE voice_profiles (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name              VARCHAR(255) NOT NULL,
    sample_audio_path TEXT NOT NULL,
    status            voice_status_enum NOT NULL DEFAULT 'pending',
    speaker_id        VARCHAR(100),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_voice_profiles_user_id ON voice_profiles(user_id);
```

#### `slides`

```sql
CREATE TABLE slides (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lecture_id      UUID NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
    slide_number    INTEGER NOT NULL,
    raw_text        TEXT,
    notes           TEXT,
    image_path      TEXT,
    slide_layout    VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(lecture_id, slide_number)
);

CREATE INDEX idx_slides_lecture_id ON slides(lecture_id);
```

#### `transcript_segments`

```sql
CREATE TABLE transcript_segments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lecture_id      UUID NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
    slide_id        UUID REFERENCES slides(id) ON DELETE SET NULL,
    segment_number  INTEGER NOT NULL,
    start_time      REAL NOT NULL,
    end_time        REAL NOT NULL,
    text            TEXT NOT NULL,
    confidence      REAL,
    speaker         VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(lecture_id, segment_number)
);

CREATE INDEX idx_transcript_lecture_id ON transcript_segments(lecture_id);
CREATE INDEX idx_transcript_slide_id ON transcript_segments(slide_id);
```

#### `narrations`

```sql
CREATE TYPE narration_status_enum AS ENUM ('pending', 'generating', 'completed', 'failed');

CREATE TABLE narrations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slide_id          UUID NOT NULL REFERENCES slides(id) ON DELETE CASCADE,
    lecture_id        UUID NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
    script_text       TEXT NOT NULL,
    audio_path        TEXT,
    duration_seconds  REAL,
    status            narration_status_enum NOT NULL DEFAULT 'pending',
    model_used        VARCHAR(100),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_narrations_lecture_id ON narrations(lecture_id);
CREATE INDEX idx_narrations_slide_id ON narrations(slide_id);
```

#### `jobs`

```sql
CREATE TYPE job_type_enum AS ENUM (
    'extract_audio',
    'transcribe',
    'parse_pptx',
    'align_transcript',
    'generate_narration',
    'generate_tts',
    'embed_narration',
    'clone_voice',
    'full_pipeline'
);

CREATE TYPE job_status_enum AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled');

CREATE TABLE jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lecture_id      UUID NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
    job_type        job_type_enum NOT NULL,
    status          job_status_enum NOT NULL DEFAULT 'pending',
    progress        REAL DEFAULT 0.0,
    payload         JSONB,
    result          JSONB,
    error_message   TEXT,
    celery_id       VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_jobs_lecture_id ON jobs(lecture_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_celery_id ON jobs(celery_id);
```

#### `files`

```sql
CREATE TYPE file_type_enum AS ENUM (
    'video_source',
    'audio_source',
    'audio_extracted',
    'pptx_source',
    'slide_image',
    'voice_sample',
    'narration_audio',
    'narrated_pptx',
    'transcript',
    'temp'
);

CREATE TABLE files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lecture_id      UUID REFERENCES lectures(id) ON DELETE SET NULL,
    file_type       file_type_enum NOT NULL,
    original_name   VARCHAR(500) NOT NULL,
    storage_path    TEXT NOT NULL,
    mime_type       VARCHAR(100),
    file_size_bytes BIGINT,
    checksum_sha256 VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_files_lecture_id ON files(lecture_id);
CREATE INDEX idx_files_user_id ON files(user_id);
```

### 5.3 Schema Design Rationale

| Design Decision | Rationale |
|----------------|-----------|
| **UUID primary keys** | Avoid sequential ID enumeration. Merge-friendly for sharding. |
| **JSONB for job payload/result** | Flexible schema for different job types. No need for separate tables per job type. |
| **Separate `slides` table** | PPTX structure is rich (notes, images, layout). Keeping it normalized allows per-slide queries. |
| **`transcript_segments` with nullable `slide_id`** | Alignment can happen after ingestion. NULL means unaligned. |
| **`voice_profiles` separate from users** | A user can have multiple voice samples. Voice model is a reusable asset across lectures. |
| **`files` as a tracking table** | Full audit trail of all files. Enables cleanup, dedup, and future S3 migration. |
| **ENUM types** | Database-level constraint enforcement. Prevents invalid states. |
| **`TIMESTAMPTZ`** | Timezone-aware timestamps. Critical for globally distributed future. |

---

## 6. Redis Queue Design

### 6.1 Redis Usage

Redis serves three purposes:

| Purpose | Data Type | Key Pattern | TTL |
|---------|-----------|-------------|-----|
| **Celery Broker** | Standard | Celery-managed `_kombu` | — |
| **Celery Result Backend** | Standard | Celery-managed `celery-task-meta-*` | 7 days |
| **WebSocket Pub/Sub** | Pub/Sub channels | `lecture:{id}:transcript` | — |
| **Rate Limiting** | Sorted Set | `ratelimit:{endpoint}:{user_id}` | Window-based |
| **Cache** | String/JSON | `cache:{entity}:{id}` | Variable |

### 6.2 Queue Definitions

```python
# celery_app.py

from celery import Celery

celery_app = Celery(
    "lecture_narrator",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
)

# Queue configuration
celery_app.conf.task_queues = {
    "default": {                    # General tasks
        "exchange": "default",
        "routing_key": "default",
    },
    "audio": {                      # Audio extraction (CPU, fast)
        "exchange": "audio",
        "routing_key": "audio",
    },
    "transcription": {              # Transcription (GPU-bound, long)
        "exchange": "transcription",
        "routing_key": "transcription",
    },
    "llm": {                        # LLM inference (GPU-bound)
        "exchange": "llm",
        "routing_key": "llm",
    },
    "tts": {                        # TTS generation (GPU-bound)
        "exchange": "tts",
        "routing_key": "tts",
    },
    "pptx": {                       # PPTX parsing/embedding (CPU)
        "exchange": "pptx",
        "routing_key": "pptx",
    },
    "priority_high": {              # User-facing synchronous tasks
        "exchange": "priority_high",
        "routing_key": "priority_high",
    },
}
```

### 6.3 Pipeline Orchestration

The pipeline uses a **chain of tasks** connected via Celery's canvas:

```
                    ┌──────────────────────────────────────────────────┐
                    │              full_pipeline task                  │
                    │  Orchestrates the chain, updates job status      │
                    └──────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────────┐
        │  extract_audio     │           │  parse_pptx            │
        │  (audio queue)     │           │  (pptx queue)          │
        │  ffmpeg extraction │           │  python-pptx parse     │
        └─────────┬─────────┘           └───────────┬───────────┘
                  │                                 │
                  ▼                                 │
        ┌───────────────────┐                        │
        │  transcribe        │                        │
        │  (transcription)   │                        │
        │  POST /transcribe  │                        │
        └─────────┬─────────┘                        │
                  │                                  │
                  ▼                                  ▼
        ┌──────────────────────────────────────────────────────────┐
        │              align_transcript (llm queue)                  │
        │  POST /align — LLM aligns transcript segments to slides   │
        └─────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
        ┌──────────────────────────────────────────────────────────┐
        │              generate_narration (llm queue)               │
        │  POST /generate-narration — LLM writes per-slide script  │
        └─────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
        ┌──────────────────────────────────────────────────────────┐
        │              generate_tts (tts queue)                     │
        │  POST /tts — F5-TTS generates audio per slide            │
        └─────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
        ┌──────────────────────────────────────────────────────────┐
        │              embed_narration (pptx queue)                 │
        │  python-pptx embeds audio into slide timings             │
        └─────────────────────────┬────────────────────────────────┘
                                  │
                                  ▼
        ┌──────────────────────────────────────────────────────────┐
        │              Mark lecture completed                       │
        │  Update DB. Notify frontend via WebSocket.               │
        └──────────────────────────────────────────────────────────┘
```

### 6.4 Task Retry & Error Strategy

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    exponential_backoff=2,
    acks_late=True,
    reject_on_worker_lost=True,
    queue="transcription",
)
def transcribe_lecture(self, lecture_id: str, audio_path: str):
    try:
        # ... do work ...
        pass
    except AIServiceUnavailable as exc:
        raise self.retry(exc=exc)
    except InvalidAudioError:
        # Non-retryable, fail immediately
        update_job_status(lecture_id, "failed", error="Invalid audio")
    except Exception as exc:
        raise self.retry(exc=exc)
```

### 6.5 Job Progress Tracking

WebSocket channel: `ws://backend/ws/lecture/{lecture_id}/progress`

```json
{
    "type": "progress",
    "lecture_id": "uuid",
    "job_type": "transcribe",
    "progress": 0.65,
    "status": "running",
    "message": "Transcribing... 65%"
}
```

Redis pub/sub channels:

| Channel | Publisher | Subscriber | Purpose |
|---------|-----------|------------|---------|
| `lecture:{id}:progress` | Celery worker | FastAPI WebSocket | Real-time progress |
| `lecture:{id}:transcript` | Celery worker | FastAPI WebSocket | Live transcript |
| `lecture:{id}:status` | FastAPI | Frontend | Status change notifications |

---

## 7. API Specifications

### 7.1 Backend API (Machine A — FastAPI)

#### 7.1.1 Authentication

##### `POST /api/v1/auth/register`

```
Request:
{
    "email": "teacher@example.com",
    "password": "SecureP@ss1",
    "full_name": "Dr. Jane Smith"
}

Response 201:
{
    "id": "uuid",
    "email": "teacher@example.com",
    "full_name": "Dr. Jane Smith",
    "created_at": "2026-07-02T10:00:00Z"
}

Validation:
- email: valid email format, max 255 chars
- password: min 8 chars, at least 1 uppercase, 1 number, 1 special char
- full_name: 1-255 chars

Error Codes:
- 409: Email already registered
- 422: Validation error
```

##### `POST /api/v1/auth/login`

```
Request:
{
    "email": "teacher@example.com",
    "password": "SecureP@ss1"
}

Response 200:
{
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 3600
}

Error Codes:
- 401: Invalid credentials
- 423: Account disabled
```

##### `POST /api/v1/auth/refresh`

```
Request:
{
    "refresh_token": "eyJ..."
}

Response 200:
{
    "access_token": "eyJ...",
    "expires_in": 3600
}

Error Codes:
- 401: Invalid or expired refresh token
```

#### 7.1.2 Projects

##### `GET /api/v1/projects`

```
Query Params:
- page: int (default 1)
- page_size: int (default 20, max 100)
- status: str (optional filter)

Response 200:
{
    "items": [
        {
            "id": "uuid",
            "title": "Physics 101 - Chapter 3",
            "description": "Lecture on thermodynamics",
            "status": "active",
            "lecture_count": 5,
            "created_at": "2026-07-01T08:00:00Z"
        }
    ],
    "total": 42,
    "page": 1,
    "page_size": 20,
    "total_pages": 3
}
```

##### `POST /api/v1/projects`

```
Request:
{
    "title": "Physics 101 - Chapter 3",
    "description": "Lecture on thermodynamics"
}

Response 201:
{
    "id": "uuid",
    "title": "Physics 101 - Chapter 3",
    "description": "Lecture on thermodynamics",
    "status": "active",
    "created_at": "2026-07-02T10:00:00Z"
}
```

##### `GET /api/v1/projects/{project_id}`

```
Response 200:
{
    "id": "uuid",
    "title": "...",
    "description": "...",
    "status": "active",
    "lectures": [...],
    "created_at": "...",
    "updated_at": "..."
}

Error Codes:
- 404: Project not found
- 403: Not authorized
```

##### `DELETE /api/v1/projects/{project_id}`

```
Response 204: No Content
Cascades to all lectures, slides, narrations, files.
```

#### 7.1.3 Lectures

##### `POST /api/v1/lectures/upload`

```
Request: multipart/form-data
- project_id: UUID
- title: string
- video_file: File (optional, for video/audio mode)
- audio_file: File (optional, for audio-only mode)
- pptx_file: File (optional)
- voice_profile_id: UUID (optional)

Validation:
- At least one of video_file or audio_file required
- video_file: .mp4, .mov, .mkv (max 2GB)
- audio_file: .mp3, .wav, .m4a, .aac (max 500MB)
- pptx_file: .pptx (max 200MB)

Response 202:
{
    "id": "uuid",
    "title": "Physics 101 - Lecture 1",
    "input_type": "video",
    "status": "pending",
    "job_id": "uuid",
    "created_at": "2026-07-02T10:00:00Z"
}

Error Codes:
- 400: No file provided
- 413: File too large
- 415: Unsupported file type
- 404: Project not found
```

##### `POST /api/v1/lectures/live/start`

```
Request:
{
    "project_id": "uuid",
    "title": "Live Lecture - Chapter 4",
    "pptx_file_id": "uuid",
    "voice_profile_id": "uuid"
}

Response 201:
{
    "id": "uuid",
    "ws_url": "wss://host/api/v1/ws/lecture/{id}",
    "status": "recording"
}
```

##### `POST /api/v1/lectures/live/{lecture_id}/stop`

```
Response 200:
{
    "id": "uuid",
    "status": "processing",
    "job_id": "uuid",
    "message": "Finalizing transcript and starting narration pipeline"
}
```

##### `GET /api/v1/lectures/{lecture_id}`

```
Response 200:
{
    "id": "uuid",
    "project_id": "uuid",
    "title": "...",
    "input_type": "video",
    "status": "completed",
    "duration_seconds": 2700,
    "slides": [
        {
            "id": "uuid",
            "slide_number": 1,
            "raw_text": "Thermodynamics...",
            "narration": {
                "id": "uuid",
                "script_text": "Welcome to thermodynamics...",
                "audio_url": "/api/v1/files/{narration_audio_id}",
                "duration_seconds": 120,
                "status": "completed"
            }
        }
    ],
    "transcript_url": "/api/v1/files/{transcript_id}",
    "narrated_pptx_url": "/api/v1/files/{narrated_pptx_id}",
    "created_at": "...",
    "updated_at": "..."
}
```

##### `GET /api/v1/lectures/{lecture_id}/status`

```
Response 200:
{
    "id": "uuid",
    "status": "processing",
    "progress": 0.45,
    "current_stage": "Transcribing lecture audio",
    "jobs": [
        {
            "id": "uuid",
            "job_type": "extract_audio",
            "status": "completed",
            "progress": 1.0
        },
        {
            "id": "uuid",
            "job_type": "transcribe",
            "status": "running",
            "progress": 0.65
        }
    ],
    "error_message": null
}
```

#### 7.1.4 Voice Profiles

##### `GET /api/v1/voice-profiles`

```
Response 200:
{
    "items": [
        {
            "id": "uuid",
            "name": "My Teaching Voice",
            "status": "ready",
            "created_at": "..."
        }
    ]
}
```

##### `POST /api/v1/voice-profiles`

```
Request: multipart/form-data
- name: string
- audio_file: File (.mp3, .wav, .m4a, .aac)
- consent: boolean (required)

Validation:
- audio: min 30 seconds, max 10 minutes, single speaker
- consent must be true

Response 202:
{
    "id": "uuid",
    "name": "My Teaching Voice",
    "status": "cloning",
    "job_id": "uuid"
}
```

#### 7.1.5 Files

##### `GET /api/v1/files/{file_id}`

```
Response 200: Binary file stream with Content-Disposition

Headers:
- Content-Type: application/vnd.openxmlformats-officedocument.presentationml.presentation
- Content-Disposition: attachment; filename="narrated_lecture.pptx"
- Content-Length: 12345678

Error Codes:
- 404: File not found
- 403: Not authorized
```

#### 7.1.6 Jobs

##### `GET /api/v1/jobs/{job_id}`

```
Response 200:
{
    "id": "uuid",
    "lecture_id": "uuid",
    "job_type": "transcribe",
    "status": "running",
    "progress": 0.65,
    "result": null,
    "error_message": null,
    "created_at": "...",
    "started_at": "...",
    "completed_at": null
}
```

#### 7.1.7 Health

##### `GET /api/v1/health`

```
Response 200:
{
    "status": "healthy",
    "version": "1.0.0",
    "services": {
        "postgres": "healthy",
        "redis": "healthy",
        "celery": "healthy",
        "ai_transcription": "healthy",
        "ai_llm": "healthy",
        "ai_tts": "healthy"
    },
    "uptime_seconds": 12345
}
```

### 7.2 WebSocket Endpoints (Backend)

##### `WS /api/v1/ws/lecture/{lecture_id}`

Live lecture audio streaming.

```
Client → Server: Binary audio chunk (Opus/PCM)

Server → Client: JSON transcript update

{
    "type": "transcript_partial",
    "lecture_id": "uuid",
    "text": "In today's lecture we will discuss...",
    "is_final": false,
    "segment_number": 42,
    "slide_number": 3
}

{
    "type": "transcript_final",
    "lecture_id": "uuid",
    "text": "In today's lecture we will discuss thermodynamics...",
    "is_final": true,
    "segment_number": 42,
    "start_time": 120.5,
    "end_time": 125.3,
    "slide_number": 3
}

{
    "type": "error",
    "code": "STREAM_DISCONNECTED",
    "message": "Audio stream interrupted, partial transcript saved"
}
```

##### `WS /api/v1/ws/lecture/{lecture_id}/progress`

```
Server Messages:
{
    "type": "progress",
    "lecture_id": "uuid",
    "job_type": "transcribe",
    "progress": 0.65,
    "status": "running",
    "message": "Transcribing... 65%"
}

{
    "type": "completed",
    "lecture_id": "uuid",
    "narrated_pptx_url": "/api/v1/files/{id}"
}

{
    "type": "failed",
    "lecture_id": "uuid",
    "error": "Transcription failed: audio too short"
}
```

### 7.3 AI Server APIs (Machine B)

##### `POST /ai/v1/transcribe`

```
Request: multipart/form-data
- audio_file: File (.wav, 16kHz mono)
- language: string (optional, auto-detect)
- vad_filter: boolean (default true)

Response 200:
{
    "status": "completed",
    "duration_seconds": 2700,
    "segments": [
        {
            "segment_number": 1,
            "start_time": 0.0,
            "end_time": 5.2,
            "text": "Welcome to today's lecture on thermodynamics.",
            "confidence": 0.98,
            "speaker": null
        }
    ],
    "language": "en",
    "language_probability": 0.99,
    "processing_time_seconds": 45.3
}

Error Codes:
- 400: Invalid audio (corrupted, too short)
- 413: Audio too large
- 500: Model inference error
```

##### `WS /ai/v1/ws/transcribe`

```
Client → Server: Binary audio chunk (16kHz mono PCM)

Server → Client: JSON
{
    "type": "partial",
    "text": "In today's lecture we will discuss",
    "segment_number": 42,
    "start_time": 120.5,
    "end_time": null
}

{
    "type": "final",
    "text": "In today's lecture we will discuss thermodynamics.",
    "segment_number": 42,
    "start_time": 120.5,
    "end_time": 125.3,
    "confidence": 0.97
}
```

##### `POST /ai/v1/align`

```
Request:
{
    "transcript": {
        "segments": [
            {"start_time": 0.0, "end_time": 5.2, "text": "Welcome to thermodynamics."},
            {"start_time": 5.2, "end_time": 30.1, "text": "Let's begin with the first law..."}
        ]
    },
    "slides": [
        {
            "slide_number": 1,
            "raw_text": "Chapter 3: Thermodynamics\nFirst Law of Thermodynamics",
            "notes": "Explain conservation of energy"
        },
        {
            "slide_number": 2,
            "raw_text": "First Law: ΔU = Q - W",
            "notes": ""
        }
    ]
}

Response 200:
{
    "alignments": [
        {
            "slide_number": 1,
            "segments": [1, 2],
            "confidence": 0.95,
            "start_time": 0.0,
            "end_time": 30.1
        },
        {
            "slide_number": 2,
            "segments": [3, 4, 5],
            "confidence": 0.88,
            "start_time": 30.1,
            "end_time": 90.5
        }
    ],
    "unassigned_segments": [12, 15],
    "model": "qwen3-14b"
}
```

##### `POST /ai/v1/generate-narration`

```
Request:
{
    "lecture_title": "Physics 101 - Thermodynamics",
    "slides": [
        {
            "slide_number": 1,
            "raw_text": "Chapter 3: Thermodynamics\nFirst Law of Thermodynamics",
            "notes": "Explain conservation of energy",
            "transcript_segments": [
                {"text": "Welcome to thermodynamics.", "start_time": 0.0, "end_time": 5.2},
                {"text": "Today we'll cover the first law.", "start_time": 5.2, "end_time": 30.1}
            ]
        }
    ]
}

Response 200:
{
    "narrations": [
        {
            "slide_number": 1,
            "script_text": "Welcome to Chapter 3 on Thermodynamics...",
            "estimated_duration_seconds": 30,
            "tone": "educational",
            "key_points": ["Energy conservation", "First law definition"],
            "model": "qwen3-14b"
        }
    ]
}
```

##### `POST /ai/v1/tts`

```
Request: multipart/form-data
- text: string (narration script)
- voice_profile_id: string (optional)
- voice_sample: File (optional, upload new sample)
- speed: float (0.5 to 2.0, default 1.0)

Response 200:
{
    "status": "completed",
    "audio_duration_seconds": 30.5,
    "audio_format": "wav",
    "sample_rate": 24000,
    "processing_time_seconds": 8.2
}

Binary audio data follows as response body (Content-Type: audio/wav).
```

##### `POST /ai/v1/clone-voice`

```
Request: multipart/form-data
- audio_sample: File (.wav, 30s-10min)
- name: string

Response 200:
{
    "status": "completed",
    "voice_profile_id": "uuid",
    "speaker_id": "spk_001",
    "sample_duration_seconds": 120
}
```

##### `GET /ai/v1/health`

```
Response 200:
{
    "status": "healthy",
    "models": {
        "whisper": {"loaded": true, "model_size": "large-v3"},
        "vllm": {"loaded": true, "model": "qwen3-14b", "healthy": true},
        "f5tts": {"loaded": true, "sample_rate": 24000}
    },
    "gpu": {
        "name": "Blackwell",
        "memory_total_gb": 24,
        "memory_used_gb": 18.5,
        "utilization_percent": 45
    },
    "uptime_seconds": 7200
}
```

### 7.4 HTTP Status Code Conventions

| Code | Usage |
|------|-------|
| 200 | Successful GET, POST (sync response) |
| 201 | Successful resource creation |
| 202 | Accepted for async processing (job queued) |
| 204 | Successful DELETE |
| 400 | Bad request (validation failed) |
| 401 | Unauthenticated |
| 403 | Unauthorized (wrong permissions) |
| 404 | Resource not found |
| 409 | Conflict (duplicate email) |
| 413 | Payload too large |
| 415 | Unsupported media type |
| 422 | Unprocessable entity (Pydantic validation) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 502 | AI server unavailable |
| 503 | Service temporarily unavailable |

---

## 8. Internal AI Pipeline

### 8.1 Pipeline Stages

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ Extract  │──▶│ Trans-   │──▶│ PPTX     │──▶│ Align    │──▶│ Generate │──▶│ Generate │──▶│ Embed    │
│ Audio    │   │ cribe    │   │ Parse    │   │ Transcript│   │ Narration│   │ TTS      │   │ Narration│
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
     │              │              │              │              │              │              │
     ▼              ▼              ▼              ▼              ▼              ▼              ▼
  ffmpeg        Faster-       python-pptx     Qwen3 via      Qwen3 via     F5-TTS        python-pptx
  extract       Whisper       extract        vLLM           vLLM                         add_audio
  audio stream  large-v3      text+notes     API            API
```

### 8.2 Stage Details

**Stage 1: Audio Extraction**
- Validate video file integrity (ffprobe)
- Extract audio stream to 16kHz mono WAV (ffmpeg)
- Normalize volume (loudnorm filter)
- Command: `ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 -af loudnorm=I=-16:LRA=11:TP=-1.5 output.wav`

**Stage 2: Transcription**
- Load audio into memory (numpy)
- Run Faster-Whisper inference (large-v3)
- Apply VAD filter (Silero VAD)
- Generate timestamped segments with confidence scores

**Stage 3: PPTX Parsing**
- Load .pptx file (python-pptx)
- Iterate slides, extract text from all shapes
- Extract speaker notes, slide layout info
- Render slide as PNG (optional, via LibreOffice)

**Stage 4: Transcript-Slide Alignment**
- Prepare slide text + transcript
- Send to LLM for semantic alignment (POST /ai/v1/align)
- Parse and validate alignment result
- Update transcript_segments.slide_id

**Stage 5: Narration Generation**
- For each slide, prepare context (slide text + notes + aligned transcript)
- Send to LLM (POST /ai/v1/generate-narration)
- Validate structured JSON output
- Store narration scripts

**Stage 6: TTS Generation**
- For each narration, prepare text + voice profile
- Send to TTS service (POST /ai/v1/tts)
- Receive audio binary, store file
- Update narration record with audio_path

**Stage 7: Embed Narration**
- Load original .pptx (python-pptx)
- Add narration audio to each slide
- Configure media playback options
- Save narrated .pptx

---

## 9. Sequence Diagrams

### 9.1 User Upload (Video Mode)

```
Frontend               Backend              Celery Worker          AI Server
    │                     │                      │                    │
    │   POST /lectures/   │                      │                    │
    │   multipart/form    │                      │                    │
    │─────────────────────▶                      │                    │
    │                     │                      │                    │
    │                     │ Validate files       │                    │
    │                     │ Store to disk         │                    │
    │                     │ Create lecture + job  │                    │
    │                     │ Enqueue pipeline      │                    │
    │                     │──────────────────────▶                    │
    │                     │                      │                    │
    │   202 {lecture_id}  │                      │                    │
    │◀─────────────────────                      │                    │
    │                     │                      │                    │
    │   WS /ws/lecture/{id}/progress             │                    │
    │■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■│
    │                     │                      │ Stage 1: Extract   │
    │                     │                      │ Audio (ffmpeg)     │
    │◀── progress 25% ───│◀───── pub/sub ────────│                    │
    │                     │                      │ Stage 2: Transcribe│
    │                     │                      │──── POST /transcribe───────────▶│
    │◀── progress 50% ───│◀───── pub/sub ────────│◀───────────────────────────────│
    │                     │                      │ Stage 3: Parse PPTX│
    │                     │                      │ (python-pptx)      │
    │                     │                      │ Stage 4: Align     │
    │                     │                      │──── POST /align ───────────────▶│
    │◀── progress 75% ───│◀───── pub/sub ────────│◀───────────────────────────────│
    │                     │                      │ Stage 5: Narrate   │
    │                     │                      │──── POST /generate-narration──▶│
    │◀── progress 85% ───│◀───── pub/sub ────────│◀───────────────────────────────│
    │                     │                      │ Stage 6: TTS       │
    │                     │                      │──── POST /tts ────────────────▶│
    │◀── progress 95% ───│◀───── pub/sub ────────│◀───────────────────────────────│
    │                     │                      │ Stage 7: Embed     │
    │                     │                      │ (python-pptx)      │
    │                     │                      │                    │
    │◀── progress 100% ──│◀───── pub/sub ────────│                    │
    │                     │                      │                    │
    │   GET /lectures/{id}│                      │                    │
    │─────────────────────▶                      │                    │
    │◀──── narrated PPTX ───────────────────────│                    │
```

### 9.2 Live Lecture Recording

```
Frontend (Browser)       Backend                AI Server
    │                      │                       │
    │  POST /lectures/live/start                   │
    │─────────────────────▶                        │
    │     {id, ws_url}    │                        │
    │◀─────────────────────                        │
    │                      │                       │
    │  WS /ws/lecture/{id} │                       │
    │══════════════════════▶                       │
    │                      │                       │
    │  [Teacher: Start]    │                       │
    │                      │                       │
    │  Audio chunk 1 ──────┼──── WS message ──────▶│
    │◀──── partial ───────┼◀── WS response ───────│
    │                      │                       │
    │  Audio chunk 2 ──────┼──── WS message ──────▶│
    │◀──── partial ───────┼◀── WS response ───────│
    │                      │                       │
    │  [Teacher: Pause]    │                       │
    │  (pause audio send)  │                       │
    │                      │                       │
    │  [Teacher: Resume]   │                       │
    │  Audio chunk N ──────┼──── WS message ──────▶│
    │                      │                       │
    │  [Teacher: Stop]     │                       │
    │                      │                       │
    │  POST /lectures/live/{id}/stop               │
    │─────────────────────▶                        │
    │                      │                       │
    │                      │ Finalize transcript   │
    │                      │ Enqueue pipeline      │
    │                      │ (skip audio extract)  │
    │                      │                       │
    │   {status:processing}│                       │
    │◀─────────────────────                        │
    │                      │                       │
    │  → Pipeline continues (align → narrate → TTS → embed)
```

---

## 10. PowerPoint Parsing Strategy

### 10.1 Parsing Approach

Using `python-pptx` library to extract structured content from each slide.

```python
from pptx import Presentation

def parse_pptx(pptx_path: str) -> list[dict]:
    prs = Presentation(pptx_path)
    slides = []

    for i, slide in enumerate(prs.slides, start=1):
        all_text = []

        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        all_text.append(text)

        # Extract speaker notes
        notes_text = None
        if slide.has_notes_slide:
            notes_text = slide.notes_slide.notes_text_frame.text.strip() or None

        slides.append({
            "slide_number": i,
            "raw_text": "\n".join(all_text),
            "notes": notes_text,
            "layout_name": slide.slide_layout.name,
        })

    return slides
```

### 10.2 Slide Content Stored

| Field | Type | Source | Purpose |
|-------|------|--------|---------|
| `slide_number` | int | Slide index | Ordering |
| `raw_text` | text | All shapes | LLM context |
| `notes` | text | Notes pane | Additional context |
| `image_path` | text | Extracted images | Visual context (future) |
| `slide_layout` | text | Layout name | Structure hints |

---

## 11. Transcript-to-Slide Alignment Algorithm

### 11.1 Approaches Considered

**Approach A: Keyword Overlap (TF-IDF + Cosine Similarity)**
- Extract keywords from each slide and transcript segment
- Compute cosine similarity
- Pros: Fast, no GPU needed
- Cons: ~60-70% accuracy, fails on synonyms

**Approach B: Semantic Embedding Similarity (Sentence Transformers)**
- Embed slide text and transcript segments into vectors
- Compute cosine similarity with temporal smoothing
- Pros: Handles synonyms, ~80% accuracy
- Cons: Misses domain-specific context

**Approach C: LLM-Based Semantic Alignment (Selected)**
- Group transcript segments into chunks
- Query LLM: "Which slide does this content belong to?"
- LLM reasons about slide content, transcript semantics, lecture flow
- Pros: ~95% accuracy, handles implicit references
- Cons: Slower (1-2s per segment)

**Approach D: Hybrid (LLM + Temporal Constraints + Fallback) — SELECTED**
1. LLM for primary alignment
2. Temporal monotonicity constraint (segments only go forward)
3. Embedding similarity as fallback if LLM unavailable
4. Keyword overlap as last resort

### 11.2 Temporal Constraint Algorithm

```python
def enforce_temporal_constraints(alignments: list[dict]) -> list[dict]:
    """
    1. First segment → slide 1 or unassigned
    2. Slide number must be non-decreasing over time
    3. If LLM assigns slide 5 then slide 3, clamp slide 3 to slide 5
    4. Interpolate unassigned segments
    """
    result = []
    current_slide = 1

    for seg in sorted(alignments, key=lambda x: x["segment_number"]):
        if seg.get("confidence", 0) >= 0.7:
            seg["slide_number"] = max(seg["slide_number"], current_slide)
            current_slide = seg["slide_number"]
        else:
            seg["slide_number"] = current_slide
            seg["needs_review"] = True

        result.append(seg)

    return result
```

### 11.3 Batch Sizing for LLM

| Content Length | Batch Size | Notes |
|---------------|------------|-------|
| < 30 segments | All at once | Single LLM call |
| 30-100 segments | 30 segments/call | Split by time boundaries |
| > 100 segments | 50 segments/call | 5-segment overlap for continuity |

---

## 12. Prompt Engineering

### 12.1 Narration Generation — System Prompt

```
You are an expert educational narration scriptwriter. Your task is to generate
a natural, engaging narration script for each PowerPoint slide based on:
1. The slide's visual content (text extracted from the slide)
2. The teacher's speaker notes (if available)
3. The transcript of what the teacher actually said during this slide

Guidelines:
- Write in a conversational, teaching tone (as if the teacher is explaining).
- Do NOT read slide text verbatim — expand, explain, contextualize.
- Each narration should be 30-90 seconds when spoken (75-225 words).
- Use transitions between slides.
- Include verbal signposts ("First...", "Importantly...", "To summarize...").
- Assume the listener cannot see the slide — describe key visuals when relevant.
- Maintain the original teacher's terminology and domain accuracy.
- If the teacher went off-topic or made an error, correct it gracefully.
- Keep explanations clear enough for a student who missed the live lecture.

Output format:
{
    "script_text": "string (the complete narration)",
    "estimated_duration_seconds": integer,
    "tone": "educational | explanatory | review",
    "key_points": ["point1", "point2", ...]
}
```

### 12.2 Narration Generation — User Prompt

```
Lecture Title: {lecture_title}

Slide {slide_number} of {total_slides}

Slide Content:
{slide_raw_text}

Teacher's Notes:
{slide_notes}

Teacher's Actual Lecture Transcript (aligned to this slide):
{transcript_text}
(Time range: {start_time} - {end_time})

Previous slide's narration ended with: "...{previous_narration_last_sentence}"

Generate a narration script for this slide following the system guidelines.
Return ONLY valid JSON.
```

### 12.3 Transcript Alignment — System Prompt

```
You are a lecture transcript-to-slide alignment system. Given:
1. A list of slides with their text content
2. A list of transcript segments with timestamps and text

Your task is to determine which slide each transcript segment belongs to.

Rules:
- Transcript segments progress forward in time. Do not assign later segments to earlier slides.
- A segment may be "unassigned" (0) if it is clearly off-topic.
- Multiple consecutive segments will typically belong to the same slide.
- If uncertain, return your best guess with lower confidence.

Output format:
{
    "alignments": [
        {
            "segment_number": integer,
            "slide_number": integer (0 for unassigned),
            "confidence": float (0.0 to 1.0),
            "reasoning": "brief explanation"
        }
    ]
}
```

### 12.4 Structured Output Validation

```python
from pydantic import BaseModel, Field
from typing import Literal

class NarrationOutput(BaseModel):
    script_text: str = Field(..., min_length=10, max_length=2000)
    estimated_duration_seconds: int = Field(..., ge=10, le=300)
    tone: Literal["educational", "explanatory", "review"]
    key_points: list[str] = Field(..., min_length=1, max_length=10)

class AlignmentOutput(BaseModel):
    alignments: list[dict]

    @classmethod
    def validate_forward_progress(cls, v: list[dict]) -> list[dict]:
        segments = sorted(v, key=lambda x: x["segment_number"])
        last_slide = 0
        for seg in segments:
            slide = seg.get("slide_number", 0)
            if slide != 0 and slide < last_slide:
                raise ValueError(f"Backwards slide progression at segment {seg['segment_number']}")
            if slide != 0:
                last_slide = slide
        return v
```

---

## 13. Voice Cloning Flow

### 13.1 End-to-End Flow

```
Teacher                     Backend                        AI Server (F5-TTS)
   │                           │                              │
   │  Upload voice sample      │                              │
   │──────────────────────────▶│                              │
   │                           │ Validate audio               │
   │                           │ - At least 30 seconds        │
   │                           │ - Single speaker             │
   │                           │ - Clear recording            │
   │                           │                              │
   │                           │ POST /ai/v1/clone-voice      │
   │                           │─────────────────────────────▶│
   │                           │                              │
   │                           │                              │ Extract features
   │                           │                              │ Train speaker embedding
   │                           │                              │ Save model checkpoint
   │                           │                              │
   │                           │◀──── voice_profile_id ───────│
   │                           │                              │
   │  202 {voice_profile_id}   │                              │
   │◀─────────────────────────│                              │
```

### 13.2 F5-TTS Integration

```python
class F5TTSModel:
    def __init__(self, model_path: str):
        self.model = load_f5tts(model_path)
        self.sample_rate = 24000

    def clone_voice(self, audio_sample: np.ndarray, name: str) -> str:
        audio = preprocess_audio(audio_sample, target_sr=self.sample_rate)
        speaker_embedding = self.model.extract_speaker_embedding(audio)
        speaker_id = f"spk_{uuid.uuid4().hex[:12]}"
        save_speaker_embedding(speaker_id, speaker_embedding)
        return speaker_id

    def synthesize(self, text: str, speaker_id: str, speed: float = 1.0) -> np.ndarray:
        speaker_embedding = load_speaker_embedding(speaker_id)
        audio = self.model.synthesize(
            text=text,
            speaker_embedding=speaker_embedding,
            speed=speed,
        )
        return audio
```

### 13.3 Voice Profile Lifecycle

```
Status Flow: PENDING → CLONING → READY
                              ↓
                            FAILED

CLONING: Voice is being processed (30s-5min)
READY: Voice can be used for TTS
FAILED: Sample was insufficient (too short, noisy, multiple speakers)

Cleanup:
- Inactive profiles older than 6 months → archived
- Model checkpoints can be 50-200MB per profile
- Profiles are user-scoped; deletion cascades on user departure
```

---

## 14. File Storage Layout

### 14.1 Local Filesystem Structure (MVP)

```
/data/storage/
├── users/
│   └── {user_id}/
│       ├── voice_samples/
│       │   └── {voice_profile_id}/
│       │       ├── original.mp3
│       │       └── processed.wav
│       └── voice_models/
│           └── {voice_profile_id}/
│               └── speaker_embedding.pt
├── projects/
│   └── {project_id}/
│       └── lectures/
│           └── {lecture_id}/
│               ├── source/
│               │   ├── video.mp4
│               │   ├── audio.mp3
│               │   └── slides.pptx
│               ├── audio/
│               │   └── extracted.wav
│               ├── slides/
│               │   ├── slide_001.png
│               │   └── ...
│               ├── transcript/
│               │   ├── raw.json
│               │   └── aligned.json
│               ├── narrations/
│               │   ├── narration_slide_001.json
│               │   └── ...
│               ├── audio_narrations/
│               │   ├── slide_001.wav
│               │   └── ...
│               └── output/
│                   └── narrated_lecture.pptx
└── temp/
    └── uploads/
        └── {session_id}/
            ├── chunk_001.webm
            └── ...
```

### 14.2 Storage Path Resolution

```python
from pathlib import Path

class StoragePaths:
    STORAGE_ROOT = Path("/data/storage")

    @classmethod
    def lecture_source_video(cls, lecture_id: str, project_id: str) -> Path:
        return cls.STORAGE_ROOT / "projects" / project_id / "lectures" / lecture_id / "source" / "video.mp4"

    @classmethod
    def extracted_audio(cls, lecture_id: str, project_id: str) -> Path:
        return cls.STORAGE_ROOT / "projects" / project_id / "lectures" / lecture_id / "audio" / "extracted.wav"

    @classmethod
    def narration_audio(cls, lecture_id: str, project_id: str, slide_number: int) -> Path:
        return cls.STORAGE_ROOT / "projects" / project_id / "lectures" / lecture_id / "audio_narrations" / f"slide_{slide_number:03d}.wav"

    @classmethod
    def output_pptx(cls, lecture_id: str, project_id: str) -> Path:
        return cls.STORAGE_ROOT / "projects" / project_id / "lectures" / lecture_id / "output" / "narrated_lecture.pptx"
```

---

## 15. Docker Compose Architecture

### 15.1 Root `docker-compose.yml`

```yaml
version: "3.9"

networks:
  web-network:
    driver: bridge
  ai-network:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
  storage_data:
  model_cache:

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infrastructure/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./infrastructure/nginx/sites:/etc/nginx/conf.d:ro
    depends_on:
      - frontend
      - backend
    networks:
      - web-network
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      - NEXT_PUBLIC_API_URL=https://api.example.com
    expose:
      - "3000"
    networks:
      - web-network
    restart: unless-stopped

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file:
      - .env
    expose:
      - "8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - storage_data:/data/storage
    networks:
      - web-network
      - ai-network
    restart: unless-stopped

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A src.worker.celery_app worker -Q default,audio,transcription,llm,tts,pptx,priority_high -l INFO --concurrency=2
    env_file:
      - .env
    depends_on:
      - backend
      - redis
    volumes:
      - storage_data:/data/storage
    networks:
      - web-network
      - ai-network
    restart: unless-stopped

  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A src.worker.celery_app beat -l INFO
    env_file:
      - .env
    depends_on:
      - redis
    networks:
      - web-network
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: lecture_narrator
      POSTGRES_USER: app_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    expose:
      - "5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app_user -d lecture_narrator"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - web-network
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    expose:
      - "6379"
    networks:
      - web-network
    restart: unless-stopped
```

### 15.2 AI Server `docker-compose.ai.yml`

```yaml
version: "3.9"

networks:
  ai-network:
    driver: bridge

volumes:
  whisper_models:
  vllm_models:
  f5tts_models:

services:
  transcription:
    build:
      context: ./ai-server/services/transcription
      dockerfile: Dockerfile
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["0"]
              capabilities: [gpu]
    environment:
      - WHISPER_MODEL_SIZE=large-v3
      - WHISPER_DEVICE=cuda
      - WHISPER_COMPUTE_TYPE=float16
    volumes:
      - whisper_models:/root/.cache/whisper
      - storage_data:/data/storage:ro
    expose:
      - "8001"
    networks:
      - ai-network
    restart: unless-stopped

  vllm:
    image: vllm/vllm-openai:latest
    command:
      - "--model"
      - "Qwen/Qwen3-8B"
      - "--gpu-memory-utilization"
      - "0.90"
      - "--max-model-len"
      - "32768"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["0"]
              capabilities: [gpu]
    environment:
      - HUGGING_FACE_HUB_TOKEN=${HF_TOKEN}
    volumes:
      - vllm_models:/root/.cache/huggingface
    expose:
      - "8000"
    networks:
      - ai-network
    restart: unless-stopped

  llm:
    build:
      context: ./ai-server/services/llm
      dockerfile: Dockerfile
    depends_on:
      - vllm
    environment:
      - VLLM_API_URL=http://vllm:8000/v1
      - VLLM_MODEL=Qwen/Qwen3-8B
    expose:
      - "8002"
    networks:
      - ai-network
    restart: unless-stopped

  tts:
    build:
      context: ./ai-server/services/tts
      dockerfile: Dockerfile
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["0"]
              capabilities: [gpu]
    environment:
      - TTS_MODEL_PATH=/models/f5-tts
      - TTS_DEVICE=cuda
    volumes:
      - f5tts_models:/models
      - storage_data:/data/storage
    expose:
      - "8003"
    networks:
      - ai-network
    restart: unless-stopped
```

### 15.3 GPU Memory Budget (Blackwell ~24GB)

| Component | Model | Memory | Notes |
|-----------|-------|--------|-------|
| vLLM | Qwen3-8B (BF16) | ~16GB | Primary LLM |
| Transcription | Faster-Whisper large-v3 | ~4GB | Loads only during transcription |
| TTS | F5-TTS | ~4GB | Loads only during TTS |

Due to memory constraints, vLLM and TTS/transcription share GPU time:
- Use Qwen3-8B instead of 14B
- Time-slice GPU: transcription/tts run when vLLM is idle
- Or use a smaller whisper model (medium) to free memory

---

## 16. Deployment Guide

### 16.1 Prerequisites

```
Machine A (Web Server):
- Ubuntu 24.04 LTS
- Docker 24+
- Docker Compose v2+
- Intel i7-14700, 8GB RAM, 100GB+ SSD

Machine B (AI Server):
- Ubuntu 24.04 LTS
- Docker 24+
- NVIDIA Driver 550+
- NVIDIA Container Toolkit
- Blackwell GPU (24GB+ VRAM), 32GB+ RAM, 200GB+ SSD
```

### 16.2 Deployment Steps

```bash
# 1. Clone repository
git clone https://github.com/org/ai-lecture-narrator.git
cd ai-lecture-narrator

# 2. Configure environment
cp .env.example .env
# Edit .env with secrets and passwords

# 3. Machine A - Deploy web services
docker compose -f infrastructure/docker-compose.yml up -d

# 4. Machine B - Deploy AI services
docker compose -f ai-server/docker-compose.ai.yml up -d

# 5. Run database migrations
docker compose exec backend alembic upgrade head

# 6. Verify health
curl https://app.example.com/api/v1/health
```

### 16.3 Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name app.example.com;

    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
    }

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_buffering off;
    }

    location /ws/ {
        proxy_pass http://backend:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
    }

    location /api/v1/lectures/upload {
        client_max_body_size 2048m;
        proxy_pass http://backend:8000;
        proxy_read_timeout 300s;
    }
}
```

### 16.4 Security Hardening

```bash
# Firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp        # SSH
ufw allow 443/tcp       # HTTPS
ufw enable
```

### 16.5 Backup Strategy

| Data | Frequency | Method | Retention |
|------|-----------|--------|-----------|
| PostgreSQL | Daily | pg_dump → encrypted S3 | 30 days |
| User files | Daily | rsync → backup server | 7 days |
| Voice profiles | Weekly | Cold storage archive | Permanent |
| Redis | Continuous | AOF + daily RDB | 7 days |
| Nginx logs | Daily | Logrotate | 90 days |

---

## 17. Security

### 17.1 Authentication & Authorization

| Mechanism | Implementation | Details |
|-----------|---------------|---------|
| Password hashing | bcrypt (12 rounds) | passlib.context.CryptContext |
| JWT access tokens | RS256, 1 hour expiry | python-jose |
| JWT refresh tokens | RS256, 30 day expiry, rotate on use | Stored hashed in DB |
| API key auth (AI server) | Static key in header | Internal network only |
| Rate limiting | Token bucket, per-user | Redis-backed |
| CORS | Strict origin whitelist | Production only allows app domain |

### 17.2 File Upload Security

```python
ALLOWED_VIDEO_TYPES = {".mp4", ".mov", ".mkv"}
ALLOWED_AUDIO_TYPES = {".mp3", ".wav", ".m4a", ".aac"}
ALLOWED_PPTX_TYPES = {".pptx"}
MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
MAX_AUDIO_SIZE = 500 * 1024 * 1024       # 500MB
MAX_PPTX_SIZE = 200 * 1024 * 1024        # 200MB

def validate_upload(file):
    # 1. Extension check
    # 2. MIME type validation (magic bytes)
    # 3. Size check
    # 4. Filename sanitization (secure_filename)
    pass
```

### 17.3 API Security

| Threat | Mitigation |
|--------|------------|
| CSRF | SameSite=Strict cookies, Origin header validation |
| XSS | Content-Security-Policy headers, input sanitization |
| SQL injection | SQLAlchemy ORM (parameterized queries) |
| Path traversal | All storage paths resolved via StoragePaths class |
| DoS | Rate limiting (100 req/min per user), max upload sizes |
| Model theft | AI server on internal network, API key auth |
| Data leakage | Signed download URLs with expiry (1 hour) |

---

## 18. Logging

### 18.1 Logging Architecture

All services emit structured JSON logs to stdout, collected by Loki and visualized in Grafana.

### 18.2 Structured Log Format

```json
{
    "timestamp": "2026-07-02T10:00:00.123Z",
    "level": "INFO",
    "service": "backend",
    "trace_id": "abc-123-def",
    "user_id": "uuid",
    "lecture_id": "uuid",
    "message": "Lecture upload completed",
    "duration_ms": 1450,
    "file_size_bytes": 52428800
}
```

### 18.3 Correlation IDs

Every request receives a trace ID (propagated via middleware header `X-Trace-ID`), sent to AI server in HTTP headers, included in Celery task messages, and logged in all service logs.

---

## 19. Monitoring

### 19.1 Key Metrics

| Category | Metric | Alert Threshold |
|----------|--------|-----------------|
| API | P99 latency | > 3s |
| Queue | Queue depth | > 100 pending |
| Database | Query latency (P95) | > 500ms |
| GPU | VRAM usage | > 90% |
| GPU | Temperature | > 80°C |
| Storage | Disk usage | > 85% |
| Business | Processing time | > 30min |

### 19.2 Monitoring Stack

```
Prometheus (metrics collection)
  ↓
Grafana (visualization + alerts)

Loki (log aggregation)
  ↓
Grafana (log exploration)

Health endpoints:
  GET /api/v1/health          → Backend + dependencies
  GET /ai/v1/health           → AI server + GPU stats
```

---

## 20. Configuration Management

### 20.1 Configuration Hierarchy

```
Environment Variables (OS/Container)
        ↓
.env file (docker-compose)
        ↓
Pydantic Settings (backend/src/config/settings.py)
        ↓
Application Code (type-validated, immutable at runtime)
```

### 20.2 Pydantic Settings Design

```python
from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, RedisDsn

class Settings(BaseSettings):
    APP_NAME: str = "AI Lecture Narrator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    DATABASE_URL: PostgresDsn
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    REDIS_URL: RedisDsn
    REDIS_RESULT_URL: RedisDsn

    JWT_PRIVATE_KEY: str
    JWT_PUBLIC_KEY: str
    JWT_ACCESS_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    AI_TRANSCRIPTION_URL: str = "http://transcription:8001"
    AI_LLM_URL: str = "http://llm:8002"
    AI_TTS_URL: str = "http://tts:8003"
    AI_API_KEY: str

    STORAGE_BACKEND: str = "local"
    STORAGE_ROOT: str = "/data/storage"

    MAX_VIDEO_SIZE_BYTES: int = 2 * 1024 * 1024 * 1024
    MAX_AUDIO_SIZE_BYTES: int = 500 * 1024 * 1024
    MAX_PPTX_SIZE_BYTES: int = 200 * 1024 * 1024

    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    WHISPER_MODEL_SIZE: str = "large-v3"
    VLLM_MODEL: str = "Qwen/Qwen3-8B"
    TTS_SAMPLE_RATE: int = 24000

    class Config:
        env_file = ".env"
        case_sensitive = True
```

---

## 21. Environment Variables

### 21.1 Master `.env.example`

```bash
# Application
APP_NAME="AI Lecture Narrator"
APP_VERSION=1.0.0
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<64-char-random>

# Database
DATABASE_URL=postgresql+asyncpg://app_user:<password>@postgres:5432/lecture_narrator
DB_PASSWORD=<64-char-random>
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# Redis
REDIS_URL=redis://:<password>@redis:6379/0
REDIS_RESULT_URL=redis://:<password>@redis:6379/1
REDIS_PASSWORD=<64-char-random>

# JWT (RSA key pair, base64-encoded)
JWT_PRIVATE_KEY=<base64-RSA-4096-private-key>
JWT_PUBLIC_KEY=<base64-RSA-4096-public-key>
JWT_ACCESS_EXPIRE_MINUTES=60
JWT_REFRESH_EXPIRE_DAYS=30

# AI Server
AI_TRANSCRIPTION_URL=http://transcription:8001
AI_LLM_URL=http://llm:8002
AI_TTS_URL=http://tts:8003
AI_API_KEY=<64-char-random>

# Storage
STORAGE_BACKEND=local
STORAGE_ROOT=/data/storage

# Upload Limits
MAX_VIDEO_SIZE_BYTES=2147483648
MAX_AUDIO_SIZE_BYTES=524288000
MAX_PPTX_SIZE_BYTES=209715200

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# Models
WHISPER_MODEL_SIZE=large-v3
VLLM_MODEL=Qwen/Qwen3-8B
TTS_SAMPLE_RATE=24000

# Hugging Face
HF_TOKEN=<read-only-token>
```

---

## 22. Testing Strategy

### 22.1 Test Pyramid

```
         ╱╲
        ╱  ╲         E2E Tests (5%)
       ╱    ╲
      ╱──────╲
     ╱        ╲      Integration Tests (25%)
    ╱          ╲
   ╱────────────╲
  ╱              ╲   Unit Tests (70%)
 ╱                ╲
╱──────────────────╲
```

### 22.2 Unit Tests (70%)

| Scope | Framework | What to Test |
|-------|-----------|-------------|
| Domain entities | pytest | Entity creation, validation, equality |
| Use cases | pytest + mocks | Business logic, error paths, state transitions |
| DTOs | pytest | Pydantic validation, serialization |
| Value objects | pytest | Email validation, path resolution |
| Prompts | pytest | Template rendering, variable substitution |

### 22.3 Integration Tests (25%)

| Scope | Framework | What to Test |
|-------|-----------|-------------|
| API routes | pytest + httpx | Request/response, auth, status codes |
| Database repos | pytest + test DB | CRUD, queries, constraints |
| File storage | pytest + temp dir | Store, retrieve, delete |
| Celery tasks | pytest + celery_eager | Task execution, retry, error handling |
| Python-pptx | pytest + sample file | Parse, embed, output validation |

### 22.4 AI Tests (Dedicated)

| Test Type | Tool | What to Verify |
|-----------|------|---------------|
| Transcription accuracy | WER (Word Error Rate) | < 10% on lecture audio |
| Alignment accuracy | Manual audit | > 90% on test set |
| Narration quality | LLM-as-judge | Coherence, accuracy, tone |
| TTS quality | MOS (Mean Opinion Score) | > 3.5 on 1-5 scale |
| Pipeline integration | pytest + mock AI | End-to-end job completion |

### 22.5 E2E Tests (5%)

| Tool | What to Test |
|------|-------------|
| Playwright | Upload flow, dashboard, live lecture UI |
| Docker compose | Full stack startup, service health |
| Load tests | k6 or locust for concurrent uploads |

---

## 23. Scalability Plan

### 23.1 10 Users (MVP)

**Architecture:** Single web server + single AI server
**Database:** Single PostgreSQL instance
**Workers:** 1-2 Celery workers
**Storage:** Local filesystem
**GPU:** Single Blackwell
**Limitations:** Everything runs on one RPS. Sequential GPU job processing.

### 23.2 100 Users

**Upgrades:**
- 2-4 Celery workers for parallel job processing
- PostgreSQL connection pooling (PgBouncer)
- GPU time-slicing for concurrent AI inference
- Redis cluster for higher throughput
- CDN for narrated PPTX downloads
**Limitations:** Single GPU becomes bottleneck for concurrent AI requests.

### 23.3 1000 Users

**Upgrades:**
- Horizontal scaling on Machine A (2-3 web servers behind Nginx load balancer)
- Read replicas for PostgreSQL (dashboard queries)
- Celery worker auto-scaling (based on queue depth)
- Multiple GPUs on Machine B (GPU cluster, 2-4 Blackwells)
- S3-compatible object storage (MinIO or AWS S3)
- File metadata CDN cache
**AI Server:** GPU load balancer routing to least-loaded AI service

### 23.4 10000 Users

**Upgrades:**
- Kubernetes cluster (migrate from Docker Compose)
- Database sharding (by user_id)
- Dedicated GPU nodes per AI model type
- Message broker upgrade (Redis → RabbitMQ/Kafka)
- Vector database (Pinecone/Qdrant) for transcript similarity search
- Full observability stack (Tempo tracing)
- Multi-region deployment with CDN
**AI Server:** Dedicated nodes for transcription (4x), LLM (8x), TTS (4x)

---

## 24. Future Architecture

### 24.1 Kubernetes Migration

```
┌─────────────────────────────────────────────────────────────┐
│                      Kubernetes Cluster                     │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Nginx     │ │ Frontend │ │ Backend  │ │ Celery       │   │
│  │ Ingress   │ │ (HPA)    │ │ (HPA)    │ │ Worker (HPA) │   │
│  │ Controller│ │          │ │          │ │              │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Postgres │ │ Redis    │ │ MinIO    │ │ GPU Node 1   │   │
│  │ (HA)     │ │ (Sentinel)│ │ (S3)     │ │ Trans/LLM/TTS│   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌────────────────────────┐      │
│  │ Prometheus│ │ Grafana  │ │ GPU Node 2 / 3 / 4... │      │
│  └──────────┘ └──────────┘ └────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 24.2 Advanced AI Features

| Feature | Technology | Benefit |
|---------|-----------|---------|
| RAG for lecture Q&A | Qdrant + embedding model | Students can ask questions about lectures |
| Live translation | Whisper + NLLB | Real-time multilingual subtitles |
| Automatic chapter detection | LLM segmentation | Navigation within long lectures |
| AI quiz generation | LLM | Auto-generated assessments per slide |
| Sentiment/engagement analysis | Emotion detection | Teacher feedback on lecture delivery |
| Multi-modal understanding | GPT-4o / Gemini | Leverage slide images in narration |
| Real-time slide detection | Audio + visual cues | Auto-advance slides during lecture |

### 24.3 Message Broker Evolution

```
MVP: Redis (Celery broker)
        ↓
Scale: RabbitMQ (dedicated message broker)
        ↓
Enterprise: Kafka (event sourcing, stream processing, audit log)
```

---

## 25. Development Roadmap

### Milestone 1: Foundation (Week 1-2)

**Goal:** Project scaffolding, database, authentication, and Docker setup.

**Files to Create:**
- `backend/` — All Clean Architecture structure (empty implementations)
- `frontend/` — Next.js project with routing and layout
- `infrastructure/` — Docker Compose, Nginx config
- `ai-server/` — Service stubs
- `docs/` — API documentation

**Key Deliverables:**
- `backend/main.py` — FastAPI app with health endpoint
- `backend/src/config/settings.py` — Pydantic settings
- `backend/src/infrastructure/db/models/*.py` — All SQLAlchemy models
- `backend/alembic/` — Initial migration with all tables
- `backend/src/api/routes/auth.py` — Register, login, refresh
- `backend/src/infrastructure/auth/jwt.py` — JWT implementation
- `frontend/src/app/(auth)/login/page.tsx` — Login page
- `infrastructure/docker-compose.yml` — Web services
- `infrastructure/nginx/` — Reverse proxy config

**Tests:**
- Backend: Unit tests for auth use case, DB model creation
- Frontend: Login page renders

**Deliverable:** Empty system with authentication. `docker compose up` works.

---

### Milestone 2: File Upload & Storage (Week 3-4)

**Goal:** Project management, file upload with validation, local storage.

**Files to Create:**
- `backend/src/api/routes/projects.py` — CRUD endpoints
- `backend/src/api/routes/lectures.py` — Upload endpoint
- `backend/src/api/routes/files.py` — Download endpoint
- `backend/src/api/routes/voice.py` — Voice profile CRUD
- `backend/src/core/use_cases/project/` — Project business logic
- `backend/src/core/use_cases/lecture/` — Lecture business logic
- `backend/src/infrastructure/storage/local_storage.py` — File operations
- `backend/src/infrastructure/storage/base.py` — Storage interface
- `frontend/src/app/(dashboard)/projects/` — Project list page
- `frontend/src/app/(dashboard)/lectures/` — Lecture upload page
- `frontend/src/components/upload/` — Upload component with progress

**Key Endpoints:**
- `POST /api/v1/projects` — Create project
- `POST /api/v1/lectures/upload` — Upload video/audio/pptx
- `GET /api/v1/files/{id}` — Download files
- `POST /api/v1/voice-profiles` — Upload voice sample

**Tests:**
- File upload validation (size, type, mime)
- Storage layer (store, retrieve, delete)
- Project CRUD integration tests

**Deliverable:** Users can upload files, create projects. Files stored on disk.

---

### Milestone 3: AI Server — Transcription (Week 5-6)

**Goal:** Faster-Whisper transcription service, both batch and streaming.

**Files to Create:**
- `ai-server/services/transcription/` — Full service
  - `src/api/routes.py` — POST /transcribe
  - `src/api/websocket.py` — WS /ws/transcribe
  - `src/core/transcriber.py` — Faster-Whisper wrapper
  - `src/config.py` — Service settings
  - `src/main.py` — FastAPI entry
  - `Dockerfile`
- `backend/src/infrastructure/ai_client/transcription.py` — HTTP client
- `backend/src/worker/tasks/lecture_tasks.py` — Transcribe task
- `backend/src/worker/pipeline/extract_audio.py` — ffmpeg wrapper
- `backend/src/worker/pipeline/transcribe.py` — Pipeline stage
- `frontend/src/components/player/` — Audio/video player prototype

**Key Endpoints:**
- `POST /ai/v1/transcribe` — Batch transcription
- `WS /ai/v1/ws/transcribe` — Streaming transcription
- `POST /api/v1/lectures/{id}/transcribe` — Trigger transcription

**Tests:**
- Audio extraction with ffmpeg (test with sample.mp4)
- Transcription accuracy (WER measurement)
- WebSocket streaming test

**Deliverable:** Upload video → extract audio → transcribe → return timestamped transcript.

---

### Milestone 4: AI Server — LLM Services (Week 7-8)

**Goal:** vLLM serving Qwen3, LLM service for alignment and narration.

**Files to Create:**
- `ai-server/services/llm/` — Full service
  - `src/api/routes.py` — POST /align, POST /generate-narration
  - `src/core/narration_generator.py` — Prompt builder + vLLM client
  - `src/core/slide_aligner.py` — Alignment prompt + validation
  - `src/config.py`
  - `src/main.py`
  - `Dockerfile`
- `ai-server/services/vllm/` — vLLM config (docker-compose only)
- `backend/src/infrastructure/ai_client/llm.py` — HTTP client
- `backend/src/worker/pipeline/align_transcript.py` — Alignment stage
- `backend/src/worker/pipeline/generate_narration.py` — Narration stage
- `backend/src/core/dto/` — Narration DTO with validation

**Key Endpoints:**
- `POST /ai/v1/align` — Transcript-slide alignment
- `POST /ai/v1/generate-narration` — Per-slide narration

**Tests:**
- Prompt template rendering
- LLM response parsing and validation
- Alignment accuracy on test data
- Narration quality evaluation

**Deliverable:** Pipeline now produces per-slide narration scripts.

---

### Milestone 5: AI Server — TTS & Voice Cloning (Week 9-10)

**Goal:** F5-TTS service for voice cloning and speech synthesis.

**Files to Create:**
- `ai-server/services/tts/` — Full service
  - `src/api/routes.py` — POST /tts, POST /clone-voice
  - `src/core/voice_cloner.py` — F5-TTS speaker embedding
  - `src/core/speech_synthesizer.py` — F5-TTS inference
  - `src/config.py`
  - `src/main.py`
  - `Dockerfile`
- `backend/src/infrastructure/ai_client/tts.py` — HTTP client
- `backend/src/worker/pipeline/generate_tts.py` — TTS pipeline stage

**Key Endpoints:**
- `POST /ai/v1/tts` — Text to speech
- `POST /ai/v1/clone-voice` — Voice cloning

**Tests:**
- TTS output quality assessment
- Voice cloning with test audio
- Narration-to-audio pipeline integration

**Deliverable:** Narration scripts → TTS audio files for each slide.

---

### Milestone 6: PowerPoint Embedding & Integration (Week 11-12)

**Goal:** Embed narration audio into PPTX and deliver final download.

**Files to Create:**
- `backend/src/infrastructure/pptx/parser.py` — PPTX content extraction
- `backend/src/infrastructure/pptx/narration_embedder.py` — Audio embedding
- `backend/src/worker/pipeline/parse_pptx.py` — Parse stage
- `backend/src/worker/pipeline/embed_narration.py` — Embed stage
- `backend/src/worker/tasks/narration_tasks.py` — Task orchestration
- `frontend/src/components/project/` — Project detail with download

**Key Endpoints:**
- `GET /api/v1/lectures/{id}` — Full lecture detail with narrations
- `GET /api/v1/files/{id}` — Download narrated PPTX

**Tests:**
- PPTX round-trip (parse → embed → verify audio embedded)
- Full pipeline integration test
- Download flow

**Deliverable:** Complete pipeline: upload → process → download narrated PPTX.

---

### Milestone 7: Live Lecture Recording (Week 13-14)

**Goal:** Browser-based live lecture recording with real-time transcription.

**Files to Create:**
- `backend/src/api/websockets/lecture.py` — Live lecture WebSocket handler
- `frontend/src/hooks/useAudioRecorder.ts` — MediaRecorder hook
- `frontend/src/hooks/useWebSocket.ts` — WebSocket hook
- `frontend/src/app/lecture/[id]/` — Live lecture page
- `frontend/src/components/lecture/` — Recording UI, transcript display

**Key Endpoints:**
- `POST /api/v1/lectures/live/start` — Create live session
- `WS /api/v1/ws/lecture/{id}` — Audio streaming
- `POST /api/v1/lectures/live/{id}/stop` — Finalize recording

**Tests:**
- WebSocket connection and reconnection
- Audio chunking and streaming
- Partial transcript recovery

**Deliverable:** Live lecture recording with real-time transcription display.

---

### Milestone 8: Dashboard & Polish (Week 15-16)

**Goal:** Full-feature dashboard, progress tracking, error handling, monitoring.

**Files to Create/Update:**
- `frontend/src/app/(dashboard)/` — All dashboard pages
- `frontend/src/components/project/` — Project cards, status badges
- `backend/src/worker/pipeline/` — Error handling improvements
- `infrastructure/monitoring/` — Prometheus, Grafana, Loki

**Features:**
- Real-time pipeline progress via WebSocket
- Job history and status dashboard
- Error recovery and retry UI
- Monitoring stack deployment
- Configuration via admin panel (future)

**Tests:**
- E2E: Upload → Process → Download (full flow)
- Error scenarios (corrupt file, model failure, disk full)
- Load test with concurrent uploads

**Deliverable:** Production-ready system with monitoring.

---

### Milestone 9: Optimization & Scale Prep (Week 17-18)

**Goal:** Performance optimization, caching, security audit.

**Tasks:**
- Redis caching for frequently accessed data
- Database query optimization (indexes, connection pooling)
- CDN integration for file downloads
- Security audit (penetration testing)
- Rate limiting fine-tuning
- GPU memory optimization (model quantization)
- Batch TTS processing (parallel per-slide generation)

---

### Milestone 10: Production Launch (Week 19-20)

**Goal:** Production deployment, documentation, handover.

**Tasks:**
- Production environment setup
- SSL certificate configuration
- Backup verification
- Monitoring alerts configuration
- User documentation
- API documentation (auto-generated from OpenAPI)
- Deployment runbook
- Rollback procedures
- Performance benchmarks

---

### Summary Timeline

```
Week 1-2:   Foundation (auth, DB, Docker)
Week 3-4:   File upload & storage
Week 5-6:   Transcription service
Week 7-8:   LLM services (alignment, narration)
Week 9-10:  TTS & voice cloning
Week 11-12: PPTX embedding & integration
Week 13-14: Live lecture recording
Week 15-16: Dashboard & polish
Week 17-18: Optimization & scaling prep
Week 19-20: Production launch
```

Each milestone includes: working code, passing tests, and deployable Docker containers. No milestone depends on a later milestone.

