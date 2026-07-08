# AI Lecture Narration Platform — Complete Specification

## 1. Architecture

```
┌─────────────────────┐     ┌──────────────────────────┐
│   Machine A         │     │   Machine B              │
│   (App Server)      │     │   (GPU / AI Server)      │
│                     │     │                          │
│  ┌───────────────┐  │     │  ┌────────────────────┐  │
│  │  Next.js 14    │  │     │  │  GPU Service       │  │
│  │  Frontend      │  │     │  │  (port 8001)       │  │
│  │  (port 3000)   │  │     │  │  ─ Faster-Whisper  │  │
│  └───────┬───────┘  │     │  │  ─ BGE-M3          │  │
│          │          │     │  │  ─ F5-TTS          │  │
│          ▼          │     │  │  ─ SGLang proxy    │  │
│  ┌───────────────┐  │     │  └────────────────────┘  │
│  │  FastAPI       │  │     │                          │
│  │  Backend       │  │     │  ┌────────────────────┐  │
│  │  (port 8000)   │  │     │  │  SGLang            │  │
│  └───────┬───────┘  │     │  │  (port 30000)       │  │
│          │          │     │  │  ─ Qwen3-8B         │  │
│          ▼          │     │  └────────────────────┘  │
│  ┌───────────────┐  │     └──────────────────────────┘
│  │  PostgreSQL   │  │
│  │  (port 5432)  │  │
│  └───────────────┘  │
│                     │
│  ┌───────────────┐  │
│  │  Redis         │  │
│  │  (port 6379)   │  │
│  └───────────────┘  │
│          │          │
│          ▼          │
│  ┌───────────────┐  │
│  │  Celery        │  │
│  │  Worker        │  │
│  └───────────────┘  │
└─────────────────────┘
```

### Deployment modes
- **Docker**: `infrastructure/docker-compose.yml` + `docker-compose.ai.yml` (GPU server)
- **Direct (no Docker)**: `uvicorn backend.main:app` + `celery worker` + `npx next start`
- **Start script**: `./start.sh` launches all 3 processes on Machine A

---

## 2. Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Next.js | 14.2 |
| Frontend | React | 18 |
| Frontend | TypeScript | 5.x |
| Frontend | Tailwind CSS | 3.x |
| Frontend | shadcn/ui | latest |
| Frontend | Lucide Icons | latest |
| Backend | Python | 3.12 |
| Backend | FastAPI | 0.115+ |
| Backend | SQLAlchemy | 2.0+ (async + sync) |
| Backend | Alembic | 1.13+ |
| Backend | Pydantic | 2.9+ |
| Backend | Celery | 5.4+ |
| Backend | Redis | (broker + result backend) |
| Backend | PostgreSQL | 16+ |
| Backend | JWT (PyJWT) | 2.9+ |
| Backend | httpx | 0.27+ |
| AI (GPU) | Faster-Whisper | large-v3 |
| AI (GPU) | BGE-M3 (sentence-transformers) | latest |
| AI (GPU) | F5-TTS | latest |
| AI (GPU) | SGLang + Qwen3-8B | latest |
| AI (GPU) | CTranslate2 | (Whisper backend) |

---

## 3. Backend — Directory Structure

```
backend/
├── main.py                          # FastAPI app entry point
├── requirements.txt                 # Python dependencies
├── alembic.ini                      # Alembic config
├── alembic/
│   └── versions/
│       └── 0001_initial_schema.py   # All 9 tables
│
├── src/
│   ├── config/
│   │   ├── settings.py              # All env vars (72 lines)
│   │   └── logging.py               # Structured logging (structlog)
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── auth.py              # /api/v1/auth/*
│   │   │   ├── projects.py          # /api/v1/projects/*
│   │   │   ├── lectures.py          # /api/v1/lectures/*
│   │   │   ├── voice.py             # /api/v1/voice-profiles/*
│   │   │   ├── files.py             # /api/v1/files/*
│   │   │   └── health.py            # /api/v1/health
│   │   ├── dependencies/
│   │   │   ├── auth.py              # get_current_user JWT validation
│   │   │   └── providers.py         # get_storage(), get_settings()
│   │   ├── errors/
│   │   │   └── handlers.py          # Error classes + exception handlers
│   │   └── middleware/
│   │       ├── logging.py           # Request/response logging
│   │       └── cors.py              # CORS config
│   │
│   ├── core/
│   │   ├── dto/
│   │   │   ├── auth.py              # LoginRequest, TokenResponse, etc.
│   │   │   ├── project.py           # ProjectResponse, ProjectDetailResponse, LectureSummary
│   │   │   ├── lecture.py           # UploadLectureResponse, LectureDetailResponse, LectureStatusResponse
│   │   │   └── voice.py             # VoiceProfileResponse
│   │   ├── ports/
│   │   │   └── storage.py           # StoragePort abstract interface
│   │   └── use_cases/
│   │       ├── auth/
│   │       │   ├── login.py         # Authenticate user, return JWT
│   │       │   └── register.py      # Create user account
│   │       ├── project/
│   │       │   ├── create_project.py
│   │       │   ├── get_project.py   # Returns lectures included
│   │       │   ├── list_projects.py # Paginated
│   │       │   ├── update_project.py
│   │       │   └── delete_project.py
│   │       ├── lecture/
│   │       │   ├── upload_lecture.py # Upload + dispatch Celery task
│   │       │   ├── get_lecture.py
│   │       │   └── get_lecture_status.py
│   │       └── voice/
│   │           ├── create_voice_profile.py
│   │           ├── list_voice_profiles.py
│   │           └── delete_voice_profile.py
│   │
│   ├── infrastructure/
│   │   ├── db/
│   │   │   ├── session.py           # Async + sync session factories
│   │   │   ├── models/
│   │   │   │   ├── base.py          # DeclarativeBase + TimestampMixin
│   │   │   │   ├── user.py          # UserModel
│   │   │   │   ├── project.py       # ProjectModel (with lectures relationship)
│   │   │   │   ├── lecture.py       # LectureModel
│   │   │   │   ├── slide.py         # SlideModel
│   │   │   │   ├── transcript_segment.py  # TranscriptSegmentModel
│   │   │   │   ├── narration.py     # NarrationModel
│   │   │   │   ├── job.py           # JobModel
│   │   │   │   ├── file_record.py   # FileModel
│   │   │   │   └── voice_profile.py # VoiceProfileModel
│   │   │   └── repositories/
│   │   │       ├── base.py          # BaseRepository (async CRUD)
│   │   │       ├── user_repo.py
│   │   │       ├── project_repo.py  # selectinload(lectures)
│   │   │       ├── lecture_repo.py
│   │   │       ├── job_repo.py
│   │   │       └── slide_repo.py
│   │   ├── auth/
│   │   │   ├── jwt.py               # create/verify access + refresh tokens
│   │   │   └── password.py          # bcrypt hash + verify
│   │   └── storage/
│   │       └── local_storage.py     # LocalStorage + StoragePaths
│   │
│   ├── worker/
│   │   ├── celery_app.py            # Celery app config + queue setup
│   │   ├── tasks/
│   │   │   └── lecture_tasks.py     # process_lecture_pipeline task
│   │   └── pipeline/
│   │       ├── orchestrator.py      # run_full_pipeline (8 stages)
│   │       ├── extract_audio.py     # Stage 1: FFmpeg
│   │       ├── transcribe.py        # Stage 2: Whisper via GPU service
│   │       ├── parse_pptx.py        # Stage 3: python-pptx
│   │       ├── generate_embeddings.py  # Stage 4: BGE-M3 via GPU service
│   │       ├── align_transcript.py  # Stage 5: BGE-M3 + Qwen via GPU/SGLang
│   │       ├── generate_narration.py   # Stage 6: Qwen via GPU/SGLang
│   │       ├── generate_tts.py      # Stage 7: F5-TTS via GPU service
│   │       └── embed_narration.py   # Stage 8: python-pptx audio embed
│   │
│   └── ai_client/                   # (alternative AI client wrappers)
│       ├── embedding.py
│       ├── llm.py
│       ├── transcription.py
│       └── tts.py
```

---

## 4. API Endpoints (17 total)

### Auth (`/api/v1/auth`)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/auth/register` | Create account | No |
| POST | `/api/v1/auth/login` | Login → JWT pair | No |
| POST | `/api/v1/auth/refresh` | Refresh access token | No |
| GET | `/api/v1/auth/me` | Get current user | Yes |

### Projects (`/api/v1/projects`)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/projects` | List user's projects (paginated) | Yes |
| POST | `/api/v1/projects` | Create project | Yes |
| GET | `/api/v1/projects/{id}` | Project detail + lectures list | Yes |
| PUT | `/api/v1/projects/{id}` | Update project | Yes |
| DELETE | `/api/v1/projects/{id}` | Delete project + all data | Yes |

### Lectures (`/api/v1/lectures`)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/lectures/upload` | Upload + dispatch pipeline | Yes |
| GET | `/api/v1/lectures/{id}` | Lecture detail + slides + narrations | Yes |
| GET | `/api/v1/lectures/{id}/status` | Pipeline progress + job status | Yes |

### Voice Profiles (`/api/v1/voice-profiles`)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/voice-profiles` | List user's voice profiles | Yes |
| POST | `/api/v1/voice-profiles` | Create voice profile | Yes |
| DELETE | `/api/v1/voice-profiles/{id}` | Delete voice profile | Yes |

### Files (`/api/v1/files`)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/files/{id}` | Download stored file | Yes |

### Health (`/api/v1`)
| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/health` | Server health + DB check | No |

---

## 5. Database Schema (9 tables)

### `users`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| email | VARCHAR(255) | NOT NULL, UNIQUE INDEX |
| password_hash | VARCHAR(255) | NOT NULL |
| full_name | VARCHAR(255) | NOT NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

### `projects`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users, CASCADE, INDEX |
| title | VARCHAR(255) | NOT NULL |
| description | TEXT | NULLABLE |
| status | VARCHAR(50) | DEFAULT 'active' |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

### `voice_profiles`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users, CASCADE, INDEX |
| name | VARCHAR(255) | NOT NULL |
| sample_audio_path | VARCHAR(500) | NOT NULL |
| status | VARCHAR(50) | DEFAULT 'pending' |
| speaker_id | VARCHAR(100) | NULLABLE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

### `lectures`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| project_id | UUID | FK → projects, CASCADE, INDEX |
| title | VARCHAR(255) | NOT NULL |
| input_type | VARCHAR(20) | NOT NULL ('video'/'audio'/'live') |
| status | VARCHAR(50) | DEFAULT 'pending', INDEX |
| video_path | VARCHAR(500) | NULLABLE |
| audio_path | VARCHAR(500) | NULLABLE |
| pptx_path | VARCHAR(500) | NULLABLE |
| narrated_pptx_path | VARCHAR(500) | NULLABLE |
| duration_seconds | INTEGER | NULLABLE |
| error_message | TEXT | NULLABLE |
| voice_profile_id | UUID | FK → voice_profiles, SET NULL |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

### `slides`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| lecture_id | UUID | FK → lectures, CASCADE, INDEX |
| slide_number | INTEGER | NOT NULL |
| raw_text | TEXT | NULLABLE |
| notes | TEXT | NULLABLE |
| image_path | VARCHAR(500) | NULLABLE |
| slide_layout | VARCHAR(100) | NULLABLE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| **UNIQUE** | (lecture_id, slide_number) | uq_lecture_slide |

### `transcript_segments`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| lecture_id | UUID | FK → lectures, CASCADE, INDEX |
| slide_id | UUID | FK → slides, SET NULL, INDEX |
| segment_number | INTEGER | NOT NULL |
| start_time | FLOAT | NOT NULL |
| end_time | FLOAT | NOT NULL |
| text | TEXT | NOT NULL |
| confidence | FLOAT | NULLABLE |
| speaker | VARCHAR(100) | NULLABLE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| **UNIQUE** | (lecture_id, segment_number) | uq_lecture_segment |

### `narrations`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| slide_id | UUID | FK → slides, CASCADE |
| lecture_id | UUID | FK → lectures, CASCADE, INDEX |
| script_text | TEXT | NOT NULL |
| audio_path | VARCHAR(500) | NULLABLE |
| duration_seconds | FLOAT | NULLABLE |
| status | VARCHAR(50) | DEFAULT 'pending' |
| model_used | VARCHAR(100) | NULLABLE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

### `jobs`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| lecture_id | UUID | FK → lectures, CASCADE, INDEX |
| job_type | VARCHAR(50) | NOT NULL |
| status | VARCHAR(50) | DEFAULT 'pending', INDEX |
| progress | FLOAT | DEFAULT 0.0 |
| payload | JSONB | NULLABLE |
| result | JSONB | NULLABLE |
| error_message | TEXT | NULLABLE |
| celery_id | VARCHAR(255) | NULLABLE, INDEX |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| started_at | TIMESTAMPTZ | NULLABLE |
| completed_at | TIMESTAMPTZ | NULLABLE |

### `files`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users, CASCADE, INDEX |
| lecture_id | UUID | FK → lectures, SET NULL, INDEX |
| file_type | VARCHAR(50) | NOT NULL |
| original_name | VARCHAR(500) | NOT NULL |
| storage_path | VARCHAR(500) | NOT NULL |
| mime_type | VARCHAR(100) | NULLABLE |
| file_size_bytes | BIGINT | NULLABLE |
| checksum_sha256 | VARCHAR(64) | NULLABLE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

---

## 6. Pipeline Stages (8 stages, sequential)

| # | Stage | Module | What it does | Duration estimate |
|---|-------|--------|-------------|-------------------|
| 1 | Extract Audio | `extract_audio.py` | FFmpeg: video → 16kHz mono WAV | 10% (skip if audio already uploaded) |
| 2 | Transcribe | `transcribe.py` | Whisper → timestamped segments | 25% |
| 3 | Parse PPTX | `parse_pptx.py` | python-pptx → slide text + notes | 10% |
| 4 | Generate Embeddings | `generate_embeddings.py` | BGE-M3 → vectors for slide + transcript | 5% |
| 5 | Align Transcript | `align_transcript.py` | BGE-M3 similarity + Qwen LLM verification → segment→slide mapping | 15% |
| 6 | Generate Narration | `generate_narration.py` | Qwen → per-slide narration scripts | 15% |
| 7 | Generate TTS | `generate_tts.py` | F5-TTS → per-slide WAV audio | 15% |
| 8 | Embed Narration | `embed_narration.py` | python-pptx → audio embedded in PPTX | 5% |

### Pipeline progress tracking
- Each stage has a weight (total = 100%)
- Progress stored in `JobModel.progress` field
- Status transitions: `pending` → `processing` → `completed` / `failed`
- Each stage creates a `JobModel` entry with `job_type = stage_name`
- Celery task has `max_retries=3`, exponential backoff, `acks_late=True`
- All stages run in a single sync DB transaction (rollback on failure)

### GPU Service endpoints (Machine B, port 8001)

| Endpoint | Method | Model | Purpose |
|----------|--------|-------|---------|
| `/ai/v1/health` | GET | — | Service health + all model statuses |
| `/ai/v1/transcribe` | POST | Faster-Whisper | Audio → text segments |
| `/ai/v1/embed` | POST | BGE-M3 | Text → embedding vectors |
| `/ai/v1/dimensions` | GET | BGE-M3 | Get embedding dimension |
| `/ai/v1/align` | POST | Qwen (via SGLang) | Transcript → slide alignment |
| `/ai/v1/generate-narration` | POST | Qwen (via SGLang) | Slide → narration script |
| `/ai/v1/tts` | POST | F5-TTS | Text → WAV audio (currently returns silence) |
| `/ai/v1/clone-voice` | POST | F5-TTS | Audio sample → voice ID |

GPU service internal LLM calls go to `LLM_API_URL` (default `http://localhost:30000/v1`, SGLang).

---

## 7. Frontend — Routes & Pages

| Route | Page | Description |
|-------|------|-------------|
| `/auth/login` | `login/page.tsx` | Login form → JWT stored in zustand persist |
| `/auth/register` | `register/page.tsx` | Registration form |
| `/dashboard` | `(dashboard)/dashboard/page.tsx` | Project list + stats overview |
| `/projects/{id}` | `(dashboard)/projects/[id]/page.tsx` | Project detail → shows lectures list |
| `/lectures/upload` | `(dashboard)/lectures/upload/page.tsx` | Upload form (audio/video + optional PPTX) |

### Frontend components
```
frontend/src/
├── app/
│   ├── auth/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   └── (dashboard)/
│       ├── layout.tsx              # Sidebar + header shell
│       ├── dashboard/page.tsx
│       ├── projects/[id]/page.tsx
│       └── lectures/upload/page.tsx
├── components/
│   ├── layout/
│   │   ├── Header.tsx
│   │   ├── Sidebar.tsx
│   │   └── AuthGuard.tsx           # Redirects to /auth/login if no token
│   └── ui/                         # shadcn/ui components
│       ├── button.tsx
│       ├── input.tsx
│       ├── card.tsx
│       ├── badge.tsx
│       └── skeleton.tsx
├── lib/
│   ├── api/
│   │   ├── client.ts              # Axios instance + interceptor (JWT refresh)
│   │   ├── auth.ts
│   │   ├── projects.ts
│   │   └── lectures.ts
│   └── utils.ts                   # cn() helper
├── stores/
│   └── authStore.ts               # Zustand persist (user, tokens, isAuthenticated)
└── types/
    ├── auth.ts
    ├── project.ts                  # Project, ProjectDetail (extends Project + lectures)
    └── lecture.ts                  # LectureSummary, LectureDetail, LectureStatus, etc.
```

### Frontend auth flow
1. Login → stores `accessToken` + `refreshToken` in zustand persist (localStorage)
2. `apiClient` interceptor attaches `Authorization: Bearer <token>` header
3. On 401 → interceptor calls `/api/v1/auth/refresh` using stored `refreshToken`
4. If refresh fails → redirect to `/auth/login`, clear storage

---

## 8. Configuration & Environment Variables

### `backend/src/config/settings.py` — all env vars:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `"AI Lecture Narrator"` | |
| `APP_VERSION` | `"1.0.0"` | |
| `ENVIRONMENT` | `"development"` | |
| `DEBUG` | `false` | Enables debug logging, /docs, /redoc |
| `DATABASE_URL` | `"postgresql+asyncpg://postgres:postgres@localhost:5432/lecture_narrator"` | Async DB URL |
| `DB_POOL_SIZE` | `10` | |
| `DB_MAX_OVERFLOW` | `20` | |
| `REDIS_URL` | `"redis://localhost:6379/0"` | Celery broker |
| `REDIS_RESULT_URL` | `"redis://localhost:6379/1"` | Celery result backend |
| `JWT_SECRET_KEY` | auto-generated | |
| `JWT_ACCESS_EXPIRE_MINUTES` | `60` | |
| `JWT_REFRESH_EXPIRE_DAYS` | `30` | |
| `AI_SERVICE_URL` | `"http://gpu-service:8001"` | GPU service endpoint |
| `AI_TRANSCRIPTION_URL` | `"http://transcription:8001"` | (legacy, kept for compat) |
| `AI_LLM_URL` | `"http://llm:8002"` | (legacy, kept for compat) |
| `AI_TTS_URL` | `"http://tts:8003"` | (legacy, kept for compat) |
| `AI_API_KEY` | `""` | |
| `STORAGE_BACKEND` | `"local"` | |
| `STORAGE_ROOT` | `"data/storage"` | Relative to project root |
| `DATA_DIR` | `"data"` | |
| `VOICE_EMBEDDINGS_DIR` | `"data/voice_embeddings"` | |
| `MAX_VIDEO_SIZE_BYTES` | `2 * 1024**3` (2GB) | |
| `MAX_AUDIO_SIZE_BYTES` | `500 * 1024**2` (500MB) | |
| `MAX_PPTX_SIZE_BYTES` | `200 * 1024**2` (200MB) | |

---

## 9. Storage Layout

All paths are relative to `STORAGE_ROOT` (default `data/storage/`).

```
data/storage/
├── projects/{project_id}/lectures/{lecture_id}/
│   ├── source/
│   │   ├── video.mp4              # Original video upload
│   │   ├── audio.mp3              # Original audio upload
│   │   └── slides.pptx            # Original PPTX upload
│   ├── audio/
│   │   └── extracted.wav          # Stage 1: audio extracted from video
│   ├── audio_narrations/
│   │   ├── slide_001.wav          # Stage 7: TTS per slide
│   │   ├── slide_002.wav
│   │   └── ...
│   └── output/
│       └── narrated_lecture.pptx  # Stage 8: final narrated PPTX

data/voice_embeddings/             # Speaker embeddings for voice cloning
data/cache/                        # HuggingFace model cache
```

---

## 10. Celery Configuration

| Setting | Value |
|---------|-------|
| Broker | Redis `redis://localhost:6379/0` |
| Backend | Redis `redis://localhost:6379/1` |
| Concurrency | 2 (prefork) |
| Task serializer | JSON |
| Result serializer | JSON |
| Task tracking | `task_track_started=True` |
| Late acks | `task_acks_late=True` |
| Prefetch | `worker_prefetch_multiplier=1` |
| Result expiry | 7 days |
| Queue names | `default`, `audio`, `transcription`, `llm`, `tts`, `pptx`, `priority_high` |
| Default queue | `default` |

### Queues by pipeline stage
| Queue | Used by |
|-------|---------|
| `default` | Full pipeline task (dispatched from upload) |
| `audio` | Stage 1: extract_audio |
| `transcription` | Stage 2: transcribe |
| `pptx` | Stage 3: parse_pptx |
| `llm` | Stages 5-6: alignment + narration |
| `tts` | Stage 7: TTS |

### Celery task: `process_lecture_pipeline`
- `bind=True` (access to `self.request.retries`)
- `max_retries=3`
- `default_retry_delay=30`
- `exponential_backoff=2` (30s → 60s → 120s)
- `acks_late=True` (task re-delivered if worker crashes)
- `reject_on_worker_lost=True`

---

## 11. Error Handling

### Custom exception classes (in `handlers.py`)
| Exception | HTTP Status | Usage |
|-----------|-------------|-------|
| `BadRequestError` | 400 | Invalid input |
| `UnauthorizedError` | 401 | Bad credentials |
| `ForbiddenError` | 403 | Wrong user |
| `NotFoundError` | 404 | Entity not found |
| `ConflictError` | 409 | Duplicate |
| `UnsupportedFileTypeError` | 415 | Wrong file format |
| `FileTooLargeError` | 413 | File exceeds limit |

### Pipeline error handling
- Each stage wrapped in try/except
- On failure: `lecture.status = "failed"`, `lecture.error_message = str(e)`
- Job record updated with `status = "failed"` + `error_message`
- Celery task catches exception → `self.retry(exc=exc)` (up to 3 retries)
- After retries exhausted → job stays `failed`, user sees error in UI

---

## 12. Infrastructure Files

| File | Purpose |
|------|---------|
| `infrastructure/docker-compose.yml` | App server stack (backend + frontend + PostgreSQL + Redis + Nginx) |
| `infrastructure/docker-compose.ai.yml` | GPU server stack (GPU service + SGLang) |
| `infrastructure/nginx.conf` | Reverse proxy config |
| `start.sh` | Launch backend + Celery + frontend directly (no Docker) |
| `DEPLOY_APP_SERVER.md` | Production Ubuntu setup guide (systemd, Nginx, PostgreSQL, Redis, Tailscale) |
| `SETUP.md` | Development setup guide |
| `scripts/run_pipeline.sh` | Manually trigger pipeline for an existing lecture |
| `.env.example` | Environment variable template |

---

## 13. AI Server (Machine B) — GPU Service

### `ai-server/service/src/main.py` (429 lines)

Single FastAPI app loading all models at startup:

| Model | Config Env Var | Default | Device Fallback |
|-------|---------------|---------|----------------|
| Faster-Whisper | `WHISPER_MODEL_SIZE` | `large-v3` | CUDA → CPU (int8) |
| BGE-M3 | `EMBEDDING_MODEL` | `BAAI/bge-m3` | CUDA → CPU |
| F5-TTS | `TTS_MODEL_PATH` | `SWivid/F5-TTS` | CUDA → CPU |
| SGLang | `LLM_API_URL` | `http://localhost:30000/v1` | External process |

SGLang starts separately:
```
sglang serve --model-path Qwen/Qwen3-8B --host 0.0.0.0 --port 30000
```

---

## 14. Logging Configuration

| Logger | Level | Notes |
|--------|-------|-------|
| Root (FastAPI) | DEBUG if `DEBUG=true`, else WARNING | |
| Root (Celery worker) | INFO (set by `-l INFO`) | |
| `sqlalchemy.engine.Engine` | WARNING | Silences SQL queries |
| `sqlalchemy.pool` | WARNING | Silences pool chatter |
| `httpx` | WARNING | Silences HTTP request logs |
| `alembic` | WARNING | Silences migration logs |
| `celery` | WARNING | Silences heartbeat/utility logs |
| `uvicorn.access` | WARNING | Silences HTTP access logs |
| `uvicorn.error` | WARNING | |

Pipeline progress uses `logger.info()` — visible in Celery worker stdout.

---

## 15. Security

- **Passwords**: bcrypt hashing via `passlib[bcrypt]`
- **JWT**: HS256, access token (60min) + refresh token (30 days)
- **DB passwords with `%`**: ConfigParser interpolation avoided by injecting URL directly into engine config
- **File upload validation**: Extension whitelist (`.mp4`, `.mov`, `.mkv`, `.webm` / `.mp3`, `.wav`, `.m4a`, `.aac`, `.ogg` / `.pptx`)
- **File size limits**: Video 2GB, Audio 500MB, PPTX 200MB
- **Path traversal protection**: `LocalStorage._resolve()` checks resolved path stays under root
- **Auth middleware**: All routes except `/auth/*` and `/health` require valid JWT
- **User scoping**: All queries filtered by `user_id` — users can't access each other's data

---

## 16. Dependencies

### Backend (`requirements.txt`)
```
fastapi, uvicorn, sqlalchemy, asyncpg, psycopg2-binary, alembic,
pydantic, pydantic-settings, passlib[bcrypt], bcrypt, python-multipart,
redis, celery[redis], aiofiles, python-pptx, httpx, tenacity,
python-dotenv, email-validator, structlog, PyJWT, pytest, pytest-asyncio,
pytest-cov, ruff, aiosqlite, numpy
```

### Frontend (`package.json`)
```
next, react, react-dom, typescript, tailwindcss, postcss, autoprefixer,
axios, zustand, lucide-react, @radix-ui/*, class-variance-authority,
clsx, tailwind-merge, tailwindcss-animate
```

### AI Service (`ai-server/service/requirements.txt`)
```
fastapi, uvicorn, faster-whisper, sentence-transformers, httpx,
numpy, pydantic, python-multipart, aiofiles
```
