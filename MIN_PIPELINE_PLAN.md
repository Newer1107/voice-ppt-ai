# Minimum Viable Pipeline Recovery

## Execution Trace

```
FRONTEND (upload page)
  lecturesApi.upload(formData) → POST /api/v1/lectures/upload

BACKEND (routes/lectures.py:33-74)
  get_current_user → validates JWT
  get_db → asyncpg session
  get_storage → LocalStorage
  Reads UploadFile → memory
  → UploadLectureUseCase.execute()

USE CASE (upload_lecture.py:40-144)
  find_by_user_and_id → validate project
  storage.store(path, bytes) → write to disk
  Create LectureModel(status="pending")
  Create JobModel(job_type="full_pipeline")
  Create FileModel for each upload
  session.flush()
  process_lecture_pipeline.apply_async(args=[lid], countdown=3)
  ↑ Celery dispatch
  Return 202 UploadLectureResponse

CELERY TASK (lecture_tasks.py:18-43)
  get_sync_session() → psycopg2
  run_full_pipeline(session, lid, settings)
  session.commit()

ORCHESTRATOR (orchestrator.py:117-394)

  Stage 1 — Extract Audio (orchestrator.py:139-152)
    extract_audio(): ffprobe → ffmpeg → AudioExtractionResult
    ✅ WORKS (needs ffmpeg installed)

  Stage 2 — Transcribe (orchestrator.py:158-180)
    transcribe_audio(): httpx → GPU Whisper → segments
    ✅ WORKS (needs GPU server at AI_SERVICE_URL)

  Stage 3 — Parse PPTX (orchestrator.py:186-209)
    parse_pptx(): python-pptx → ParsedSlide[]
    ✅ WORKS (needs PPTX uploaded)

  Stage 4 — Embeddings (orchestrator.py:215-228)
    generate_embeddings(): httpx → GPU BGE-M3
    ⚠️ Return value discarded (results recomputed in Stage 5)
    ✅ Still works, just wasteful

  Stage 5 — Align (orchestrator.py:234-269)
    align_transcript(): generate_embeddings() → cos sim → httpx → GPU Qwen
    ✅ WORKS (needs slides + segments, GPU server)

  Stage 6 — Narration (orchestrator.py:275-317)
    generate_narrations(): httpx → GPU Qwen → script_text
    ✅ WORKS (needs slides_data, GPU server)

  Stage 7 — TTS (orchestrator.py:323-343)
    generate_slide_tts(): httpx → GPU → save response bytes
    🔴 F5-TTS NEVER INTEGRATED → server returns silence

  Stage 8 — Embed into PPTX (orchestrator.py:349-372)
    embed_narration_into_pptx(): python-pptx → add_movie()
    🔴 add_movie() creates VIDEO shape, not audio
    🔴 Stores external absolute file path, not embedded bytes

  Completion (orchestrator.py:378-383)
    lecture.status = "completed", session.flush()

POST-PIPELINE
  lecture.narrated_pptx_path = absolute path (not a FileModel)
  narration audio files on disk (no FileModel records)
  GET /api/v1/lectures/{id}
    → audio_url = /api/v1/files/{narration.id} ← NOT a file ID → 404
    → narrated_pptx_url = /api/v1/files/download/{lecture.id} ← no route → 404
  Frontend project detail page
    → Shows status badge, NO download button
    → No poll for status updates
    → Silent console.error on failure (no toast)
```

---

## Blocker Identification

### Verified: Stages 1-6 all execute and produce correct intermediate data.
### Three pipeline killers:

**R1 — TTS produces silence (Stage 7)**
- File: `ai-server/service/src/main.py` lines 335-370
- Function: `synthesize()` at `/ai/v1/tts`
- Root cause: F5-TTS import is commented out. `_load_tts()` returns a config dict (not a model). The endpoint guesses duration from word count and fills a WAV with zero bytes. Every narration gets a silent audio file.
- Impact: All `.wav` output files are silence. Stage 8 embeds silence. Final output has no speech.
- Blocks: Stage 8 (no real audio to embed), download (silence is useless), MVP (core feature).
- Confidence: 100%

**R2 — PPTX audio embedding uses wrong API (Stage 8)**
- File: `backend/src/worker/pipeline/embed_narration.py` line 76
- Function: `embed_narration_into_pptx()`, specifically `slide.shapes.add_movie(audio_path, 0, 0, 1, 1)`
- Root cause: `add_movie()` creates a **video** relationship in the OpenXML, not audio. The `audio_path` argument stores the server's absolute path as an external reference — the bytes read into `audio_bytes` on line 70 are never used. The output PPTX references a path like `/Users/.../data/storage/projects/.../slide_001.wav` which only exists on the server, won't play when the file is opened elsewhere.
- Impact: Output PPTX does not play narration audio. MVP fails.
- Blocks: Download (PPTX is broken).
- Confidence: 100%

**R3 — No FileModel records created for pipeline outputs**
- File: `backend/src/worker/pipeline/orchestrator.py` lines 323-372
- Root cause: Stage 7 saves `ndb.audio_path` (relative path string on the NarrationModel). Stage 8 saves `lecture.narrated_pptx_path` (absolute path string on the LectureModel). Neither creates a `FileModel` row. The `/api/v1/files/{file_id}` endpoint only finds files registered in the `files` table.
- Impact: No way to download outputs via the API.
- Blocks: Download (404).
- Confidence: 100%

**R4 — API response contains dead download URLs**
- File: `backend/src/core/use_cases/lecture/get_lecture.py` lines 82-91
- Root cause: Line 82: `audio_url = f"/api/v1/files/{slide.narration.id}"` — uses the narration model's UUID, but the files endpoint expects a `FileModel.id`. Line 90: `narrated_pptx_url = f"/api/v1/files/download/{lecture.id}"` — no route matches `/api/v1/files/download/{id}` (the real route is `/api/v1/files/{id}`). Line 88: `transcript_url = "/api/v1/transcripts/" + str(lecture.id)` — no route at all.
- Impact: Frontend cannot construct download links.
- Blocks: Download (wrong URL format).
- Confidence: 100%

**R5 — Frontend has no download or status UI**
- File: `frontend/src/app/(dashboard)/projects/[id]/page.tsx` lines 74-157
- Root cause: The project detail page renders a lecture list with status badges, but: (1) no download button for narrated PPTX when status=completed, (2) no polling of `GET /api/v1/lectures/{id}/status`, (3) no per-lecture click-through to a detail view. Error handling uses `console.error()` — user sees nothing on failure.
- Impact: User can upload, can see "completed" badge, but cannot download the output.
- Blocks: MVP flow complete (user has no way to get the output).
- Confidence: 100%

**R6 — No-PPTX uploads produce zero output**
- File: `backend/src/worker/pipeline/orchestrator.py` lines 155, 190, 275, 349
- Root cause: `slides_data = []` when no PPTX uploaded. Stage 5 checks `if slides_data and transcript.segments` → skips. Stage 6 checks `if slides_data:` → skips. Stage 8 checks `if lecture.pptx_path:` → skips. Stage 7 runs but finds no `NarrationDbModel` records (because Stage 6 was skipped). Pipeline completes with `status="completed"` and zero narrations, zero audio files, zero output PPTX.
- Impact: Audio-only uploads silently produce nothing.
- Blocks: Audio-only workflow (PPTX uploads work fine).
- Confidence: 100%

### Not Blockers (removed from previous analysis)

- **Docker import path**: Irrelevant for local dev with `start.sh`. `cd "$ROOT"` then `uvicorn backend.main:app` resolves correctly. Only blocks Docker deployment.
- **Frontend API URL double `/api`**: Irrelevant for local dev. `client.ts` defaults to `http://localhost:8000` when `NEXT_PUBLIC_API_URL` is unset. Paths like `/api/v1/auth/login` resolve to `http://localhost:8000/api/v1/auth/login` — correct. Only blocks Docker.
- **Celery import path**: `start.sh` runs `celery -A backend.src.worker.celery_app worker` from project root. `PYTHONPATH` includes the root. Works locally.
- **Embedding cache NameError**: Never triggers in practice because at least one text is always uncached on the first call. Not a real-world blocker.
- **AI port abstractions unused**: Doesn't affect pipeline execution.
- **Domain events dead**: Doesn't affect anything.

---

## Implementation Order

### Task 1 — Fix TTS to produce real speech

**Why**: Stage 7 produces silence. Every downstream step (embedding, download) depends on real audio. This is the root cause of the entire output pipeline failing.

**What breaks without this**: Audio output is silence. PPTX has no speech. MVP fails.

**Files to modify:**
- `ai-server/service/src/main.py` — replace the `synthesize()` function's silence generation with real TTS inference

**Files to inspect only:**
- `backend/src/worker/pipeline/generate_tts.py` — verify it reads the response correctly (it already does — `resp.content` saved to file)
- `backend/src/config/settings.py` — `AI_SERVICE_URL` must point to GPU server, `TTS_SAMPLE_RATE` must match

**Files that must NOT change:**
- Any frontend files
- Any database model files
- Any Celery/pipeline files
- Any repository files

**Implementation options (pick one):**
1. **F5-TTS**: Uncomment `from f5_tts.model import DiT`, implement actual inference. Requires model weights.
2. **Cloud TTS API**: Replace the silence code with `httpx.post("https://api.elevenlabs.io/...")` or similar. Returns real speech bytes.
3. **Local OSS TTS**: Use `gTTS` (Google TTS — needs internet) or `pyttsx3` (offline, lower quality).

**Dependencies**: None.

**Verification:**
```bash
curl -X POST -F "text=This is a test narration for my lecture slides." \
  http://<gpu-server>:8001/ai/v1/tts -o test.wav
ffprobe test.wav  # Duration should be > 0, streams: audio
```
Play `test.wav` — must hear speech, not silence.

**Expected result**: WAV file contains actual synthesized speech.

**Difficulty**: Medium (1-3 days depending on TTS approach).

---

### Task 2 — Fix PPTX audio embedding

**Why**: Stage 8 uses `add_movie()` which creates a video relationship with an external file reference. The output PPTX is broken.

**What breaks without this**: User downloads a PPTX that looks correct but has no working audio.

**Files to modify:**
- `backend/src/worker/pipeline/embed_narration.py` — replace the `slide.shapes.add_movie()` call with proper OpenXML audio embedding

**Files to inspect only:**
- `backend/src/worker/pipeline/orchestrator.py` lines 349-372 — verify the caller passes the right paths (it does)

**Files that must NOT change:**
- Any frontend files
- Any database model files
- Any AI server files
- Any repository files

**Implementation approach**: The PPTX format is a ZIP archive. To embed audio properly:
1. Open the PPTX as a ZIP
2. Copy the audio WAV file into the `ppt/media/` directory inside the ZIP
3. Create a relationship (in `ppt/slides/_rels/slideN.xml.rels`) linking the slide to the media file
4. Add a `<p:timing>` element to the slide XML that triggers audio playback on entry

Or use `python-pptx`'s low-level API:
```python
# Add audio to slide via relationship (pseudo-code)
slide.part.related_parts[audio_part] = AudioPart(audio_path)
# Then add timing element to slide XML
```

**Dependencies**: Task 1 (needs real audio files to embed).

**Verification:**
```python
from pptx import Presentation
prs = Presentation("narrated_lecture.pptx")
print(len(prs.slides))  # Same as original
```
Open in PowerPoint/Keynote — audio icon should appear on each slide, clicking it should play real speech.

**Expected result**: PPTX plays narration audio when opened.

**Difficulty**: Medium (1 day).

---

### Task 3 — Handle no-PPTX uploads

**Why**: The upload page offers PPTX as optional. Uploading audio-only silently produces zero output.

**What breaks without this**: Audio-only uploads complete but produce nothing. User sees "completed" with no output.

**Files to modify:**
- `backend/src/worker/pipeline/orchestrator.py` lines 155, 190, 275, 349 (the `if slides_data:` and `if lecture.pptx_path:` guards)

**Files to inspect only:**
- `backend/src/core/use_cases/lecture/upload_lecture.py` — verifies `input_type` logic (correct)

**Files that must NOT change:**
- Any frontend files (except the upload page's optional PPTX hint — leave it)
- Any AI server files
- Any database model files

**Implementation approach**: When no PPTX is uploaded:
- Skip Stage 3 (parse_pptx)
- Skip Stage 5 (align_transcript) — nothing to align to
- Skip Stage 6 (generate_narration) — no slide-by-slide narration
- Skip Stage 8 (embed_narration) — no PPTX to embed into
- Set lecture status to a meaningful state like "completed (audio only)" or produce a simple output (e.g., concatenated transcript as a text file)
- **Important**: The lecture must NOT be marked "completed" with zero narrations as it currently is

*Simplest fix*: When no PPTX, skip to "completed" with a clear `error_message` or a new `"completed_no_pptx"` status. Or generate a bare-minimum single-slide PPTX with the lecture title and embed the full TTS audio into it.

**Dependencies**: Task 1 (TTS, because even audio-only needs speech).

**Verification**: Upload audio-only → pipeline completes → `GET /api/v1/lectures/{id}` returns status that's not "completed" with zero content.

**Expected result**: Audio-only uploads don't silently produce zero output.

**Difficulty**: Low (0.5-1 day).

---

### Task 4 — Create FileModel records for pipeline outputs and fix download URLs

**Why**: Without FileModel records, the `/api/v1/files/{file_id}` endpoint returns 404 for narration audio and narrated PPTX. The API response contains URLs that point to non-existent routes or wrong IDs.

**What breaks without this**: Download links return 404. MVP flow cannot complete.

**Files to modify:**
- `backend/src/worker/pipeline/orchestrator.py` — after Stage 7 (TTS), create FileModel for each narration audio; after Stage 8, create FileModel for the narrated PPTX
- `backend/src/core/use_cases/lecture/get_lecture.py` lines 82-91 — fix narrated_pptx_url and audio_url to use correct FileModel IDs

**Files to inspect only:**
- `backend/src/api/routes/files.py` — verify the existing `GET /api/v1/files/{file_id}` endpoint. It's correct — accepts a FileModel UUID, checks ownership, returns the file.
- `backend/src/infrastructure/db/repositories/file_repo.py` — verify `get()` method exists (yes, inherited from BaseRepository).

**Files that must NOT change:**
- Any AI server files
- Any frontend files
- Any settings files

**Implementation details:**

In `orchestrator.py`, after Stage 7 (after line 341, before `session.flush()`):
```python
# Create FileModel for each narration audio
for ndb in narrations_db:
    if ndb.audio_path:
        abs_audio = str(storage_root / ndb.audio_path)
        if os.path.exists(abs_audio):
            file_record = FileModel(
                user_id=lecture.user_id,  # need to get user_id from project
                lecture_id=lecture_id,
                file_type="narration_audio",
                original_name=f"slide_{slide.slide_number:03d}.wav",
                storage_path=ndb.audio_path,
                file_size_bytes=os.path.getsize(abs_audio),
                mime_type="audio/wav",
            )
            session.add(file_record)
```

In `orchestrator.py`, after Stage 8 (after line 370):
```python
# Create FileModel for narrated PPTX
if lecture.narrated_pptx_path and os.path.exists(lecture.narrated_pptx_path):
    pptx_file = FileModel(
        user_id=lecture.user_id,
        lecture_id=lecture_id,
        file_type="narrated_pptx",
        original_name=f"{lecture.title}_narrated.pptx",
        storage_path=str(Path(lecture.narrated_pptx_path).relative_to(storage_root)),
        file_size_bytes=os.path.getsize(lecture.narrated_pptx_path),
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    session.add(pptx_file)
```

*Note*: `lecture.user_id` doesn't exist on LectureModel — need to fetch it from the project. The lecture has `project_id`, and ProjectModel has `user_id`.

In `get_lecture.py`, fix the URLs:
- `narrated_pptx_url`: Need to query FileModel where `lecture_id == lecture.id AND file_type == "narrated_pptx"` → return `/api/v1/files/{id}`
- `audio_url`: Need to query FileModel where `lecture_id == lecture.id AND file_type == "narration_audio" AND slide_id == slide.id` → return `/api/v1/files/{id}`
- `transcript_url`: Either create a new endpoint or remove it (set to null) — MVP doesn't need transcript download

**Dependencies**: Task 1 (needs real audio to have files to register), Task 2 (needs working PPTX to register).

**Verification:**
```bash
# After pipeline completes
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/lectures/{lecture_id}
# Output should include working narrated_pptx_url
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/files/{file_id}
# Should return the actual file
```

**Expected result**: All download URLs in the API response resolve to real files.

**Difficulty**: Medium (1 day).

---

### Task 5 — Frontend download button and status polling

**Why**: The project detail page shows lectures with status badges but has no download button, no status polling, and no way to get the output PPTX.

**What breaks without this**: User uploads, waits, sees "completed", but has no way to download. MVP flow is incomplete.

**Files to modify:**
- `frontend/src/app/(dashboard)/projects/[id]/page.tsx` — add:
  1. Status polling for lectures with `status === "processing"` (poll `GET /api/v1/lectures/{id}/status` every 5s)
  2. Download button/link for narrated PPTX when `status === "completed"` (from `GET /api/v1/lectures/{id}` response's `narrated_pptx_url`)
  3. Click-through to a per-lecture detail view (or inline expand)

**Files to inspect only:**
- `frontend/src/lib/api/lectures.ts` — `lecturesApi.get()` and `lecturesApi.getStatus()` already exist
- `frontend/src/types/lecture.ts` — `LectureDetail` type already has `narrated_pptx_url` field
- `frontend/src/app/(dashboard)/lectures/upload/page.tsx` — the upload success screen links to `/projects/{id}`, which is the project detail page that needs the download button

**Files that must NOT change:**
- Any backend files
- Any AI server files
- Any database model files

**Implementation details:**

In the project detail page, after line 74 (inside the lecture render loop):
```tsx
// Status polling effect
useEffect(() => {
  const processing = lectures.filter(l => l.status === 'processing');
  if (processing.length === 0) return;
  
  const interval = setInterval(async () => {
    try {
      const p = await projectsApi.get(params.id as string);
      setLectures(p.lectures);
    } catch {}
  }, 5000);
  
  return () => clearInterval(interval);
}, [lectures, params.id]);
```

In the lecture list item, add download button when completed:
```tsx
{lecture.status === 'completed' && lecture.narrated_pptx_url && (
  <a
    href={lecture.narrated_pptx_url}
    download
    className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700"
  >
    Download PPTX
  </a>
)}
```

*Note*: The existing `LectureSummary` type doesn't include `narrated_pptx_url` — it needs to be added, or the frontend should call `GET /api/v1/lectures/{id}` for completed lectures to get the full `LectureDetail` response.

**Dependencies**: Task 4 (download URLs must return real files).

**Verification:**
1. Upload lecture with PPTX
2. See status badge change from "processing" to "completed"
3. Click download button → browser downloads narrated PPTX
4. Open PPTX → audio plays on each slide

**Expected result**: Complete end-to-end flow works from upload to download.

**Difficulty**: Low-Medium (1 day).

---

### Task 6 — Frontend error toasts

**Why**: All data-fetching pages use `console.error()` on failure. Users see infinite loading spinners with no feedback.

**What breaks without this**: Users don't know when uploads fail, projects fail to load, etc.

**Files to modify:**
- `frontend/src/app/layout.tsx` — add `<Toaster />` component from `sonner`
- `frontend/src/app/(dashboard)/dashboard/page.tsx` — replace `console.error` with `toast.error`
- `frontend/src/app/(dashboard)/projects/page.tsx` — same
- `frontend/src/app/(dashboard)/projects/[id]/page.tsx` — same
- `frontend/src/app/(dashboard)/voice-profiles/page.tsx` — same

**Files that must NOT change:**
- Any backend files
- Any AI server files
- Any database model files
- Any upload page (already has inline error display)

**Verification**: Disconnect backend → navigate to dashboard → see toast notification.

**Expected result**: API failures visible to user.

**Dependencies**: None (can be done in parallel with any other task).

**Difficulty**: Low (0.5 day).

---

## Dependency Graph

```
Task 1 (TTS fix)
  └── No dependencies
  └── Required by: Task 2, Task 3

Task 2 (PPTX embedding fix)
  └── Depends on: Task 1
  └── Required by: Task 4

Task 3 (No-PPTX handling)
  └── Depends on: Task 1
  └── Independent of Task 2, Task 4

Task 4 (FileModel + URL fixes)
  └── Depends on: Task 2 (needs working PPTX output)
  └── Required by: Task 5

Task 5 (Frontend download + polling)
  └── Depends on: Task 4 (needs working download URLs)

Task 6 (Error toasts)
  └── No dependencies (parallel with everything)
```

## Execution Order

```
Phase 1 (parallel):
  Task 1 — Fix TTS
  Task 6 — Error toasts

Phase 2 (parallel after Task 1):
  Task 2 — Fix PPTX embedding
  Task 3 — Handle no-PPTX uploads

Phase 3 (after Task 2):
  Task 4 — FileModel records + fix URLs

Phase 4 (after Task 4):
  Task 5 — Frontend download + polling
```

---

## Verification Checklist

Run this in order. Do not proceed to the next step until the current step passes.

```
☐ STEP 0: Prerequisites
  - PostgreSQL running on localhost:5432
  - Redis running on localhost:6379
  - GPU server running and reachable at AI_SERVICE_URL
  - alembic upgrade head (database migrated)
  - `.env` file exists at project root with correct values

  Verify: curl http://localhost:8000/api/v1/health → 200 OK

☐ STEP 1: After Task 1 (TTS fix)
  curl -X POST -F "text=Welcome to this lecture on physics." \
    http://<gpu-server>:8001/ai/v1/tts -o test.wav
  ffprobe test.wav
  → streams=1, duration > 0
  Play test.wav → hear speech

☐ STEP 2: After Task 2 (PPTX embedding)
  Create test PPTX with 2-3 slides containing text
  python -c "
  from backend.src.worker.pipeline.embed_narration import embed_narration_into_pptx
  result = embed_narration_into_pptx('test.pptx', {1: 'test.wav', 2: 'test.wav'}, 'out.pptx')
  print(f'Slides: {result.slide_count}, Audio tracks: {result.audio_tracks_added}')
  "
  Open out.pptx in PowerPoint → audio icon on each slide → plays speech

☐ STEP 3: After Task 3 (no-PPTX handling)
  Upload audio-only lecture (no PPTX)
  → Pipeline completes
  → GET /api/v1/lectures/{id} returns meaningful status
  → Not marked "completed" with zero content

☐ STEP 4: After Task 4 (FileModel + URLs)
  Upload lecture with PPTX
  Wait for pipeline to complete
  GET /api/v1/lectures/{id}
  → Response contains narrated_pptx_url
  → URL format: /api/v1/files/{uuid}
  curl -H "Authorization: Bearer $TOKEN" {narrated_pptx_url} -o output.pptx
  → File downloads, is valid PPTX, contains audio

☐ STEP 5: After Task 5 (frontend)
  Login
  Create project
  Upload lecture with PPTX
  → See status change from "pending" → "processing" → "completed"
  → Download button appears
  → Click download → browser saves narrated PPTX
  → Open in PowerPoint → audio plays on each slide

☐ STEP 6: After Task 6 (error toasts)
  Stop the backend
  Refresh frontend dashboard
  → Toast notification appears: "Failed to load projects"
  Start the backend
  → Dashboard loads normally
```

---

## Final Output

When all 6 tasks are complete, this flow works end-to-end:

```
Register → Login → Create Project → Upload (video + PPTX)
  → Pipeline starts automatically
  → Audio extracted (Stage 1)
  → Transcribed (Stage 2)
  → PPTX parsed (Stage 3)
  → Alignment (Stage 5)
  → Narration scripts (Stage 6)
  → Real TTS audio generated (Stage 7) ← Task 1
  → Audio embedded into PPTX (Stage 8) ← Task 2
  → FileModels created, download URLs fixed ← Task 4
  → Status updates in frontend, download button appears ← Task 5
  → User clicks download → narrated PPTX saved → audio plays ← Task 4+5
```

Audio-only uploads produce a meaningful result instead of silent completion ← Task 3.

API failures are visible via toast notifications instead of silent console.error ← Task 6.
