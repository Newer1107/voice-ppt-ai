# MVP Pipeline Recovery Plan

---

## 1. End-to-End Execution Trace

```
───────────────────────────────────────────────────────────────────────
FRONTEND UPLOAD BUTTON
───────────────────────────────────────────────────────────────────────
frontend/src/app/(dashboard)/lectures/upload/page.tsx:94-127
  handleSubmit() builds FormData with:
    project_id, title, video_file?, audio_file?, pptx_file?, voice_profile_id?
  →
  lecturesApi.upload(formData, setProgress)
    frontend/src/lib/api/lectures.ts:12-21
    apiClient.post('/api/v1/lectures/upload', formData, { onUploadProgress })
      → client.ts: axios instance with baseURL=NEXT_PUBLIC_API_URL
                              Auth header from zustand store
                              Content-Type: multipart/form-data
  401? → refresh interceptor → /api/v1/auth/refresh → retry → /api/v1/auth/login

───────────────────────────────────────────────────────────────────────
BACKEND API: POST /api/v1/lectures/upload
───────────────────────────────────────────────────────────────────────
backend/src/api/routes/lectures.py:33-74
  Depends(get_current_user)     → validates JWT, returns UserModel
  Depends(get_db)               → asyncpg session (commit on success)
  Depends(get_storage)          → LocalStorage(root=STORAGE_ROOT)
  Reads UploadFile contents into memory (video_data, audio_data, pptx_data)
  →
  UploadLectureUseCase.execute(...)
    backend/src/core/use_cases/lecture/upload_lecture.py:40-144
    STEP 1: find_by_user_and_id(user_id, project_id) → validates project exists
    STEP 2: Validate extensions + file sizes
    STEP 3: storage.store(path, content) → LocalStorage._resolve().store()
            Creates files at: data/storage/projects/{pid}/lectures/{lid}/source/{video.mp4|audio.mp3|slides.pptx}
    STEP 4: Create LectureModel(project_id, title, input_type, status="pending",
                                video_path, audio_path, pptx_path, voice_profile_id)
    STEP 5: Create JobModel(lecture_id, job_type="full_pipeline", status="pending",
                            payload={extract_audio, has_pptx})
    STEP 6: Create FileModel for each uploaded file (user_id, lecture_id, storage_path, sha256)
    STEP 7: session.flush()
    STEP 8: process_lecture_pipeline.apply_async(args=[lid], countdown=3)
            → Celery dispatch with 3s delay
  Returns 202 UploadLectureResponse(id, title, input_type, status="pending", job_id, created_at)
  
  get_db() commits the session (or rolls back on exception)

───────────────────────────────────────────────────────────────────────
CELERY: process_lecture_pipeline(lecture_id_str)
───────────────────────────────────────────────────────────────────────
backend/src/worker/tasks/lecture_tasks.py:18-43
  @celery_app.task(bind=True, max_retries=3, acks_late=True)
  →
  _run_pipeline(lecture_id)
    get_sync_session() → sync psycopg2 session from same DATABASE_URL (asyncpg→psycopg2)
    run_full_pipeline(session, lid, settings)
    session.commit() / session.rollback() on error

───────────────────────────────────────────────────────────────────────
PIPELINE ORCHESTRATOR
───────────────────────────────────────────────────────────────────────
backend/src/worker/pipeline/orchestrator.py:117-394

STAGE 1: Extract Audio (orchestrator.py:139-152)
  if lecture.video_path AND NOT lecture.audio_path:
    src_path = data/storage/{video_path}
    audio_result = extract_audio(src_path, abs_out) 
      → ffprobe for audio stream → ffmpeg -i video -vn -acodec pcm_s16le -ar 16000 -ac 1 loudnorm output.wav
      → returns AudioExtractionResult(duration_seconds, audio_path)
    lecture.audio_path = rel_out
    lecture.duration_seconds = int(duration)
  elif lecture.audio_path: (already has audio → use existing)
    audio_result = dummy object with duration
  else: raise ValueError
  
  VERDICT: ✅ WORKS (requires ffmpeg)

STAGE 2: Transcribe (orchestrator.py:158-180)
  audio_abs = data/storage/{lecture.audio_path}
  transcript = transcribe_audio(audio_abs)
    → httpx.post(f"{AI_SERVICE_URL}/ai/v1/transcribe", files={audio_file}, timeout=600)
    → GPU Server: Whisper transcription → returns segments with timestamps
  Creates TranscriptSegmentModel rows in DB
  
  VERDICT: ✅ WORKS (requires GPU server running)

STAGE 3: Parse PPTX (orchestrator.py:186-209)
  if lecture.pptx_path:
    pptx_result = parse_pptx(pptx_abs)
      → python-pptx: Presentation(pptx_path) → iterate slides → extract text, notes, layout
    Creates SlideModel rows in DB
    slides_data = [{slide_number, raw_text, notes}, ...]
  else:
    slides_data = []
    "No PPTX to parse"
  
  VERDICT: ✅ WORKS (requires PPTX uploaded)

STAGE 4: Generate Embeddings (orchestrator.py:215-228)
  if slides_data: (empty if no PPTX!)
    slide_texts + seg_texts → all_texts
    generate_embeddings(all_texts)  ← RETURN VALUE DISCARDED
      → httpx.post(f"{AI_SERVICE_URL}/ai/v1/embed", json={texts, normalize=true})
      → GPU Server: BGE-M3 encoding → embeddings stored in _EMBEDDING_CACHE (in-memory)
  
  VERDICT: ⚠️ WORKS but results thrown away (stage 5 recomputes)

STAGE 5: Align Transcript (orchestrator.py:234-269)
  if slides_data AND transcript.segments: (BOTH REQUIRED)
    alignment = align_transcript(seg_dicts, slides_data)
      → generate_embeddings(slide_texts) ← HTTP call again
      → generate_embeddings(seg_texts)   ← HTTP call again
      → cosine similarity matrix
      → httpx.post(f"{AI_SERVICE_URL}/ai/v1/align", ...) for LLM verification
      → fallback to embedding-only if LLM unavailable
    Updates transcript_segments.slide_id in DB
  else:
    "No alignment needed" (skip)
  
  VERDICT: ⚠️ WORKS if slides_data AND transcript exist. SKIPS otherwise.

STAGE 6: Generate Narration (orchestrator.py:275-317)
  if slides_data: (empty if no PPTX → SKIPS)
    Builds slides_with_transcripts (slide + aligned transcript segments)
    narrations = generate_narrations(lecture.title, slides_with_transcripts)
      → httpx.post(f"{AI_SERVICE_URL}/ai/v1/generate-narration", json={...}, timeout=600)
      → GPU Server: Qwen per-slide narration via SGLang → returns script_text
    Creates NarrationModel rows in DB
  
  VERDICT: ⚠️ SKIPS if no PPTX. WORKS if PPTX exists (requires GPU + SGLang).

STAGE 7: Generate TTS (orchestrator.py:323-343)
  narrations_db = all NarrationModel for lecture
  for each narration:
    tts_result = generate_slide_tts(text, output_path, slide_number)
      → httpx.post(f"{AI_SERVICE_URL}/ai/v1/tts", files={text}, timeout=300)
      → GPU Server: ⚠️ RETURNS SILENCE (placeholder, not real F5-TTS)
      → Saves response bytes to output_path
    ndb.audio_path = rel_audio
  
  VERDICT: 🔴 PRODUCES SILENCE FILES

STAGE 8: Embed Narration into PPTX (orchestrator.py:349-372)
  if lecture.pptx_path:
    slide_audio_map = {slide_number: abs_audio_path for each narration with audio}
    embed_narration_into_pptx(pptx_path, slide_audio_map, output_path)
      → python-pptx: Presentation(pptx_path)
      → slide.shapes.add_movie(audio_path, 0, 0, 1, 1)  ← WRONG API for audio
      → ⚠️ Creates VIDEO shape with external file reference, not embedded audio
    lecture.narrated_pptx_path = output_path
  
  VERDICT: 🔴 CREATES NON-FUNCTIONAL PPTX

COMPLETION (orchestrator.py:378-383)
  lecture.status = "completed"
  session.flush()
  
───────────────────────────────────────────────────────────────────────
USER DOWNLOADS NARRATED PPTX
───────────────────────────────────────────────────────────────────────
frontend/src/app/(dashboard)/projects/[id]/page.tsx
  projectsApi.get(id) → GET /api/v1/projects/{id}
    → GetProjectUseCase returns ProjectDetailResponse with lectures[]
    Each LectureSummary has status but NO download URL
  → NO download button in UI
  → Even if user calls GET /api/v1/files/{file_id}, narration audio files were
    NEVER registered as FileModel records → 404

frontend/src/app/(dashboard)/dashboard/page.tsx
  No polling → user never sees status updates
  Console.error on failure → no toast
```

---

## 2. Pipeline Blocker Report

### Category A: Project Cannot Start

**A1. Import path mismatch in Docker**
- Files: `backend/Dockerfile:16`, `backend/main.py:2-14`
- Root cause: `WORKDIR /app` = `backend/` but imports use `from backend.src.*`. Python can't resolve the package.
- Impact: `docker compose up backend` crashes immediately.
- Severity: **BLOCKER** — Docker deployment impossible.
- Confidence: **100%**
- Fix: Set `PYTHONPATH=/app/..` in Dockerfile before CMD, or change CMD to `PYTHONPATH=/app/.. uvicorn backend.main:app`

**A2. `.env` file may not exist**
- Files: `infrastructure/docker-compose.yml:33`, `.env.example`
- Root cause: docker-compose references `../.env` but only `.env.example` exists. No `.env` file.
- Impact: All env vars use defaults from `settings.py`. DB password `devpassword` might not match Docker postgres default.
- Severity: **BLOCKER** — Database connection fails.
- Confidence: **90%**
- Fix: `cp .env.example .env` or docker-compose provides defaults.

### Category B: Upload Cannot Complete

**B1. Frontend API URL double `/api` in Docker**
- Files: `infrastructure/docker-compose.yml:28`, `frontend/src/lib/api/client.ts:4`
- Root cause: `NEXT_PUBLIC_API_URL=http://localhost:80/api` + paths like `/api/v1/auth/login` → `http://localhost:80/api/api/v1/auth/login`. Inside Docker, `localhost:80` is the container itself, not nginx.
- Impact: All API calls fail in Docker Compose.
- Severity: **BLOCKER** — Can't register, login, or upload in Docker.
- Confidence: **100%**
- Fix: Set `NEXT_PUBLIC_API_URL=http://nginx:80` (no `/api` suffix) and ensure nginx is on the same network.

### Category C: Pipeline Cannot Execute

**C1. Celery worker can't import tasks**
- Files: `backend/src/worker/celery_app.py:48`, `backend/src/worker/tasks/lecture_tasks.py`
- Root cause: `celery_app.conf.imports = ["backend.src.worker.tasks.lecture_tasks"]`. If PYTHONPATH doesn't include the project root, Celery can't find `backend.src.*`.
- Impact: `celery -A src.worker.celery_app worker` fails at startup.
- Severity: **BLOCKER** — Pipeline never starts.
- Confidence: **95%**
- Fix: Run Celery from project root with proper PYTHONPATH. The `start.sh` script does this correctly.

**C2. GPU server must be reachable**
- Files: `backend/src/config/settings.py:34`, `backend/src/worker/pipeline/transcribe.py:39`
- Root cause: `AI_SERVICE_URL` defaults to `http://gpu-service:8001`. Pipeline stages 2, 4, 5, 6, 7 all make HTTP calls to this URL. If the GPU server isn't running or reachable, stages fail.
- Impact: Everything after Stage 1 fails.
- Severity: **BLOCKER** — Pipeline stops at Stage 2 (or falls through but produces junk).
- Confidence: **100%**
- Fix: Ensure `AI_SERVICE_URL` points to a running GPU server. For local dev without GPU, the pipeline will crash at Stage 2.

### Category D: Pipeline Executes But Output Is Wrong

**D1. TTS returns silence**
- Files: `ai-server/service/src/main.py:348-368`
- Root cause: F5-TTS was never integrated. The `/ai/v1/tts` endpoint generates `b"\x00\x00" * num_samples` — silence. `_load_tts()` returns a config dict, not a model.
- Impact: All narration audio files are silent WAVs. PPTX has no real audio.
- Severity: **BLOCKER** — Core feature missing.
- Confidence: **100%**
- Fix: Implement real TTS (F5-TTS or cloud API).

**D2. PPTX audio embedding uses wrong API**
- Files: `backend/src/worker/pipeline/embed_narration.py:76`
- Root cause: `slide.shapes.add_movie(audio_path, ...)` creates a VIDEO relationship, not audio. Stores external file path (absolute server path), not embedded audio bytes.
- Impact: Output PPTX doesn't play audio correctly.
- Severity: **BLOCKER** — Output unusable.
- Confidence: **100%**
- Fix: Use OpenXML (python-pptx low-level) to add proper audio media relationships.

**D3. No-PPTX uploads produce zero output**
- Files: `backend/src/worker/pipeline/orchestrator.py:155,190,275,349`
- Root cause: If no PPTX uploaded, `slides_data` stays `[]`. Stages 5 (alignment), 6 (narration), and 8 (embedding) all check `if slides_data:` and skip. Stage 7 (TTS) has no narrations to process. Pipeline completes with status="completed" but zero narrations, zero TTS files, zero output PPTX.
- Impact: Audio-only uploads complete with no useful output.
- Severity: **BLOCKER** — Audio-only workflow broken.
- Confidence: **100%**
- Fix: Generate a synthetic single slide when no PPTX is present, or produce audio-only output.

**D4. Narration audio files not registered as FileModel records**
- Files: `backend/src/worker/pipeline/orchestrator.py:323-343`, `backend/src/core/use_cases/lecture/get_lecture.py:82`
- Root cause: TTS output is saved to disk but never added to the `files` table. The `audio_url` in `get_lecture.py` points to `/api/v1/files/{narration_id}` which doesn't exist in the files table.
- Impact: Narration audio can't be downloaded via the API.
- Severity: **HIGH** — Can't play or download narration audio.
- Confidence: **100%**
- Fix: Create FileModel rows for each TTS output during Stage 7.

**D5. Dead download URLs in lecture detail**
- Files: `backend/src/core/use_cases/lecture/get_lecture.py:86-91`
- Root cause: `transcript_url` → `/api/v1/transcripts/{id}` (no route). `narrated_pptx_url` → `/api/v1/files/download/{id}` (no route).
- Impact: Links in API response return 404.
- Severity: **HIGH** — Frontend can't navigate to output.
- Confidence: **100%**
- Fix: Fix URLs to point to `/api/v1/files/{file_id}` with actual FileModel IDs.

### Category E: Output Reaches User Incorrectly

**E1. No frontend download or status UI**
- Files: `frontend/src/app/(dashboard)/projects/[id]/page.tsx:100-140`
- Root cause: Project detail page shows a list of lectures with status badges but no download button for narrated PPTX, no audio playback, no polling for status updates.
- Impact: User can't download or listen to the output.
- Severity: **BLOCKER** — MVP flow not complete.
- Confidence: **100%**
- Fix: Add download link to narrated PPTX when status == "completed". Add polling for status updates.

**E2. No error feedback in frontend**
- Files: `frontend/src/app/(dashboard)/dashboard/page.tsx:30-32`, `projects/page.tsx:20-23`, `projects/[id]/page.tsx:24-26`
- Root cause: `.catch(err) { console.error(...) }` pattern everywhere. User never sees errors.
- Impact: Silent failures, infinite loading spinners.
- Severity: **HIGH** — UX broken.
- Confidence: **100%**
- Fix: Show user-facing error messages or toasts.

---

## 3. Root Cause Summary

| Blocker | Category | Root File | What's Wrong |
|---|---|---|---|
| A1 | Start | `Dockerfile` | No PYTHONPATH |
| A2 | Start | `.env` | File may not exist |
| B1 | Upload | `docker-compose.yml` | Wrong API URL |
| C1 | Pipeline | `celery_app.py` | Import path |
| C2 | Pipeline | `settings.py` | GPU server unreachable |
| D1 | Output | `ai-server/main.py:348` | TTS is silence |
| D2 | Output | `embed_narration.py:76` | Wrong PPTX API |
| D3 | Output | `orchestrator.py:275` | No-PPTX path skipped |
| D4 | Output | `orchestrator.py:323` | No FileModel for audio |
| D5 | Output | `get_lecture.py:86` | Dead URLs |
| E1 | UX | `projects/[id]/page.tsx` | No download button |
| E2 | UX | All pages | No error toasts |

---

## 4. Minimum Implementation Order

### Task 1: Fix Docker Startup
**Goal**: Backend and Celery worker start without import errors.
- Files: `backend/Dockerfile`
- Change: Add `ENV PYTHONPATH=/app/..` or `ENV PYTHONPATH="${PYTHONPATH}:/app/.."` before the CMD
- Also: `cp .env.example .env` in setup instructions
- Verify: `docker compose up backend` starts without ImportError
- Pass: Health endpoint responds
- Fail: Container exits with ModuleNotFoundError

### Task 2: Fix Frontend API URL for Docker
**Goal**: Frontend API calls reach the backend through nginx.
- Files: `infrastructure/docker-compose.yml`
- Change: `NEXT_PUBLIC_API_URL=http://nginx:80` (use Docker service name, remove `/api`)
- Verify: Frontend loads login page, register creates user
- Pass: Registration returns 201 through nginx
- Fail: API calls return 404 or connection refused

### Task 3: Fix TTS to Produce Real Speech
**Goal**: `/ai/v1/tts` returns actual speech audio.
- Files: `ai-server/service/src/main.py` (the `synthesize()` function, lines 335-370)
- Options (pick one):
  - **Option A**: Integrate F5-TTS with real inference (`from f5_tts.infer import InferenceSession`)
  - **Option B**: Call a cloud TTS API (ElevenLabs, OpenAI TTS) and return the audio
  - **Option C**: Use a local library like `pyttsx3` or `gTTS` (lower quality but functional)
- Verify: `curl -X POST -F "text=Hello, this is a test" http://localhost:8001/ai/v1/tts -o test.wav` → `ffprobe test.wav` shows duration > 0
- Pass: WAV file contains speech audio
- Fail: WAV file is silence or request errors

### Task 4: Fix PPTX Audio Embedding
**Goal**: Narrated PPTX properly embeds audio in each slide.
- Files: `backend/src/worker/pipeline/embed_narration.py`
- Change: Replace `slide.shapes.add_movie(audio_path, ...)` with proper OpenXML audio embedding:
  1. Create a `media` relationship in the slide XML with the audio file
  2. Create a `timing` node that triggers playback on slide entry
  3. The audio data must be stored in the PPTX ZIP archive, not referenced by external path
- Verify: Open output PPTX → each slide has an audio icon → audio plays on slide entry
- Pass: Audio plays correctly in PowerPoint/Keynote
- Fail: Audio icon missing, audio doesn't play, or references broken path

### Task 5: Handle No-PPTX Uploads
**Goal**: Audio-only uploads complete with meaningful output.
- Files: `backend/src/worker/pipeline/orchestrator.py`
- Change: When no PPTX is present, generate a synthetic single slide or skip narration stages gracefully without marking the lecture as "completed" with zero output. Options:
  - Create a minimal "Audio Lecture" slide with the lecture title
  - Generate narration for the full transcript as one block (no slide alignment needed)
  - Produce an audio file only (no PPTX output)
- Verify: Upload audio-only → pipeline completes → status is "completed" or meaningful error
- Pass: Pipeline doesn't silently produce zero output
- Fail: Pipeline marks "completed" with no narrations/output

### Task 6: Register Narration Audio as FileModels
**Goal**: Narration audio files can be downloaded via the API.
- Files: `backend/src/worker/pipeline/orchestrator.py` (after Stage 7 TTS generation)
- Change: After each `generate_slide_tts()` call, create a `FileModel` record:
  ```
  FileModel(user_id=lecture.user_id,
            lecture_id=lecture_id,
            file_type="narration_audio",
            original_name=f"slide_{sn:03d}.wav",
            storage_path=rel_audio,
            file_size_bytes=os.path.getsize(abs_audio),
            mime_type="audio/wav")
  ```
- Verify: `GET /api/v1/files/{file_id}` returns the WAV audio
- Pass: Audio file downloads correctly
- Fail: 404 or wrong content

### Task 7: Fix Dead API URLs
**Goal**: Lecture detail response has working download URLs.
- Files: `backend/src/core/use_cases/lecture/get_lecture.py:86-91`
- Change: 
  - `transcript_url` → create a real endpoint or return null
  - `narrated_pptx_url` → point to `/api/v1/files/{filemodel_id}` for the narrated PPTX FileModel
  - `audio_url` → point to `/api/v1/files/{filemodel_id}` for each narration's FileModel
- Verify: URLs in `GET /api/v1/lectures/{id}` response resolve to actual content
- Pass: Each URL returns 200 with the correct file
- Fail: Any URL returns 404

### Task 8: Add Frontend Download and Status
**Goal**: Users can see processing progress and download output.
- Files: `frontend/src/app/(dashboard)/projects/[id]/page.tsx`
- Changes:
  - Poll `GET /api/v1/lectures/{id}/status` every 5 seconds for lectures with status="processing"
  - Show a progress bar or status indicator
  - When status = "completed", show download button for narrated PPTX
  - Link download button to `/api/v1/files/{filemodel_id}` for the output PPTX
- Verify: Upload lecture → see progress update → see download button → click to download
- Pass: End-to-end flow from upload to download works
- Fail: Infinite "processing" or no download button

### Task 9: Add Error Toasts
**Goal**: Users see error messages instead of silent failures.
- Files: `frontend/src/app/layout.tsx` (add `<Toaster />`), all data-fetching pages (replace catch blocks)
- Change: Add `sonner` `<Toaster />` to root layout. Replace `console.error()` with `toast.error()` in all catch blocks.
- Verify: Disconnect backend → see toast message on dashboard load
- Pass: User sees error notification
- Fail: Console-only error message

---

## 5. MVP Readiness Score

After completing Tasks 1-9:

| Flow Step | Now | After Fix | After Tasks |
|---|---|---|---|
| Backend starts (Docker) | ❌ | ✅ | Task 1 |
| Register/Login | ✅ | ✅ | — |
| Create project | ✅ | ✅ | — |
| Upload lecture | ✅ | ✅ | — |
| Extract audio | ✅ | ✅ | — |
| Transcribe | ✅ | ✅ | — |
| Parse PPTX | ✅ | ✅ | — |
| Align transcript | ⚠️ (needs GPU) | ⚠️ | — |
| Generate narration | ⚠️ (needs GPU) | ⚠️ | — |
| TTS produces speech | ❌ Silence | ✅ | Task 3 |
| PPTX has audio | ❌ Broken | ✅ | Task 4 |
| No-PPTX uploads | ❌ Silent fail | ✅ | Task 5 |
| Download narrated PPTX | ❌ 404 | ✅ | Task 6, 7 |
| Frontend shows status | ❌ No polling | ✅ | Task 8 |
| Errors shown to user | ❌ console | ✅ | Task 9 |
| Docker end-to-end | ❌ | ✅ | Task 1, 2 |

**MVP Readiness: 2/10 → 9/10 after tasks**

---

## 6. Verification Checklist

### After Each Task, Run This:

```
Task 1: docker compose build backend && docker compose up backend
  → Container runs, health endpoint responds at http://localhost:8000/api/v1/health

Task 2: docker compose up -d
  → Frontend loads at http://localhost
  → Can register, login, create project through nginx

Task 3: curl -X POST -F "text=Hello world test narration" \
         http://gpu-server:8001/ai/v1/tts -o test.wav
  → ffprobe test.wav → streams 1, duration > 0
  → Play test.wav → hear speech

Task 4: python -c "
  from pptx import Presentation
  from backend.src.worker.pipeline.embed_narration import embed_narration_into_pptx
  result = embed_narration_into_pptx('test.pptx', {1: 'test.wav'}, 'out.pptx')
  prs = Presentation('out.pptx')
  print(len(prs.slides))  # Should match original
  "
  → Open out.pptx in PowerPoint → audio plays on slide 1

Task 5: Upload audio-only lecture → pipeline completes → status="completed"
  → lecture.duration_seconds != null
  → Non-empty response from GET /api/v1/lectures/{id}

Task 6: GET /api/v1/files/{file_id} where file_id is from narration FileModel
  → 200 OK, Content-Type: audio/wav, body is valid WAV

Task 7: GET /api/v1/lectures/{id}
  → narrated_pptx_url and audio_url resolve to actual files

Task 8: Upload lecture in frontend → see progress → see download button
  → Click download → browser downloads narrated PPTX → file is valid

Task 9: Disconnect backend → dashboard shows error toast
  → No infinite loading spinners
```

---

## 7. Execution Order Summary

```
Task 1: Fix Docker PYTHONPATH           →  0.5 day  →  Backend starts
Task 2: Fix frontend API URL            →  0.5 day  →  Upload works in Docker
Task 3: Implement real TTS              →  1-3 days →  Audio is real speech
Task 4: Fix PPTX audio embedding        →  1 day    →  Output PPTX works
Task 5: Handle no-PPTX uploads          →  1 day    →  Audio-only works
Task 6: Register narration FileModels   →  0.5 day  →  Audio downloadable
Task 7: Fix dead API URLs               →  0.5 day  →  All links work
Task 8: Frontend download + status      →  1 day    →  User sees progress
Task 9: Error toasts                    →  0.5 day  →  User sees errors

Total: 6-9 days
```

**Critical path**: Task 3 → Task 4 → Task 6 → Task 7 → Task 8 (core output pipeline)
**Parallel**: Task 1 + Task 2 (Docker), Task 5 (handling), Task 9 (toasts)

Ignore everything else until these 9 tasks are verified working end-to-end.
