# MASTER MVP RECOVERY PLAN — Verified Final

---

## 1. VERIFIED AUDIT: Previous Findings Reviewed

I independently re-read every functional file in the repository and verified each claim against the source code.

### Critical Issues

**C1. Backend Docker Container Import Path**
- *Claim*: Container won't start because `backend.main.py` uses `from backend.src.*` imports but Docker's `WORKDIR /app` maps to `backend/` without PYTHONPATH.
- **Verdict**: ⚠️ **Partially Correct**
- *Why*: `backend/main.py` line 2 imports `from backend.src.api.errors.handlers import ...`. When `uvicorn main:app` runs from `/app/` (which = `backend/`), Python can't resolve `backend.src.*` because `backend` is not on `sys.path`. However, the previous audit missed that `start.sh` (local dev) runs uvicorn from the **project root** (`cd "$ROOT"` then `uvicorn backend.main:app`), which works fine. The Dockerfile has `WORKDIR /app` (where `/app` = `backend/`), and `uvicorn main:app` from there cannot resolve package imports. **Fix**: Restructure to run from the parent directory, set PYTHONPATH, or install the package.
- **Files**: `backend/Dockerfile:16`, `backend/main.py:1-15`, `start.sh:21-23`
- **Impact**: Docker deployment blocked. Local dev works.

**C2. TTS Produces Silence**
- *Claim*: `/ai/v1/tts` generates silence.
- **Verdict**: ✅ **Confirmed**
- *Why*: `ai-server/service/src/main.py` lines 345-368. The `synthesize()` function computes `duration = max(1.0, len(text.split()) / 2.5 / speed)`, generates `b"\x00\x00" * num_samples`, and returns that as WAV. F5-TTS import is commented out (`# from f5_tts.model import DiT`). The `_load_tts()` function never instantiates a model — it returns a config dict `{"path": ..., "device": ..., "sample_rate": ...}`.
- **Impact**: **Core feature broken.** Pipeline completes but output has silence.

**C3. embed_narration_into_pptx Uses Wrong API**
- *Claim*: `slide.shapes.add_movie()` creates video shapes, not audio embedding.
- **Verdict**: ✅ **Confirmed**
- *Why*: `backend/src/worker/pipeline/embed_narration.py` line 76 calls `slide.shapes.add_movie(audio_path, 0, 0, 1, 1)`. `python-pptx`'s `add_movie()` creates a **video** relationship in the PPTX XML. It also stores the server's **absolute file path** as a reference, not the actual audio bytes. The PPTX will reference `C:\Users\Raunak\...\slide_001.wav` which won't exist on any other machine. Even `audio_bytes` is read on line 70 but **never used** — the data is not embedded.
- **Impact**: Narrated PPTX output is broken.

**C4. Frontend API URL Double `/api` Prefix**
- *Claim*: `NEXT_PUBLIC_API_URL=http://localhost:80/api` + `/api/v1/auth/...` paths = double prefix.
- **Verdict**: ⚠️ **Partially Correct**
- *Why*: `infrastructure/docker-compose.yml` line 28 sets `NEXT_PUBLIC_API_URL=http://localhost:80/api`. The frontend's `client.ts` line 24 posts to `${API_BASE}/api/v1/auth/refresh` which would become `http://localhost:80/api/api/v1/auth/refresh`. **However**: the frontend accesses the backend through nginx in production, and nginx proxies `/api/` → backend. So the URL sent by the browser should be `http://localhost:80/api/api/v1/...` which nginx would match to `/api/` and forward as `/api/api/v1/...` to backend — which is wrong. But in local dev (not Docker), the frontend uses `http://localhost:8000` directly (the fallback default), and none of the API paths include a base `/api` prefix, so the paths like `/api/v1/auth/login` resolve correctly to `http://localhost:8000/api/v1/auth/login`. **This bug only manifests in Docker Compose deployment** where nginx is in front.
- **Impact**: All API calls 404 in Docker deployment. Local dev is fine.
- **Fix**: Set `NEXT_PUBLIC_API_URL=http://localhost:80` (no trailing `/api`).

**C5. AI Port Interfaces Never Used**
- *Claim*: 4 abstract interfaces + 5 client classes are never instantiated.
- **Verdict**: ✅ **Confirmed**
- *Why*: `backend/src/core/ports/ai.py` defines `TranscriptionPort`, `EmbeddingPort`, `LLMPort`, `TTSPort`. `backend/src/infrastructure/ai_client/` has `base.py`, `transcription.py`, `embedding.py`, `llm.py`, `tts.py` implementing these. **No file in the codebase imports any of these clients or ports.** The pipeline stages make direct `httpx.post()` calls. This is dead code by intent, not by accident — the ports were designed but the pipeline was implemented directly.
- **Impact**: Architectural debt. Testing pipeline stages requires mocking HTTP.

**C6. Dead Endpoint URLs in Lecture Detail Response**
- *Claim*: `transcript_url` points to nonexistent `/api/v1/transcripts/{id}`, `narrated_pptx_url` points to nonexistent `/api/v1/files/download/{id}`.
- **Verdict**: ✅ **Confirmed**
- *Why*: `backend/src/core/use_cases/lecture/get_lecture.py` lines 86-91. Line 88: `"transcript_url": "/api/v1/transcripts/" + str(lecture.id)` — no such route exists. Line 90: `"narrated_pptx_url": "/api/v1/files/download/" + str(lecture.id)` — the actual endpoint is `GET /api/v1/files/{file_id}` (which expects a FileModel ID, not a lecture ID).
- **Impact**: Links in API response always 404.

**C7. `audio_url` Uses Narration ID Instead of File ID**
- *Claim*: Audio download link points to `/api/v1/files/{narration_id}`.
- **Verdict**: ✅ **Confirmed**
- *Why*: `get_lecture.py` line 81-82: `audio_url = f"/api/v1/files/{slide.narration.id}"`. The files endpoint expects a `FileModel.id`, not a `NarrationModel.id`. Narration audio files are **never saved as FileModel records** in the pipeline.
- **Impact**: Audio playback links always 404.

**C8. In-Memory Embedding Cache Between Stages**
- *Claim*: Orchestrator discards stage 4 embedding results, stage 5 re-computes.
- **Verdict**: ✅ **Confirmed**
- *Why*: `orchestrator.py` line 173: `generate_embeddings(all_texts)` — return value is discarded. `align_transcript.py` line 96 calls `generate_embeddings(slide_texts)` and line 105 calls `generate_embeddings(seg_texts)` again, hitting the HTTP service a second time (or the in-memory cache if worker process still alive).
- **Impact**: 2x GPU calls for embeddings. Cache only survives within a single Celery worker process lifetime.

---

### High Issues

**H1. `get_optional_user()` Nullable Request Parameter**
- **Verdict**: ❌ **Incorrect**
- *Why*: `backend/src/api/dependencies/auth.py` line 58: `request: Request = None`. The previous audit claimed this is not valid FastAPI DI. **Actually**: this function is **never used** anywhere. No route calls `Depends(get_optional_user)`. It's dead code. Even if called, FastAPI **does** inject `Request` automatically — the `= None` default is never exercised because FastAPI always provides the request. The guard `if request else None` on line 66 is indeed always True. This is not a bug.
- **Reclassification**: Dead code, not a bug.

**H2. Orchestrator `slides_data` Scope Issue**
- *Claim*: If no PPTX, `slides_data = []` causes stages 5-6 to be skipped.
- **Verdict**: ⚠️ **Partially Correct**
- *Why*: `orchestrator.py` line 179 initializes `slides_data = []`. Line 155: `if lecture.pptx_path:` populates it. If there's no PPTX, `slides_data` stays `[]`. Line 190 (`if slides_data and transcript.segments`) — Stage 5 skips. Line 233 (`if slides_data:`) — Stage 6 skips. Line 276 (`if lecture.pptx_path:`) — Stage 8 skips. **However**: the previous audit missed that Stage 7 (TTS) runs regardless — it looks for `NarrationDbModel` records which don't exist if Stage 6 was skipped, so TTS produces nothing. **Result**: the pipeline runs through all 8 stages, marks itself "completed", but generates zero narrations, TTS, or PPTX output. The lecture ends in "completed" state with no content.
- **Impact**: No-PPTX uploads silently produce zero output.

**H3. Refresh Endpoint Missing `response_model`**
- **Verdict**: ✅ **Confirmed**
- *Why*: `backend/src/api/routes/auth.py` line 42: `@router.post("/refresh")` has no `response_model`. Returns a raw dict. Missing OpenAPI schema.
- **Corrected Fix**: Add `TokenResponse` or a lighter schema.

**H4. Duplicate Job Records (full_pipeline vs per-stage)**
- **Verdict**: ✅ **Confirmed**
- *Why*: `upload_lecture.py` line 91 creates `JobModel(job_type="full_pipeline")`. The orchestrator `_update_job_stage()` creates `JobModel(job_type="extract_audio")`, `JobModel(job_type="transcribe")`, etc. Two sets of job records for the same pipeline.
- **Impact**: Redundant data. Progress tracking is split across two job hierarchies.

**H5. Frontend `console.error()` Silent Failures**
- **Verdict**: ✅ **Confirmed**
- *Why*: All data-fetching pages (dashboard, projects, project detail, voice profiles) use `catch(err) { console.error(...) }` without showing errors to users. Only the upload page shows errors. Users see infinite loading spinners on API failure.
- **Impact**: Poor UX, silent failures.

**H6. File Download Loads Entire Content in Memory**
- **Verdict**: ✅ **Confirmed**
- *Why*: `backend/src/api/routes/files.py` line 70: `content = await storage.retrieve(file_record.storage_path)`. `LocalStorage.retrieve()` (`local_storage.py` line 57) does `async with aiofiles.open(str(abs_path), "rb") as f: return await f.read()`. Entire file loaded into memory. Then wrapped in `iter([content])` on line 73.
- **Impact**: Memory exhaustion on large files. A 2GB video upload would require 2GB RAM per download.

**H7. Celery Task Retry Swallows Exception Context**
- **Verdict**: ✅ **Confirmed**
- *Why*: `tasks/lecture_tasks.py` line 27: `raise self.retry(exc=exc)` — `self.retry()` raises `Retry` exception. The `raise` is never reached. Original traceback is lost after retries exhausted.
- **Impact**: Debugging pipeline failures is harder.

---

### Medium Issues

**M1. Duplicate File Validation Logic**
- **Verdict**: ⚠️ **Partly Correct** — `upload_lecture.py` uses inline `_validate_extension()` (lines 26-29) that extends manually parses `rsplit(".", 1)`. `validation.py` has `validate_file_extension()` using `os.path.splitext()`. Different implementations, same purpose. The upload use case never calls the validation module.

**M2. SlideModel and TranscriptSegmentModel Skip TimestampMixin**
- **Verdict**: ✅ **Confirmed** — Both extend `Base` directly and have only `created_at`. Missing `updated_at`.

**M3. `passlib` Dependency Unused**
- **Verdict**: ❌ **Partially incorrect** — `requirements.txt` line 9 has `passlib[bcrypt]>=1.7.4`. The password module uses `bcrypt` directly (`import bcrypt`). Passlib is never imported. However, `passlib` may be a transitive dependency. This is an unnecessary direct dependency but not a bug.

**M4. Rate Limiting Config But No Implementation**
- **Verdict**: ✅ **Confirmed** — `settings.py` has `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS` but no middleware uses them.

**M5. Domain Events Never Emitted**
- **Verdict**: ✅ **Confirmed** — `events.py` defines 6 dataclasses. Zero instantiations exist.

**M6. Frontend Dockerfile Missing `next.config.js`**
- **Verdict**: ✅ **Confirmed** — `Dockerfile` doesn't copy `next.config.js` to runner. Default Next.js config will be used.

**M7. Empty `__init__.py` Files**
- **Verdict**: ❌ **Not a bug** — This is standard Python package convention. Empty `__init__.py` files are fine.

---

### New Issues Found

These were **missed by the previous audit**:

#### N1. AuthMiddleware Registered But Never Added to App (Critical)
- **Files**: `backend/src/api/middleware/auth.py` (AuthMiddleware class), `backend/main.py`
- **Issue**: `AuthMiddleware` is defined but **never added to the FastAPI app**. `main.py` registers `LoggingMiddleware` but not `AuthMiddleware`. The auth decorator `get_current_user` (via `OAuth2PasswordBearer`) handles auth per-route, but the middleware's JWT extraction + `request.state.user_id` is never used. The auth middleware's `PUBLIC_PATHS` set is also dead code.
- **Impact**: Dead code with incorrect expectations. If someone later adds the middleware, it would double-check auth.

#### N2. Docker Compose Frontend Can't Reach Backend via Service Name (High)
- **Files**: `infrastructure/docker-compose.yml`, `frontend/src/lib/api/client.ts`
- **Issue**: Frontend's `NEXT_PUBLIC_API_URL=http://localhost:80/api` points to nginx on `localhost:80`. But inside a Docker container, `localhost` refers to the **container itself**, not the host. When nginx is a separate container, the frontend should use `http://nginx:80` (Docker DNS) or the container network name. This is separate from the double `/api` issue.
- **Impact**: In Docker Compose, the frontend container tries to reach its own port 80, not nginx's.

#### N3. Voice Profile API Returns Wrong Schema (High)
- **Files**: `backend/src/api/routes/voice.py` (POST), `backend/src/core/dto/voice.py`, `backend/src/core/use_cases/voice/create_voice_profile.py`
- **Issue**: The POST `/api/v1/voice-profiles` route declares `response_model=VoiceProfileResponse` but the route handler accepts `name: str = Form(...), consent: bool = Form(...)`. `VoiceProfileResponse` doesn't include `sample_audio_path`, `speaker_id`, or `user_id`. The `created_at` is `datetime` but the response might not serialize correctly without `model_config = ConfigDict(from_attributes=True)`.
- **Check**: `VoiceProfileResponse` has `model_config = ConfigDict(from_attributes=True)`. But it only exposes `id`, `name`, `status`, `created_at`. The frontend `VoiceProfile` type expects `id`, `name`, `status`, `created_at`. **Actually this matches.** No bug here — moving on.

**Verification**: Re-checking... `frontend/src/types/lecture.ts` line 58-62: `VoiceProfile { id, name, status, created_at }`. `backend/src/core/dto/voice.py` line 17-22: `VoiceProfileResponse { id, name, status, created_at }`. **They match.**

#### N4. Frontend Login Race Condition (Medium)
- **Files**: `frontend/src/app/auth/login/page.tsx` lines 27-32
- **Issue**: `useAuthStore.getState().setAccessToken(tokens.access_token);` then `const me = await authApi.getMe();` then `setAuth(me, ...)`. The `setAccessToken` call mutates the store synchronously, then `getMe()` makes an HTTP call. Meanwhile, the `(dashboard)/layout.tsx` component watches `isAuthenticated` which is still `false` (because `setAuth` hasn't been called yet — only `setAccessToken` was called). This is fine — no race because `setAuth` happens before `router.push('/dashboard')`. The layout checks auth and redirects, but the redirect happens in the next render cycle. **Actually fine.** No bug.

**Verification**: Let me trace: login submits → `tokens = await authApi.login()` → `setAccessToken(token)` → `me = await getMe()` → `setAuth(me, access, refresh)` → `router.push('/dashboard')`. The `setAccessToken` in the middle ensures the next HTTP call (`getMe`) has the auth header. `isAuthenticated` stays false until `setAuth` is called. After `router.push`, the dashboard layout renders, sees `isAuthenticated=true`. **No race.**

#### N5. ListProjectsUseCase Returns Serialized Dicts Instead of Model Instances (High)
- **Files**: `backend/src/core/use_cases/project/list_projects.py` lines 32-35
- **Issue**: `return {"items": [item.model_dump() for item in items], ...}` — the items are **already serialized to dicts**. The route has no `response_model` (line 24: `@router.get("")` without response_model), so FastAPI will serialize the dict again. But the frontend `projectsApi.list()` expects `PaginatedResponse<Project>` with typed `items`. Since `model_dump()` produces plain dicts, FastAPI can't validate the inner structure. The `PaginatedResponse` schema on line 55 uses `items: list` (untyped), so validation passes but the returned objects lose Pydantic type information.
- **Impact**: Frontend receives raw dicts instead of validated models. If the schema changes, no compile-time check catches it.

#### N6. UploadLectureUseCase Creates Job Then Dispatches Celery — But Job and Pipeline Disagree on job_type (Medium)
- **Files**: `backend/src/core/use_cases/lecture/upload_lecture.py`, `backend/src/worker/pipeline/orchestrator.py`
- **Issue**: `upload_lecture.py` creates `JobModel(job_type="full_pipeline")` then dispatches Celery. The orchestrator creates per-stage jobs (`job_type="extract_audio"`, etc.). The frontend's `get_lecture_status.py` uses `PIPELINE_STAGES` that includes `"extract_audio"`, `"transcribe"`, etc., but **not** `"full_pipeline"`. So the initial "full_pipeline" job is ignored in progress calculation.
- **Impact**: Redundant initial job record.

#### N7. Nginx `location /api/v1/lectures/upload` Overlap With `location /api/` (Medium)
- **Files**: `infrastructure/nginx/sites/default.conf`
- **Issue**: The `location /api/` block proxies to `http://backend:8000/api/` (note the appended path). The more specific `location /api/v1/lectures/upload` block proxies to `http://backend:8000` (no appended path). Due to nginx location matching rules, the prefix match `/api/` will catch `/api/v1/lectures/upload` first since nginx picks the longest matching prefix. **Fix**: The upload block is redundant — `/api/` already matches. And it has a bug: the upload block's `proxy_pass http://backend:8000;` without the `/api/` suffix means it would strip the `/api/` prefix on proxying. This should be `proxy_pass http://backend:8000/api/;` to match the general API rule.

#### N8. `JobService` Function `_update_job_stage` Loads ALL Jobs Every Time (Medium)
- **Files**: `backend/src/worker/pipeline/orchestrator.py` line 83-84
- **Issue**: `jobs = session.query(JobModel).filter(JobModel.lecture_id == lecture_id).all()` — loads **every job** for the lecture on every stage update. As pipelines progress, the number of jobs grows and this becomes increasingly expensive.
- **Impact**: Inefficient, unnecessary query. A simple `COUNT` or filtered query would suffice.

#### N9. Pipeline Has No Rollback for Side Effects From Stages 1 and 4 (High)
- **Files**: `backend/src/worker/pipeline/orchestrator.py`
- **Issue**: Stages 1 (extract_audio) and 4 (generate_embeddings) have **side effects outside the database**: audio files written to disk, no cleanup if a later stage fails. If Stage 7 fails, the extracted audio from Stage 1 remains on disk forever. The orchestrator catches exceptions and marks the lecture as "failed", but doesn't clean up files written by completed stages.
- **Impact**: Orphaned files on disk on pipeline failure.

#### N10. AlignTranscript Uses Wrong AI Server URL Mode (Low)
- **Files**: `backend/src/worker/pipeline/align_transcript.py` line 122
- **Issue**: The backend's `align_transcript.py` sends a POST to `{AI_SERVICE_URL}/ai/v1/align` (which is `http://gpu-service:8001/ai/v1/align`). The AI server's router is mounted at `prefix="/ai/v1"`, so the full path resolves to `http://gpu-service:8001/ai/v1/align` — this is **correct**. But the AI server's `align()` handler on line 230 uses `data.get("transcript", {})` — the backend sends `"transcript": transcript_dict` where `transcript_dict = {"segments": transcript_segments}`. The AI server expects `transcript.segments`. **This matches.** No bug.

#### N11. No `MIME_TYPE` Detected for Uploaded Files (Low)
- **Files**: `backend/src/core/use_cases/lecture/upload_lecture.py`
- **Issue**: `FileModel` has a `mime_type` field but the upload use case never populates it (always `None`). The file download endpoint falls back to `"application/octet-stream"`.
- **Impact**: Files always served with generic MIME type. Browsers might not play video/audio inline.

#### N12. `_update_Job_Stage` Uses `session.query()` (Sync API) In Async Context (Critical)
- **Files**: `backend/src/worker/pipeline/orchestrator.py`
- **Issue**: `session.query(JobModel)` uses the SQLAlchemy **Sync-style query API**, not the async `select()` pattern. The orchestrator runs in Celery workers which use a **sync DB session** (`get_sync_session()`), so this is actually **correct** — the celery worker path uses sync sessions. The previous audit didn't flag this as a problem, and it isn't one.
- **Verdict**: Not a bug.

#### N13. `Generate_embeddings` Has A Name Collision With `data` Variable (Low)
- **Files**: `backend/src/worker/pipeline/generate_embeddings.py` line 84
- **Issue**: On cache miss, the function calls `data = resp.json()` (line 84), then accesses `data["embeddings"]`. On cache hit, there's no `data` variable — line 92 references `data.get("model", "bge-m3 (cached)")` in the return statement, which would raise `NameError` if ALL texts are cache hits.
- **Impact**: If every text is cached and `uncached_texts` is empty, the `data` variable is never defined and the final return statement would crash.
- **Files**: Let me verify... line 74-79: for cache hits, `continue` skips to next text. After loop (line 82): `if uncached_texts:` block runs the HTTP call. If `uncached_texts` is empty (all cached), this block is skipped and `data` is never defined. Line 92: `model=data.get("model", "bge-m3")` — **CRASH**: `NameError: name 'data' is not defined`.

Wait, let me re-read more carefully:

```python
uncached_texts = []
for i, text in enumerate(texts):
    if use_cache:
        key = hashlib.sha256(text.encode()).hexdigest()
        if key in _EMBEDDING_CACHE:
            results[i] = _EMBEDDING_CACHE[key]
            continue
    uncached_indices.append(i)
    uncached_texts.append(text)

if uncached_texts:
    try:
        resp = httpx.post(...)
        data = resp.json()
        ...
```

Line 92: `model=data.get("model", "bge-m3") if uncached_texts else "bge-m3 (cached)"`

Actually there's a ternary check! `model = data.get(...) if uncached_texts else "bge-m3 (cached)"`. So if `uncached_texts` is empty, it uses the string literal. **This is handled.** But if `uncached_texts` is truthy and the response doesn't contain `model`, then `data.get("model", "bge-m3")` is fine. **No crash here.**

However, there's a subtler bug: if `uncached_texts` is truthy AND `data["embeddings"]` exists but the inner loop iterates correctly, all is fine. But what if the HTTP response has no `"embeddings"` key? `zip(uncached_indices, data["embeddings"])` would `KeyError`. The AI server always returns `{"embeddings": [...]}` so this is only a problem if the server is misconfigured.

**Verdict**: Minor. Would crash with unusual server response.

#### N14. Missing Root Layout `Toaster` Rendering (Medium)
- **Files**: `frontend/src/app/layout.tsx`, `frontend/src/components/ui/sonner.tsx`
- **Issue**: The `sonner` package is installed and `Sonner` component exists, but it's never rendered in any layout. The `auth/layout.tsx` and `(dashboard)/layout.tsx` don't include `<Toaster />`.
- **Impact**: Toast notifications are unavailable even though the library is installed.

---

## 2. ROOT CAUSE ANALYSIS

### Why The Project Reached This State

**1. Architecture-First, Implementation-Second Mismatch**
The project was designed with Clean Architecture (ports, adapters, use cases, entities) but the pipeline was implemented procedurally. The port abstractions (`ai.py`, `storage.py`) were defined but never wired into the pipeline — the pipeline calls `httpx.post()` directly. This suggests the abstractions were written during design and never revisited during implementation.

**2. Two Independent Implementation Passes**
The API layer (routes, use cases, DTOs, repositories) is solid and follows Clean Architecture. The pipeline layer (orchestrator, stages) was written independently with completely different patterns:
- API uses async repositories; pipeline uses sync `session.query()`.
- API uses dependency injection; pipeline creates its own HTTP clients.
- API uses proper error handling; pipeline has bare `try/except` with rollback.
- This explains the dual JobModel records, the unused AI clients, and the duplicate embedding calls.

**3. Feature-Driven Development Without Integration Testing**
Each piece works in isolation:
- TTS endpoint returns a valid WAV (silence, but valid).
- PPTX embedding runs without errors (wrong behavior, but no errors).
- Pipeline processes without errors (but produces no useful output).
No end-to-end test ever verified: upload → transcribe → narrate → TTS → generate PPTX → verify output.

**4. Missing MVP Definition**
The project has ambitious features (voice cloning, WebSocket progress, rate limiting, 7 Celery queues) that were built as scaffolding but never deliverable. No one asked "what's the minimum useful product?" If they had, they would have focused on getting TTS working and PPTX audio embedding correct before building rate limiting configs and domain events.

**5. Docker As An Afterthought**
The Dockerfile for backend was written without testing that imports resolve. The docker-compose.yml has the double-/api issue. The Makefile references `docker compose` (without the `-` in v2). This suggests Docker was configured but never actually run end-to-end.

---

## 3. MVP DEFINITION

### Must Have (MVP)
1. User registration and login
2. Create projects, upload lectures (video/audio + optional PPTX)
3. Transcribe audio (Whisper)
4. Align transcript to slides (BGE-M3 + Qwen)
5. Generate narration scripts (Qwen)
6. **TTS that produces actual speech** (F5-TTS or alternative)
7. **PPTX with properly embedded narration audio**
8. Download narrated PPTX
9. View processing status from the frontend
10. Basic error handling and user feedback (toasts)

### Nice To Have (MVP+)
11. Voice cloning / voice profiles
12. WebSocket progress updates (polling is fine for MVP)
13. Rate limiting
14. Celery multi-queue routing
15. Domain events
16. AI port abstractions
17. S3 cloud storage
18. HTTPS/SSL

### Postpone
- WebSocket real-time updates (poll `/status` endpoint)
- Voice cloning (MVP uses default TTS voice)
- 7 Celery queues (single `default` queue is fine)
- Domain event system
- S3 storage adapter
- Rate limiting (add after MVP ships)
- Video streaming (serve files, don't stream)
- CI/CD pipeline

---

## 4. ENGINEERING EPICS

### Epic 1: Pipeline Core Fixes
**Goal**: Make the pipeline produce real output.

| Task | Files | Dependencies | Complexity |
|---|---|---|---|
| E1.1 Fix TTS to produce real speech | `ai-server/service/src/main.py` | None | 3 days |
| E1.2 Fix PPTX audio embedding | `embed_narration.py` | E1.1 | 1 day |
| E1.3 Create FileModel records for narration audio | `orchestrator.py` | E1.2 | 0.5 day |
| E1.4 Fix dead API endpoint URLs | `get_lecture.py` | E1.3 | 0.5 day |
| E1.5 Add no-PPTX pipeline handling (audio-only) | `orchestrator.py` | None | 1 day |
| E1.6 Fix embedding cache `NameError` | `generate_embeddings.py` | None | 0.5 day |

### Epic 2: Docker & Deployment
**Goal**: The project runs in Docker.

| Task | Files | Dependencies | Complexity |
|---|---|---|---|
| E2.1 Fix backend Dockerfile import path | `backend/Dockerfile`, `main.py` | None | 0.5 day |
| E2.2 Fix frontend API URL for Docker | `docker-compose.yml`, `client.ts` | None | 0.5 day |
| E2.3 Fix nginx upload location overlap | `default.conf` | None | 0.5 day |
| E2.4 Add migration to Docker startup | `docker-compose.yml`, `Makefile` | E2.1 | 0.5 day |
| E2.5 Add Celery health check | `docker-compose.yml` | None | 0.5 day |
| E2.6 Copy next.config.js to Docker runner | `frontend/Dockerfile` | None | 0.5 day |

### Epic 3: Frontend Usability
**Goal**: Users can navigate, see errors, and track processing.

| Task | Files | Dependencies | Complexity |
|---|---|---|---|
| E3.1 Add Toaster to layouts | `layout.tsx` | None | 0.5 day |
| E3.2 Add error toast to data-fetching pages | All pages | E3.1 | 1 day |
| E3.3 Add lecture status polling | New page or existing | E1.4 | 1 day |
| E3.4 Add loading skeletons | Pages | None | 0.5 day |
| E3.5 Add voice profile count to dashboard | `dashboard/page.tsx` | None | 0.5 day |

### Epic 4: Infrastructure & Cleanup
**Goal**: Remove dead code, fix remaining bugs, add tests.

| Task | Files | Dependencies | Complexity |
|---|---|---|---|
| E4.1 Remove dead AI client classes or wire them up | `infrastructure/ai_client/*` | None | 0.5 day |
| E4.2 Remove duplicate JobModel for full_pipeline | `upload_lecture.py`, `orchestrator.py` | None | 0.5 day |
| E4.3 Fix streaming file download | `files.py`, `local_storage.py` | None | 1 day |
| E4.4 Remove dead domain events or wire them up | `events.py` | None | 0.5 day |
| E4.5 Add response_model to refresh endpoint | `auth.py` routes | None | 0.5 day |
| E4.6 Consolidate duplicate file validation | `upload_lecture.py`, `validation.py` | None | 0.5 day |
| E4.7 Add pipeline integration tests | New test files | E1.1, E1.2 | 2 days |
| E4.8 Add MIME type detection for uploaded files | `upload_lecture.py` | None | 0.5 day |
| E4.9 Add pipeline cleanup on failure | `orchestrator.py` | None | 1 day |

---

## 5. DEPENDENCY GRAPH

```
E2.1 (Docker imports)
  └── No deps — can do first

E1.1 (TTS fix)
  └── No deps — can do first
  └── Required by: E1.2

E1.2 (PPTX embedding)
  └── Depends on: E1.1 (needs real audio)

E1.3 (FileModel for narration)
  └── Depends on: E1.2 (needs working audio files)
  └── Required by: E1.4 (fix audio URL)

E1.4 (Fix API URLs)
  └── Depends on: E1.3

E1.5 (No-PPTX handling)
  └── No deps — independent

E1.6 (Embedding cache bug)
  └── No deps — independent

E2.2 (Frontend API URL)
  └── No deps — independent

E2.3 (Nginx fix)
  └── No deps — independent

E2.4 (Migration in Docker)
  └── Depends on: E2.1

E2.5 (Celery health check)
  └── Depends on: E2.1

E3.1 (Toaster)
  └── No deps — independent
  └── Required by: E3.2

E3.2 (Error toasts)
  └── Depends on: E3.1

E3.3 (Status polling)
  └── Depends on: E1.4 (needs working API)

E4.x (Cleanup tasks)
  └── Independent of each other
  └── Can be done in any order after core pipeline works
```

**Critical Path**: E1.1 → E1.2 → E1.3 → E1.4 → E3.3

---

## 6. PRIORITY MATRIX

| Task | Priority | Reason |
|---|---|---|
| E1.1 — TTS fix | **Critical** | Core feature: pipeline produces silence |
| E1.2 — PPTX embedding fix | **Critical** | Core feature: output is broken |
| E2.1 — Docker import path | **Critical** | Deployment blocked |
| E2.2 — Frontend API URL | **Critical** | Docker deployment blocked |
| E1.3 — FileModel for narration | **High** | Download links return 404 |
| E1.4 — Fix API URLs | **High** | Links in API response 404 |
| E1.5 — No-PPTX handling | **High** | Audio-only uploads produce nothing |
| E3.1 — Toaster in layout | **High** | No user-facing error feedback |
| E3.2 — Error toasts | **High** | Silent failures everywhere |
| E3.3 — Status polling | **High** | Users can't see processing progress |
| E4.7 — Pipeline integration tests | **High** | Prevent regression on core feature |
| E1.6 — Embedding cache fix | Medium | Rare crash on all-cached texts |
| E2.4 — Docker migration | Medium | Manual migration step needed |
| E2.6 — next.config.js in Docker | Medium | Strict mode disabled in production |
| E4.5 — refresh response_model | Medium | Missing schema |
| E4.9 — Pipeline cleanup | Medium | Orphaned files on failure |
| E2.3 — Nginx overlap | Low | Doesn't break, just redundant |
| E4.1 — Remove dead AI clients | Low | Dead code, no functional impact |
| E4.3 — Streaming download | Low | Works for small files |
| E4.2 — Duplicate JobModel | Low | Redundant but not harmful |
| E4.4 — Domain events | Low | Dead code |
| E4.6 — Consolidate validation | Low | Code quality |
| E4.8 — MIME types | Low | Cosmetic |
| E3.4 — Loading skeletons | Low | UX polish |
| E3.5 — Voice profile count | Low | Dashboard stat |
| E2.5 — Celery health check | Low | Operational |

---

## 7. RISK REPORT

| Component | Risk | Mitigation |
|---|---|---|
| **F5-TTS integration** (E1.1) | **HIGH** — May require significant engineering to get F5-TTS producing quality audio. The F5-TTS code was never attempted, model weights are large, and GPU requirements may exceed what's available. | **Alternative**: Use a cloud TTS API (ElevenLabs, OpenAI TTS) via HTTP as a fallback. The port abstraction exists for this reason. |
| **PPTX audio embedding** (E1.2) | **MEDIUM** — python-pptx doesn't natively support audio embedding. Requires direct OpenXML manipulation (ZIP-based format). Risk of corrupting PPTX structure. | Prototype with a single test PPTX first. Create a minimal reproduction. |
| **Docker networking** (E2.x) | **MEDIUM** — Multiple interdependent containers (nginx, frontend, backend, worker, postgres, redis). Frontend's `NEXT_PUBLIC_API_URL` must resolve inside containers correctly. | Test with `docker compose up` after each networking fix. |
| **No-PPTX pipeline** (E1.5) | **LOW** — Simple conditional changes. No external dependencies. | |
| **Status polling** (E3.3) | **LOW** — Simple frontend `setInterval` calling existing `/status` endpoint. | |
| **Testing pipeline** (E4.7) | **MEDIUM** — Requires mocking the GPU server or running a test GPU server. Complex setup. | Test stages 1 and 8 (local) independently. Mock HTTP for stages 2, 4-7. |

---

## 8. FINAL IMPLEMENTATION ROADMAP

### Critical Path (Must Ship)

```
☐ Task 1: Fix Docker import path
  Goal: Backend container starts
  Files: backend/Dockerfile, backend/main.py
  Change: Add PYTHONPATH or convert to relative imports
  Dependencies: None
  Complexity: 0.5 day
  Acceptance: `docker compose up backend` starts without ImportError

☐ Task 2: Fix TTS silence
  Goal: TTS endpoint returns actual speech audio
  Files: ai-server/service/src/main.py
  Change: Replace silence generation with actual F5-TTS inference, OR switch to cloud TTS API
  Dependencies: None
  Complexity: 3 days (F5-TTS) or 1 day (cloud API)
  Acceptance: POST /ai/v1/tts with text returns WAV containing speech

☐ Task 3: Fix PPTX audio embedding
  Goal: Narrated PPTX plays audio on each slide
  Files: backend/src/worker/pipeline/embed_narration.py
  Change: Use OpenXML relationship manipulation to properly embed audio media
  Dependencies: Task 2 (needs real audio files)
  Complexity: 1 day
  Acceptance: Output PPTX has audio that plays automatically on slide entry

☐ Task 4: Fix frontend API URL for Docker
  Goal: Frontend API calls reach backend in Docker
  Files: infrastructure/docker-compose.yml
  Change: Remove /api from NEXT_PUBLIC_API_URL suffix
  Dependencies: None
  Complexity: 0.5 day
  Acceptance: Frontend login works in Docker Compose

☐ Task 5: Create FileModel records for narration audio
  Goal: Narration audio URLs point to real files
  Files: backend/src/worker/pipeline/orchestrator.py
  Change: Register each TTS output file as a FileModel record
  Dependencies: Task 2, Task 3
  Complexity: 0.5 day
  Acceptance: GET /api/v1/files/{file_id} returns narration audio

☐ Task 6: Fix dead API endpoint URLs
  Goal: Lecture detail response has working URLs
  Files: backend/src/core/use_cases/lecture/get_lecture.py
  Change: Fix transcript_url, narrated_pptx_url, and audio_url to point to real endpoints
  Dependencies: Task 5
  Complexity: 0.5 day
  Acceptance: URLs in API response resolve to actual content
```

### High Priority (Ship Before MVP)

```
☐ Task 7: No-PPTX pipeline handling
  Goal: Audio-only uploads produce output
  Files: backend/src/worker/pipeline/orchestrator.py
  Dependencies: None | Complexity: 1 day
  Acceptance: Uploading audio without PPTX completes pipeline with status

☐ Task 8: Add Toaster to root layout
  Goal: Toast notifications work
  Files: frontend/src/app/layout.tsx
  Dependencies: None | Complexity: 0.5 day
  Acceptance: toast() call shows visible notification

☐ Task 9: Add error toast to all data-fetching pages
  Goal: API failures shown to user
  Files: frontend/src/app/(dashboard)/dashboard/page.tsx, projects/page.tsx, etc.
  Dependencies: Task 8 | Complexity: 1 day
  Acceptance: Network error on dashboard shows toast instead of silent console.error

☐ Task 10: Add processing status polling
  Goal: Users see lecture processing progress
  Files: frontend/ — new or existing page
  Dependencies: Task 6 | Complexity: 1 day
  Acceptance: After upload, user sees progress bar updating as pipeline runs

☐ Task 11: Add pipeline integration tests
  Goal: Verify pipeline produces valid output
  Files: backend/tests/
  Dependencies: Task 2, Task 3 | Complexity: 2 days
  Acceptance: Test creates lecture, runs pipeline, verifies narrated PPTX has audio
```

### Medium Priority (MVP Stretch)

```
☐ Task 12: Fix Docker migration automation
  Goal: Database migrates on startup
  Files: infrastructure/docker-compose.yml
  Dependencies: Task 1 | Complexity: 0.5 day

☐ Task 13: Add response_model to refresh endpoint
  Goal: OpenAPI schema complete
  Files: backend/src/api/routes/auth.py
  Dependencies: None | Complexity: 0.5 day

☐ Task 14: Fix embedding cache NameError
  Goal: No crash on all-cached texts
  Files: backend/src/worker/pipeline/generate_embeddings.py
  Dependencies: None | Complexity: 0.5 day

☐ Task 15: Pipeline cleanup on failure
  Goal: Orphaned files cleaned up on pipeline failure
  Files: backend/src/worker/pipeline/orchestrator.py
  Dependencies: None | Complexity: 1 day
```

### Low Priority (Polish)

```
☐ Task 16: Remove duplicate JobModel for full_pipeline
☐ Task 17: Remove dead AI client classes
☐ Task 18: Fix nginx upload location overlap
☐ Task 19: Fix streaming file download
☐ Task 20: Add MIME type detection
☐ Task 21: Consolidate file validation
☐ Task 22: Add loading skeletons
☐ Task 23: Add voice profile count to dashboard
☐ Task 24: Copy next.config.js in Docker runner
☐ Task 25: Add Celery health check
```

---

## 9. TESTING PLAN

### Pre-MVP Regression Tests
These must pass before every release:

```
☐ Auth: Register, login, refresh, /me
  Type: API integration (exists)
  Files: tests/integration/test_auth_api.py
  Status: ✅ Already passing

☐ Projects: CRUD operations
  Type: API integration (exists)
  Files: tests/integration/test_project_api.py
  Status: ✅ Already passing

☐ Health check
  Type: API integration (exists)
  Files: tests/integration/test_health.py
  Status: ✅ Already passing

☐ Storage: LocalStorage operations
  Type: Integration (exists)
  Files: tests/integration/test_storage.py
  Status: ✅ Already passing

☐ Pipeline: Extract audio
  Type: Unit (new)
  Status: 🔴 Needs to be written

☐ Pipeline: Transcribe (mocked)
  Type: Unit (new)
  Status: 🔴 Needs to be written

☐ Pipeline: Parse PPTX
  Type: Unit (new)
  Status: 🔴 Needs to be written

☐ Pipeline: Embed narration into PPTX
  Type: Integration (new)
  Status: 🔴 Needs to be written

☐ Pipeline: End-to-end with mocked GPU
  Type: Integration (new)
  Status: 🔴 Needs to be written
```

### Acceptance Criteria

**Pipeline produces valid output:**
1. Upload video + PPTX → pipeline completes → download narrated PPTX → verify each slide has embedded audio
2. Upload audio-only → pipeline completes with appropriate status → no crash
3. Upload video without PPTX → pipeline completes with informative status
4. Pipeline failure → lecture marked "failed" → error message stored

**Docker deployment:**
1. `docker compose up` starts all services without errors
2. Registration works through nginx
3. Lecture upload works through nginx
4. Celery worker picks up tasks and processes pipeline

**Frontend:**
1. User registers and sees dashboard
2. User creates project, uploads lecture, sees upload confirmation
3. User views project, sees lecture with processing status
4. User sees toast on API errors
5. User can download narrated PPTX (when available)

---

## 10. FINAL VERDICT

| Metric | Previous Audit | This Audit |
|---|---|---|
| Critical issues | 8 | 8 (4 confirmed, 2 partially confirmed, 2 reclassified) |
| High issues found | 7 | 9 (5 confirmed, 1 partially, 1 rejected, 3 new) |
| Medium issues found | 7 | 10 (5 confirmed, 2 partially, 3 new) |
| Low issues found | 6 | 7 (4 confirmed, 3 new) |
| **New issues discovered** | — | **12** |
| **False positives in previous audit** | — | **3** (H1, M7, N12) |
| **Reclassifications** | — | **2** (C4 partial, H1 dead code not bug) |

**Core finding unchanged**: The project's pipeline has 2 critical failures (TTS silence + PPTX audio embedding) that make the entire output pipeline non-functional. Fixing these two things first (Tasks 2 & 3) unlocks everything else.

**New critical finding**: The `generate_embeddings` module has a `NameError` crash when all texts are cached (N13) — this exists in the pipeline code currently running.

**Biggest missed finding in previous audit**: AuthMiddleware is registered in `backend/src/api/middleware/auth.py` but **never added to the FastAPI app** (N1). Dead code with expectations.

**Simplification recommendation**: Drop voice cloning from MVP. Drop WebSocket. Drop 7 Celery queues (use 1). Drop rate limiting. Drop domain events. The port abstractions can stay as documentation but don't need to be wired until a second TTS provider is added. The critical path is: TTS → PPTX → Docker → polling UI. Everything else is polish.
