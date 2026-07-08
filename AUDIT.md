# Voice PPT — Complete Engineering Audit

---

## 1. Repository Overview

This is an **AI Lecture Narration Platform** that takes lecture recordings (video/audio) + optional PowerPoint slides, transcribes the audio, aligns the transcript to slides, generates AI narration scripts, converts them to speech via TTS, and embeds the narration audio back into the PPTX. Two-machine architecture: an **App Server** (FastAPI + Next.js + Postgres + Redis + Celery) and a **GPU Server** (Whisper + BGE-M3 + SGLang/Qwen + F5-TTS).

---

## 2. Directory Map

| Folder | Responsibility | Status |
|---|---|---|
| `backend/` | FastAPI app with Clean Architecture layers | 🟡 Partial |
| `backend/src/api/` | Routes, dependencies, middleware, error handlers | ✅ Mostly done |
| `backend/src/core/` | Use cases, DTOs, ports, domain entities | 🟡 Partial |
| `backend/src/infrastructure/` | DB models/repos, auth (JWT/bcrypt), storage, AI clients | 🟡 Partial |
| `backend/src/worker/` | Celery app, tasks, pipeline (8 stages) | 🟡 Partial |
| `frontend/` | Next.js 14 App Router frontend | 🟡 Partial |
| `ai-server/service/` | GPU inference server (FastAPI) | 🟡 Partial |
| `infrastructure/` | Docker Compose, Nginx, Makefile | 🟡 Partial |
| `scripts/` | Utility scripts (pipeline runner) | 🟢 Partial |
| `data/` | Runtime data (gitignored) | N/A |

---

## 3. Broken Components Report

### CRITICAL

#### C1. Docker container will not start (backend)
- **Files**: `backend/Dockerfile` (line 17), `backend/main.py` (lines 5-15)
- **Issue**: Dockerfile runs `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]` from `/app` (which maps to `backend/`). But `main.py` uses `from backend.src.*` imports. The `backend` package is not importable from within `backend/` because there's no `PYTHONPATH` set and `backend` isn't installed as a pip package.
- **Expected**: Container starts and serves the API.
- **Root cause**: The Docker working directory is `backend/` but imports are `backend.src.*` (package-qualified). `uvicorn main:app` treats `main.py` as a module, not a package member. `backend.src.*` requires `backend` to be on `sys.path`.
- **Impact**: Backend container **will not start**. Full production block.
- **Fix**: Set `PYTHONPATH=/app/..` or install the package with `pip install -e .`

#### C2. TTS produces silence (not speech)
- **Files**: `ai-server/service/src/main.py` lines 354-368
- **Issue**: The `/ai/v1/tts` endpoint generates silence (`b"\x00\x00" * num_samples`) instead of actual speech. The F5-TTS model import is commented out (`# from f5_tts.model import DiT`). The `_load_tts()` function returns a config dict `{"path": ..., "device": ..., "sample_rate": ...}` without actually loading any model.
- **Expected**: TTS endpoint returns actual synthesized speech audio from narration text.
- **Root cause**: F5-TTS was never integrated. The endpoint is a placeholder that estimates duration from word count and generates a silence WAV of that duration.
- **Impact**: **All narrated PPTX files will contain silence.** Core feature completely broken.
- **Fix**: Implement actual F5-TTS inference, or use a different TTS provider.

#### C3. Embed_narration_into_pptx uses wrong API (adds video shapes, not audio)
- **Files**: `backend/src/worker/pipeline/embed_narration.py` lines 72-82
- **Issue**: Uses `slide.shapes.add_movie(audio_path, 0, 0, 1, 1)` which (a) creates a video shape, not an audio shape, (b) stores an **external file reference** (the absolute server path) rather than embedding the audio data, and (c) won't play correctly in PowerPoint since it requires the file at that exact absolute path.
- **Expected**: Audio files are embedded into PPTX slides and play automatically on slide entry.
- **Root cause**: `python-pptx` doesn't natively support embedding audio via a simple API. Adding via `add_movie` creates a video relation.
- **Impact**: **Narrated PPTX output is broken.** Audio won't play when the file is opened.
- **Fix**: Use `python-pptx`'s low-level relationship API to add audio media, or use a ZIP/OpenXML manipulation approach.

#### C4. Frontend API URL has double `/api` prefix in Docker
- **Files**: `infrastructure/docker-compose.yml` (line 28), `infrastructure/nginx/sites/default.conf`
- **Issue**: `NEXT_PUBLIC_API_URL=http://localhost:80/api` and frontend's `client.ts` prepends this to paths like `/api/v1/auth/login`, resulting in `http://localhost:80/api/api/v1/auth/login`. Nginx proxies `/api/` to backend, so the backend receives `/api/api/v1/...` which doesn't match any route.
- **Expected**: API calls reach the backend at `/api/v1/...`
- **Root cause**: `NEXT_PUBLIC_API_URL` includes `/api` but the frontend API paths also start with `/api/v1/...`
- **Impact**: **All API calls from the frontend will return 404 in Docker deployment.**
- **Fix**: Set `NEXT_PUBLIC_API_URL=http://localhost:80` (remove `/api`)

#### C5. AI Port interfaces defined but never used
- **Files**: `backend/src/core/ports/ai.py` (191 lines, 4 abstract classes), `backend/src/infrastructure/ai_client/` (5 files)
- **Issue**: `TranscriptionPort`, `EmbeddingPort`, `LLMPort`, `TTSPort` and their implementations (`TranscriptionClient`, `EmbeddingClient`, `LLMClient`, `TTSClient`) are **never imported or instantiated anywhere**. The pipeline stages (`transcribe.py`, `generate_embeddings.py`, `align_transcript.py`, `generate_narration.py`, `generate_tts.py`) all make direct `httpx.post()` calls instead of using the port abstractions.
- **Expected**: Clean Architecture dependency inversion — pipeline stages should depend on ports, not on HTTP details.
- **Root cause**: The abstractions were designed but never wired into the pipeline.
- **Impact**: Tight coupling to HTTP transport. Testing requires mocking HTTP calls instead of injecting test ports. Violates the declared architecture.
- **Fix**: Inject port implementations into pipeline stages, make stages depend on ports via DI.

#### C6. Dead endpoint URLs in lecture detail response
- **Files**: `backend/src/core/use_cases/lecture/get_lecture.py` lines 86-91
- **Issue**: `transcript_url` is hardcoded to `/api/v1/transcripts/{lecture_id}` — **no such endpoint exists**. `narrated_pptx_url` is hardcoded to `/api/v1/files/download/{lecture_id}` — **no such endpoint exists** (the actual download endpoint is `/api/v1/files/{file_id}`).
- **Expected**: URLs should point to real endpoints that return the actual content.
- **Root cause**: These were written as planned, not as implemented.
- **Impact**: Frontend links to transcripts and narrated PPTXs will 404.
- **Fix**: Create the missing endpoints or fix the URLs to point to existing `/api/v1/files/{file_id}`.

#### C7. `audio_url` uses narration ID instead of file ID
- **Files**: `backend/src/core/use_cases/lecture/get_lecture.py` line 82
- **Issue**: `audio_url` is set to `/api/v1/files/{narration_id}` but the file download endpoint expects a `FileModel` ID, not a `NarrationModel` ID. Narration audio files are never registered in the `files` table.
- **Expected**: Audio download URL should resolve to the actual file.
- **Root cause**: No file record is created for narration audio files during the pipeline.
- **Impact**: Audio play links in the frontend will 404 after pipeline completion.
- **Fix**: Create FileModel records for narration audio during TTS stage, or create a dedicated narration audio download endpoint.

#### C8. In-memory embedding cache loses data between stages
- **Files**: `backend/src/worker/pipeline/generate_embeddings.py` line 22
- **Issue**: `_EMBEDDING_CACHE: dict[str, list[float]] = {}` is module-level. In the orchestrator, Stage 4 calls `generate_embeddings(all_texts)` and **discards the results** (the return value is not captured). Stage 5 calls `generate_embeddings()` again internally to recompute the same embeddings.
- **Expected**: Embedding results from stage 4 should be persisted or passed to stage 5.
- **Root cause**: Orchestrator doesn't pass embeddings between stages.
- **Impact**: Embeddings are computed twice per pipeline execution. Cache only helps within a single Python process if the Celery worker stays alive.
- **Fix**: Persist embeddings to the database, or pass them through pipeline context.

### HIGH

#### H1. `get_optional_user()` nullable request parameter risk
- **Files**: `backend/src/api/dependencies/auth.py` line 59
- **Issue**: `request: Request = None` — parameter can be `None`, and function accesses `request.headers` on line 66 after the guard check `if request else None`. Actually guarded, but `request: Request = None` is not valid FastAPI DI default for a `Request` parameter — FastAPI won't inject `None`, it will fail to resolve the dependency if the caller doesn't have a request context.
- **Impact**: Calling `get_optional_user` outside of a request context (e.g., from background tasks) would fail.
- **Fix**: Make `request` an explicit optional using proper FastAPI `Request` injection pattern.

#### H2. Orchestrator Stage 3 scope issue — `slides_data` may be undefined
- **Files**: `backend/src/worker/pipeline/orchestrator.py` lines 149-167
- **Issue**: `slides_data` is initialized with `[]` but only populated inside `if lecture.pptx_path:` block (line 155). If no PPTX is provided during upload, Stage 5 and Stage 6 still reference `slides_data`. During Stage 6 (`if slides_data:`), it would skip narration generation entirely — which means the pipeline would complete without generating any narrations or TTS. This leaves the lecture in "completed" state with zero narrations.
- **Expected**: Pipeline should handle the no-PPTX case gracefully, either by skipping TTS/narration stages or by still processing audio-only.
- **Impact**: Audio-only uploads will complete the pipeline with no narrations generated. User sees "completed" with no output.
- **Fix**: Clear error message when narrations are skipped, or generate slide-less narration.

#### H3. Refresh endpoint missing response_model
- **Files**: `backend/src/api/routes/auth.py` line 42
- **Issue**: `@router.post("/refresh")` has no `response_model`. The use case returns a raw dict `{"access_token": ..., "expires_in": ...}`. No OpenAPI schema, no automatic validation.
- **Impact**: Missing API documentation. Less robust error handling for the response.
- **Fix**: Add `response_model` with a proper Pydantic schema.

#### H4. Slides data not aligned to JobModel
- **Files**: `backend/src/worker/pipeline/orchestrator.py`
- **Issue**: The orchestrator creates per-stage `JobModel` records using `_update_job_stage()` but these are **separate records** from the initial `full_pipeline` job created in `upload_lecture.py`. The upload creates `JobModel(job_type="full_pipeline")` while the orchestrator creates `JobModel(job_type="extract_audio")`, etc. The status endpoint checks for per-stage jobs, not the initial job.
- **Impact**: Two sets of job records for the same pipeline. Redundant data.
- **Fix**: Either use a single job record with progress tracking, or properly link sub-jobs to the parent job.

#### H5. Frontend uses `console.error()` for user-facing errors
- **Files**: `frontend/` dashboard, projects, upload pages
- **Issue**: All error handling just does `console.error('Failed to load...')` with no user-facing toast or error state. The upload page shows errors, but project listing, detail pages don't show error states to users.
- **Impact**: Silent failures. User sees loading spinners forever if API calls fail.
- **Fix**: Add error state UI with retry buttons for all data-fetching pages.

#### H6. File download returns entire file content in memory
- **Files**: `backend/src/api/routes/files.py` line 70
- **Issue**: `content = await storage.retrieve(file_record.storage_path)` loads the entire file into memory, then wraps it in `iter([content])`. For a 2GB video file, this means 2GB in memory on every download.
- **Expected**: Stream files in chunks.
- **Root cause**: `LocalStorage.retrieve()` reads the entire file with `aiofiles.open().read()`.
- **Impact**: Memory exhaustion on concurrent large file downloads.
- **Fix**: Use `StreamingResponse` with a file-like object that reads in chunks.

#### H7. Celery task retry swallows exception context
- **Files**: `backend/src/worker/tasks/lecture_tasks.py` line 27
- **Issue**: `raise self.retry(exc=exc)` — `self.retry()` raises a `Retry` exception, not the original exception. The `raise` is redundant. The original traceback is lost after retries exhausted.
- **Impact**: Hard to debug pipeline failures after retries are exhausted.
- **Fix**: Properly log the exception before calling `self.retry()`.

### MEDIUM

#### M1. Duplicate file validation logic
- **Files**: `backend/src/core/use_cases/lecture/upload_lecture.py` (lines 26-29, inline `_validate_extension`), `backend/src/api/dependencies/validation.py` (lines 42-44, `validate_file_extension`)
- **Issue**: Two implementations of the same file extension validation. The one in `upload_lecture.py` manually parses the extension while `validation.py` uses `os.path.splitext`.
- **Impact**: Code duplication. Inconsistency risk if one is updated but not the other.
- **Fix**: Use `validation.py` consistently.

#### M2. SlideModel and TranscriptSegmentModel don't use TimestampMixin
- **Files**: `backend/src/infrastructure/db/models/slide.py`, `transcript_segment.py`
- **Issue**: Most models use `TimestampMixin` (created_at + updated_at) but `SlideModel` and `TranscriptSegmentModel` extend `Base` directly and only have `created_at` (no `updated_at`). `JobModel` also breaks the pattern by extending `Base` only.
- **Impact**: Inconsistency. Some tables track updates, others don't.
- **Fix**: Use `TimestampMixin` consistently.

#### M3. `passlib` dependency unused
- **Files**: `backend/requirements.txt` line 9
- **Issue**: `passlib[bcrypt]>=1.7.4` is listed but the code uses `bcrypt` directly. Passlib is not imported anywhere.
- **Impact**: Unnecessary dependency.
- **Fix**: Remove passlib from requirements.

#### M4. Rate limiting values configured but not implemented
- **Files**: `backend/src/config/settings.py` lines 41-42
- **Issue**: `RATE_LIMIT_REQUESTS=100` and `RATE_LIMIT_WINDOW_SECONDS=60` are defined but no rate limiting middleware exists.
- **Impact**: Settings are dead config. No rate limiting on any endpoint.
- **Fix**: Implement rate limiting middleware, or remove the config values.

#### M5. Domain events defined but never emitted
- **Files**: `backend/src/core/domain/events.py`
- **Issue**: `LectureUploaded`, `LectureProcessingStarted`, `LectureProcessingCompleted`, `LectureProcessingFailed`, `NarrationGenerated`, `VoiceProfileCreated` are defined as dataclasses. Not a single one is ever instantiated or emitted anywhere in the codebase.
- **Impact**: Dead code. The domain event pattern was planned but never wired.
- **Fix**: Emit events at the appropriate use case boundaries, or remove them.

#### M6. Frontend Dockerfile missing next.config.js
- **Files**: `frontend/Dockerfile` lines 1-17
- **Issue**: The runner stage copies `.next`, `public`, `package.json`, and `node_modules` from the builder — but not `next.config.js`. While `next start` may work with defaults, the `reactStrictMode: true` setting from the config will be lost.
- **Impact**: React strict mode won't be enabled in production Docker images.
- **Fix**: Copy `next.config.js` in the runner stage.

#### M7. No `__init__.py` re-exports at package boundaries
- **Files**: `backend/src/__init__.py`, several other `__init__.py` files
- **Issue**: Most `__init__.py` files are empty. No clean public API surface at package level. Imports use full dotted paths everywhere.
- **Impact**: Brittle imports. Internal refactoring requires updating imports across many files.
- **Fix**: Re-export key classes at package boundaries.

### LOW

#### L1. Hardcoded secrets in settings defaults
- **Files**: `backend/src/config/settings.py` lines 13, 25-26
- **Issue**: `SECRET_KEY = "change-me-in-production"`, `JWT_SECRET_KEY = "change-me-jwt-secret-key-64-chars-min"` as defaults. These are development-only defaults and will be overridden by env vars in production, but if someone deploys without setting them, all JWT tokens can be forged.
- **Impact**: Security risk if defaults are used in production.
- **Fix**: Add startup validation that checks for production env vars.

#### L2. Celery queue system configured but not used
- **Files**: `backend/src/worker/celery_app.py` lines 30-44
- **Issue**: 7 Celery queues are defined (`default`, `audio`, `transcription`, `llm`, `tts`, `pptx`, `priority_high`) but the only task `process_lecture_pipeline` doesn't specify a queue, so everything goes to 'default'.
- **Impact**: Queue infrastructure is dead config.
- **Fix**: Route pipeline stages to appropriate queues, or remove unneeded queues.

#### L3. `ai-server/service/src/config.py` defined but main.py uses env vars directly
- **Files**: `ai-server/service/src/config.py`, `ai-server/service/src/main.py`
- **Issue**: `ServiceConfig` class is defined using Pydantic settings but `main.py` uses `os.getenv()` calls directly. The config class is never imported.
- **Impact**: Dead code. Config is duplicated between the class and env var reads.
- **Fix**: Use the config class in main.py.

#### L4. No health check for Celery worker in docker-compose
- **Files**: `infrastructure/docker-compose.yml`
- **Issue**: Postgres has a health check, but Celery worker has no health check or restart conditions.
- **Impact**: Worker failures go undetected.
- **Fix**: Add Celery health check.

#### L5. Backend `__init__.py` at `backend/__init__.py` is empty
- **Files**: `backend/__init__.py`
- **Issue**: Empty. If the `backend` directory is meant to be a Python package, it should have proper setup.
- **Impact**: Minor — doesn't affect imports because Python treats it as a namespace package anyway.

#### L6. `slides` and `transcript_segments` models define `created_at` without `server_default` in ORM
- **Files**: `backend/src/infrastructure/db/models/slide.py`, `transcript_segment.py`
- **Issue**: `created_at = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)` uses Python-side `default` not `server_default`. If inserts bypass SQLAlchemy (e.g., raw SQL), `created_at` would be NULL.
- **Impact**: Inconsistent with migration which uses `server_default=sa.text("NOW()")`.
- **Fix**: Add `server_default=func.now()` or keep ORM-side default consistent.

---

## 4. Missing Components Report

| Component | Referenced In | Status | Impact |
|---|---|---|---|
| WebSocket implementation | Nginx config, `backend/src/api/websockets/` | 🔴 Missing | Placeholder only |
| Rate limiting middleware | `settings.py` config values | 🔴 Missing | No rate limiting |
| Transcript download endpoint (`/api/v1/transcripts/{id}`) | `get_lecture.py` generates URL | 🔴 Missing | Dead link in API response |
| Narrated PPTX download endpoint (`/api/v1/files/download/{id}`) | `get_lecture.py` generates URL | 🔴 Missing | Dead link in API response |
| F5-TTS model integration | `ai-server/service/src/main.py` | 🔴 Missing | TTS produces silence |
| Real S3/cloud storage implementation | `StoragePort` abstraction | 🔴 Missing | Only LocalStorage exists |
| Pipeline progress tracking on `JobModel.progress` field | `JobModel` schema, orchestrator | 🟡 Partial | `progress` field never updated |
| Frontend error toast component | `sonner` dependency installed | 🔴 Missing | `sonner` package installed but `<Toaster>` never rendered in layout |
| Frontend loading skeleton states | `Skeleton` component exists | 🟡 Partial | Used nowhere |
| Frontend project update page/form | `update` API in projects.ts | 🔴 Missing | No UI for editing projects |
| Frontend lecture detail page with narration playback | UI references it | 🔴 Missing | No dedicated lecture detail page |
| Frontend processing status polling | `getStatus` API exists | 🔴 Missing | No UI that polls for status |
| Alembic migration runner in Docker | `Makefile`, docker-compose | 🟡 Partial | No automated migration on startup |
| `.env` file | Required by `docker-compose.yml` | 🟡 Partial | Only `.env.example` exists |
| ServiceConfig usage in AI server | `ai-server/service/src/config.py` | 🔴 Missing | Config class never imported |
| backend/src/infrastructure/queue/ | Empty `__init__.py` | 🔴 Missing | Queue abstraction placeholder |
| backend/src/infrastructure/pptx/ | Empty `__init__.py` | 🔴 Missing | PPTX abstraction placeholder |
| Celery beat/scheduled tasks | Configured in architecture docs | 🔴 Missing | Not implemented |
| `backend/src/core/domain/entities/__init__.py` | Domain entities folder | 🔴 Missing | Empty package |

---

## 5. API Health Report

| Endpoint | Status | Works? | Frontend Calls? | Auth? | Schema Correct? | Notes |
|---|---|---|---|---|---|---|
| `GET /api/v1/health` | ✅ Complete | ✅ | No | No | ✅ | Checks PG, skips Redis |
| `POST /api/v1/auth/register` | ✅ Complete | ✅ | ✅ | No | ✅ | 201, 409, 422 |
| `POST /api/v1/auth/login` | ✅ Complete | ✅ | ✅ | No | ✅ | 200, 401 |
| `POST /api/v1/auth/refresh` | 🟡 Partial | ✅ | ✅ | No | ❌ No response_model | Returns raw dict |
| `GET /api/v1/auth/me` | ✅ Complete | ✅ | ✅ | ✅ | ✅ | |
| `GET /api/v1/projects` | ✅ Complete | ✅ | ✅ | ✅ | 🟡 Manual serialization | Returns dicts not models |
| `POST /api/v1/projects` | ✅ Complete | ✅ | ✅ | ✅ | ✅ | |
| `GET /api/v1/projects/{id}` | ✅ Complete | ✅ | ✅ | ✅ | ✅ | |
| `PUT /api/v1/projects/{id}` | ✅ Complete | ✅ | No UI | ✅ | ✅ | No frontend form |
| `DELETE /api/v1/projects/{id}` | ✅ Complete | ✅ | ✅ | ✅ | ✅ | |
| `POST /api/v1/lectures/upload` | ✅ Complete | ✅ | ✅ | ✅ | ✅ | Dispatches Celery |
| `GET /api/v1/lectures/{id}` | ✅ Complete | ✅ | No UI | ✅ | 🟡 Dead URLs | `transcript_url` and `narrated_pptx_url` 404 |
| `GET /api/v1/lectures/{id}/status` | ✅ Complete | ✅ | No UI | ✅ | ✅ | Not polled by frontend |
| `GET /api/v1/voice-profiles` | ✅ Complete | ✅ | ✅ | ✅ | ✅ | |
| `POST /api/v1/voice-profiles` | 🟡 Partial | ✅ | ✅ | ✅ | ✅ | No async voice cloning |
| `GET /api/v1/voice-profiles/{id}` | ✅ Complete | ✅ | No UI | ✅ | ✅ | |
| `DELETE /api/v1/voice-profiles/{id}` | ✅ Complete | ✅ | ✅ | ✅ | ✅ | |
| `GET /api/v1/files/{file_id}` | 🟡 Partial | ✅ | No UI | ✅ | 🟡 Loads to memory | No streaming |
| `GET /api/v1/transcripts/{id}` | 🔴 Missing | ❌ | Via dead URL | N/A | N/A | Doesn't exist |
| `GET /api/v1/files/download/{id}` | 🔴 Missing | ❌ | Via dead URL | N/A | N/A | Doesn't exist |

**AI Server Endpoints:**

| Endpoint | Status | Works? | Notes |
|---|---|---|---|
| `GET /ai/v1/health` | ✅ Complete | ✅ | Reports all model status |
| `POST /ai/v1/transcribe` | ✅ Complete | ✅ | Faster-Whisper integrated |
| `POST /ai/v1/embed` | ✅ Complete | ✅ | BGE-M3 integrated |
| `GET /ai/v1/dimensions` | ✅ Complete | ✅ | |
| `POST /ai/v1/align` | ✅ Complete | ✅ | SGLang/Qwen proxy |
| `POST /ai/v1/generate-narration` | ✅ Complete | ✅ | Per-slide with fallback |
| `POST /ai/v1/tts` | 🔴 Broken | ❌ | Returns silence (placeholder) |
| `POST /ai/v1/clone-voice` | 🟡 Partial | ✅ | Returns speaker ID, no real cloning |

---

## 6. Frontend Health Report

| Page | Route | Status | Works? | Notes |
|---|---|---|---|---|
| Root Layout | `/` | ✅ | ✅ | Inter font, globals.css |
| Auth Layout | `/auth/*` | ✅ | ✅ | Centered card |
| Login | `/auth/login` | ✅ | ✅ | Email/password form |
| Register | `/auth/register` | ✅ | ✅ | With validation |
| Dashboard Layout | `/*` (dashboard group) | ✅ | ✅ | Auth guard, Sidebar + Header |
| Dashboard Redirect | `/` | ✅ | ✅ | Redirects to /dashboard |
| Dashboard | `/dashboard` | 🟡 Partial | ✅ | Stats, project list, create dialog |
| Projects List | `/projects` | ✅ | ✅ | Full list with pagination |
| Project Detail | `/projects/[id]` | 🟡 Partial | ✅ | Lecture list, delete confirm |
| Upload Lecture | `/lectures/upload` | ✅ | ✅ | Multi-file form, progress bar |
| Voice Profiles | `/voice-profiles` | ✅ | ✅ | Create/list/delete |
| Lecture Detail | Should exist | 🔴 Missing | ❌ | No dedicated page |
| Processing Status | Should exist | 🔴 Missing | ❌ | No polling UI |

**Frontend Issues:**
- No `Sonner` `<Toaster>` component rendered in layout (installed but unused)
- No error toast/notification system
- Dashboard stats card for Voice Profiles shows `—` instead of actual count
- No loading skeleton usage (Skeleton component exists but unused)
- No lecture detail / processing status page
- No project update UI (API exists, no form)
- No polling for lecture processing status
- Silent `console.error()` instead of user-facing error messages (except upload page)

---

## 7. Backend Health Report

| Subsystem | Status | Notes |
|---|---|---|
| FastAPI app factory | ✅ Complete | Clean setup, routers registered |
| Error handling | ✅ Complete | 9 exception classes, proper handlers |
| CORS | ✅ Complete | Configurable from settings |
| Request logging | ✅ Complete | Trace ID, timing |
| JWT auth | ✅ Complete | Access + refresh tokens |
| Password hashing | ✅ Complete | bcrypt 12 rounds |
| User registration | ✅ Complete | With password validation |
| User login | ✅ Complete | |
| Token refresh | ✅ Complete | Missing response_model |
| Project CRUD use cases | ✅ Complete | All 5 operations |
| Lecture upload | ✅ Complete | File validation, storage, Celery dispatch |
| Lecture detail + status | ✅ Complete | But dead URLs |
| Voice profile CRUD | ✅ Complete | |
| File download | 🟡 Partial | No streaming, in-memory |
| ORM models | ✅ Complete | 9 models, proper FKs |
| Repositories | ✅ Complete | Base + 8 sub-repos |
| Alembic migration | ✅ Complete | 1 migration, all 9 tables |
| Celery app | ✅ Complete | 7 queues configured |
| Pipeline orchestrator | 🟡 Partial | Scope issues, embedding waste |
| Extract audio (FFmpeg) | ✅ Complete | |
| Transcribe (Whisper) | ✅ Complete | HTTP to GPU server |
| Parse PPTX | ✅ Complete | python-pptx |
| Generate embeddings | 🟡 Partial | Results not persisted |
| Align transcript | 🟡 Partial | Re-embeds, double computation |
| Generate narration | 🟡 Partial | Falls back on error |
| Generate TTS | 🔴 Broken | Returns silence from GPU server |
| Embed narration into PPTX | 🔴 Broken | Wrong API for audio |
| AI client abstractions | 🔴 Never used | Ports + implementations are dead code |
| Domain events | 🔴 Never used | Dead code |
| Rate limiting | 🔴 Not implemented | Config only |
| WebSocket | 🔴 Not implemented | Placeholder only |

---

## 8. Pipeline Health Report

| Stage # | Stage Name | File | Implemented? | Connected? | Executable? | Notes |
|---|---|---|---|---|---|---|
| 1 | Extract Audio | `extract_audio.py` | ✅ Full | ✅ | ✅ | FFmpeg, loudnorm filter |
| 2 | Transcribe | `transcribe.py` | ✅ Full | ✅ (GPU HTTP) | ✅ | Faster-Whisper |
| 3 | Parse PPTX | `parse_pptx.py` | ✅ Full | ✅ | ✅ | python-pptx |
| 4 | Generate Embeddings | `generate_embeddings.py` | 🟡 Partial | ✅ (GPU HTTP) | ✅ | Results discarded |
| 5 | Align Transcript | `align_transcript.py` | 🟡 Partial | ✅ (GPU HTTP) | ✅ | Double-embeds |
| 6 | Generate Narration | `generate_narration.py` | 🟡 Partial | ✅ (GPU HTTP) | ✅ | Per-slide fallback |
| 7 | Generate TTS | `generate_tts.py` | 🔴 Broken | ✅ (GPU HTTP) | 🔴 Returns silence | F5-TTS not integrated |
| 8 | Embed Narration into PPTX | `embed_narration.py` | 🔴 Broken | ✅ (local) | 🔴 Wrong API | `add_movie` not for audio |

**Pipeline Flow:**
```
upload → Stage 1 (extract audio) → Stage 2 (transcribe) → Stage 3 (parse pptx)
  → Stage 4 (generate embeddings) → [embeddings discarded] → Stage 5 (align transcript)
  → [re-embeds in stage 5] → Stage 6 (generate narration) → Stage 7 (TTS — SILENCE)
  → Stage 8 (embed into pptx — BROKEN)
```

---

## 9. Database Report

### Schema Quality

| Table | Has Migrations? | Matches ORM? | Has FKs? | Has Indexes? | Status |
|---|---|---|---|---|---|
| `users` | ✅ | ✅ | N/A | ✅ email unique | ✅ |
| `projects` | ✅ | ✅ | ✅ users | ✅ user_id | ✅ |
| `voice_profiles` | ✅ | ✅ | ✅ users | ✅ user_id | ✅ |
| `lectures` | ✅ | ✅ | ✅ projects, voice_profiles | ✅ project_id, status | ✅ |
| `slides` | ✅ | ✅ | ✅ lectures | ✅ lecture_id, uq | ✅ |
| `transcript_segments` | ✅ | ✅ | ✅ lectures, slides | ✅ lecture_id, slide_id, uq | ✅ |
| `narrations` | ✅ | ✅ | ✅ slides, lectures | ✅ lecture_id, slide_id | ✅ |
| `jobs` | ✅ | ✅ | ✅ lectures | ✅ lecture_id, status, celery_id | ✅ |
| `files` | ✅ | ✅ | ✅ lectures, users | ✅ lecture_id, user_id | ✅ |

### Issues

| Issue | Severity | Notes |
|---|---|---|
| Missing updated_at on slides, transcript_segments, jobs | Low | Inconsistency, not a bug |
| All created_at use Python-side `default=` not `server_default=` in ORM (except via migration which uses `server_default`) | Low | ORM vs migration mismatch |
| No cascade delete for file_records when user deleted | Info | Migration has CASCADE |
| No migration for the `images` table (mentioned in architecture docs but not in models or migrations) | Low | May not be needed |
| `slide_id` FK in `transcript_segments` uses `ON DELETE SET NULL` which is correct for alignment | ✅ Good | |
| `voice_profile_id` FK in `lectures` uses `ON DELETE SET NULL` which is correct | ✅ Good | |

---

## 10. Deployment Report

### Docker

| Service | Dockerfile | Status | Issues |
|---|---|---|---|
| nginx | `nginx:alpine` | ✅ | |
| frontend | `frontend/Dockerfile` | 🟡 Partial | Missing `next.config.js` in runner |
| backend | `backend/Dockerfile` | 🔴 Broken | Import path, no PYTHONPATH |
| celery-worker | `backend/Dockerfile` | 🔴 Broken | Same import path issue as backend |
| postgres | `postgres:16-alpine` | ✅ | Has health check |
| redis | `redis:7-alpine` | ✅ | Password protected |
| sglang | `lmsysorg/sglang:latest` | ✅ | GPU reserved |
| gpu-service | `ai-server/service/Dockerfile` | ✅ | GPU reserved |

### Environment

| File | Status | Notes |
|---|---|---|
| `.env.example` | ✅ Exists | 56 lines, well documented |
| `.env` | 🟡 Unknown | Referenced by docker-compose, may not exist |
| Docker env overrides | 🟡 Partial | Some values hardcoded, some use defaults |

### Production Readiness

| Criterion | Status | Notes |
|---|---|---|
| No default secrets in production config | 🔴 | `change-me-in-production` defaults |
| Database migration automation | 🔴 | No `alembic upgrade head` in startup |
| Volume persistence | ✅ | Postgres, Redis, storage volumes |
| GPU support | ✅ | NVIDIA device reservations |
| Health checks | 🟡 Partial | Postgres only |
| Container restart policy | ✅ | `unless-stopped` on all |
| Network isolation | ✅ | Separate `web-network` and `ai-network` |
| Nginx reverse proxy | ✅ | Configured |
| HTTPS | 🔴 | Not configured (no SSL) |
| Monitoring/logging | 🔴 | No centralized logging |
| CI/CD | 🔴 | Not set up |

---

## 11. MVP Readiness Score

| Subsystem | Score | Justification |
|---|---|---|
| **Frontend** | 4/10 | All core pages exist but missing error handling, loading states, lecture detail page, processing status polling, toast notifications |
| **Backend** | 5/10 | Core API works but AI port abstractions dead, pipeline stages 7-8 broken, memory issues, dead URLs |
| **Database** | 8/10 | Well-designed schema, clean migrations, proper FKs — minor inconsistencies only |
| **Pipeline** | 3/10 | Stages 1-3 solid, 4-6 partial but functional, 7-8 completely broken (silence + wrong PPTX API) |
| **AI Server** | 4/10 | Whisper + BGE-M3 + Qwen work great. TTS returns silence. F5-TTS never integrated. |
| **Infrastructure** | 4/10 | Docker compose is well structured but backend container won't start, frontend has double-/api bug |
| **Deployment** | 3/10 | Blocked by backend Dockerfile import path. No migration automation. No HTTPS. |
| **Testing** | 4/10 | 15 unit + 12 integration tests passing (SQLite), but zero pipeline tests, zero AI server tests, zero frontend tests, zero end-to-end tests |
| **Documentation** | 6/10 | Extensive docs (architecture.md, SPECS.md, SETUP.md) but doesn't match actual implementation |
| **Security** | 5/10 | JWT + bcrypt are solid. But dev secrets in defaults, no rate limiting, no input sanitization beyond file validation |
| **Overall MVP** | **4.2/10** | Core architecture is sound but 3 critical bugs block any meaningful deployment or demonstration |

### Blockers (in order of severity)

1. **Backend Docker container won't start** — import path mismatch
2. **TTS returns silence** — F5-TTS never wired up
3. **PPTX embedding broken** — `add_movie` creates video shapes, not audio embedding
4. **Frontend API calls 404 in Docker** — double `/api` prefix
5. **Dead URLs in lecture detail** — transcript and narrated PPTX endpoints don't exist

---

## 12. Prioritized Action Plan

### Phase 1 — Critical Blockers

1. Fix backend Dockerfile import path (`PYTHONPATH`)
2. Implement actual F5-TTS inference (replace silence generation)
3. Fix `embed_narration_into_pptx` to properly embed audio via OpenXML
4. Fix frontend `NEXT_PUBLIC_API_URL` double `/api` bug
5. Create missing `/api/v1/transcripts/{id}` and `/api/v1/files/download/{id}` endpoints (or fix URLs to use existing `/api/v1/files/{file_id}`)

### Phase 2 — Core Functionality

6. Wire up AI port abstractions or remove them
7. Create FileModel records for narration audio during pipeline
8. Fix audio_url in lecture detail to point to actual file ID
9. Add user-facing error handling in frontend (toast notifications)
10. Create lecture detail / processing status frontend page
11. Add processing status polling to frontend
12. Add loading skeleton states

### Phase 3 — Stabilization

13. Stream files instead of loading into memory
14. Fix scope issue for `slides_data` when no PPTX provided
15. Add `response_model` to all endpoints
16. Add Celery worker health check
17. Add database migration on startup
18. Implement rate limiting middleware or remove config
19. Consolidate duplicate file validation code

### Phase 4 — Performance

20. Persist embeddings to database between pipeline stages
21. Route pipeline stages to appropriate Celery queues
22. Add database connection pooling tuning
23. Add request caching for embeddings

### Phase 5 — Polish

24. Add HTTPS/SSL configuration
25. Add centralized logging infrastructure
26. Add CI/CD pipeline
27. Write pipeline integration tests
28. Add end-to-end tests
29. Remove dead code (unused ports, events, AI clients if not needed)

---

## 13. Implementation Order (Exact Execution Sequence)

```
Task  1: Fix backend/Dockerfile — add PYTHONPATH=/app/.. or restructure to make backend package importable
Task  2: Fix ai-server/service TTS endpoint — implement actual F5-TTS inference
Task  3: Fix embed_narration_into_pptx — use proper OpenXML audio embedding
Task  4: Fix docker-compose.yml — remove /api from NEXT_PUBLIC_API_URL
Task  5: Fix get_lecture.py — fix transcript_url and narrated_pptx_url to point to real endpoints
Task  6: Fix get_lecture.py — fix audio_url to use file_id not narration_id
Task  7: Create FileModel records for narration audio in pipeline orchestrator
Task  8: Add Sonner <Toaster> to frontend root layout
Task  9: Add error toast notifications to all frontend pages
Task 10: Create lecture detail + processing status page in frontend
Task 11: Add status polling to upload page
Task 12: Add loading skeletons
Task 13: Fix files.py download to use StreamingResponse with chunked reads
Task 14: Register response_model on /auth/refresh endpoint
Task 15: Add .env file creation to setup docs or startup script
Task 16: Add docker-compose health check for celery-worker
Task 17: Run alembic upgrade head in backend startup (or docker-compose entrypoint)
Task 18: Consolidate file validation into validation.py
Task 19: Wire up rate limiting middleware or remove config values
Task 20: Pipeline refactor — pass embeddings between stages
Task 21: Route pipeline stages to proper Celery queues
Task 22: Clean up dead code (unused ports, events, AI client classes)
Task 23: Add pipeline integration tests
```

Total: 23 tasks to reach MVP.
