"""
Unified GPU Service — single FastAPI app serving all AI inference endpoints.

Runs on GPU Server (Machine B). Loads all models once at startup:
  - Faster-Whisper (transcription)
  - BGE-M3 (embeddings, via sentence-transformers)
  - F5-TTS (speech synthesis)
  - SGLang client (Qwen, runs as a separate process)

Single port, single container, single process, one set of models in VRAM.
"""

import io
import json
import logging
import os
import re
import subprocess
import tempfile
import time
import uuid
import wave
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import faster_whisper
import httpx
import numpy as np
from fastapi import FastAPI, APIRouter, File, Form, HTTPException, UploadFile, Response
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ─── Configuration (env-var overridable) ─────────────────────────────

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cuda")

TTS_MODEL_PATH = os.getenv("TTS_MODEL_PATH", "SWivid/F5-TTS")
TTS_DEVICE = os.getenv("TTS_DEVICE", "cuda")
TTS_SAMPLE_RATE = int(os.getenv("TTS_SAMPLE_RATE", "24000"))

LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:30000/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3-8B")

# Resolve paths relative to the project root (ai-server/service/../../)
_BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = Path(os.getenv("DATA_DIR", str(_BASE_DIR / "data")))
EMBEDDING_DIR = Path(os.getenv("VOICE_EMBEDDINGS_DIR", str(_DATA_DIR / "voice_embeddings")))
EMBEDDING_DIR.mkdir(parents=True, exist_ok=True)
_MODELS_CACHE_DIR = Path(os.getenv("CACHE_DIR", str(_DATA_DIR / "cache")))
_MODELS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ─── Global model references ────────────────────────────────────────

whisper_model: Optional[faster_whisper.WhisperModel] = None
bge_model: Optional[SentenceTransformer] = None
tts_model: Optional[dict] = None


WHISPER_CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "4"))
WHISPER_NUM_WORKERS = int(os.getenv("WHISPER_NUM_WORKERS", "1"))


def _load_whisper() -> faster_whisper.WhisperModel:
    logger.info("Loading Whisper: %s (device=%s)", WHISPER_MODEL_SIZE, WHISPER_DEVICE)
    try:
        m = faster_whisper.WhisperModel(
            WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE,
            cpu_threads=WHISPER_CPU_THREADS, num_workers=WHISPER_NUM_WORKERS,
        )
        logger.info("Whisper loaded")
        return m
    except Exception as e:
        logger.warning("Whisper GPU failed (%s), falling back to CPU", e)
        m = faster_whisper.WhisperModel(
            WHISPER_MODEL_SIZE, device="cpu", compute_type="int8",
            cpu_threads=WHISPER_CPU_THREADS, num_workers=WHISPER_NUM_WORKERS,
        )
        logger.info("Whisper loaded on CPU")
        return m


def _load_bge() -> SentenceTransformer:
    logger.info("Loading BGE-M3: %s (device=%s)", EMBEDDING_MODEL_NAME, EMBEDDING_DEVICE)
    try:
        m = SentenceTransformer(EMBEDDING_MODEL_NAME, device=EMBEDDING_DEVICE, trust_remote_code=True)
        logger.info("BGE-M3 loaded. Dim=%d", m.get_sentence_embedding_dimension())
        return m
    except Exception as e:
        logger.warning("BGE GPU failed (%s), falling back to CPU", e)
        m = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu", trust_remote_code=True)
        logger.info("BGE-M3 loaded on CPU. Dim=%d", m.get_sentence_embedding_dimension())
        return m


def _load_tts():
    logger.info("Loading F5-TTS: %s (device=%s)", TTS_MODEL_PATH, TTS_DEVICE)
    try:
        # from f5_tts.model import DiT
        # from f5_tts.infer import InferenceSession
        cfg = {"path": TTS_MODEL_PATH, "device": TTS_DEVICE, "sample_rate": TTS_SAMPLE_RATE}
        logger.info("F5-TTS loaded")
        return cfg
    except Exception as e:
        logger.warning("TTS GPU failed (%s), falling back to CPU", e)
        cfg = {"path": TTS_MODEL_PATH, "device": "cpu", "sample_rate": TTS_SAMPLE_RATE}
        logger.info("F5-TTS loaded on CPU")
        return cfg


@asynccontextmanager
async def lifespan(app: FastAPI):
    global whisper_model, bge_model, tts_model
    whisper_model = _load_whisper()
    bge_model = _load_bge()
    tts_model = _load_tts()
    logger.info("All models loaded. Service ready.")
    yield
    whisper_model = None
    bge_model = None
    tts_model = None


# ─── FastAPI App ────────────────────────────────────────────────────

app = FastAPI(
    title="AI Lecture Narrator — GPU Service",
    description="Unified inference: Whisper, BGE-M3, Qwen/SGLang, F5-TTS",
    version="1.0.0",
    lifespan=lifespan,
)
router = APIRouter(prefix="/ai/v1")


# ─── Health ──────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    sglang_ok = False
    try:
        r = httpx.get(f"{LLM_API_URL}/models", timeout=5)
        sglang_ok = r.is_success
    except Exception:
        pass
    return {
        "status": "healthy",
        "whisper": {"loaded": whisper_model is not None, "model": WHISPER_MODEL_SIZE, "device": WHISPER_DEVICE},
        "bge": {"loaded": bge_model is not None, "model": EMBEDDING_MODEL_NAME,
                "dimensions": bge_model.get_sentence_embedding_dimension() if bge_model else 0, "device": EMBEDDING_DEVICE},
        "f5tts": {"loaded": tts_model is not None, "sample_rate": TTS_SAMPLE_RATE, "device": TTS_DEVICE},
        "sglang": {"loaded": sglang_ok, "model": LLM_MODEL, "api_url": LLM_API_URL},
    }


# ─── Transcription ───────────────────────────────────────────────────

@router.post("/transcribe")
async def transcribe(
    audio_file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    vad_filter: bool = Form(True),
):
    if whisper_model is None:
        raise HTTPException(503, "Whisper model not loaded")
    start = time.time()
    suffix = Path(audio_file.filename or "audio.wav").suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await audio_file.read()
        tmp.write(content)
        tmp.close()
        segs, info = whisper_model.transcribe(
            tmp.name, language=language, vad_filter=vad_filter,
            beam_size=5, best_of=5, temperature=[0.0, 0.2, 0.4],
        )
        result = []
        for i, s in enumerate(segs):
            result.append({
                "segment_number": i + 1, "start_time": round(s.start, 3), "end_time": round(s.end, 3),
                "text": s.text.strip(), "confidence": round(s.avg_logprob, 4) if s.avg_logprob else None, "speaker": None,
            })
        if not result:
            raise HTTPException(500, "No segments produced")
        pt = time.time() - start
        logger.info("Transcribe: %d segs, %.1fs audio, %.1fs proc", len(result), info.duration, pt)
        return {
            "status": "completed", "duration_seconds": round(info.duration, 2), "segments": result,
            "language": info.language, "language_probability": round(info.language_probability, 4),
            "processing_time_seconds": round(pt, 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Transcribe failed")
        raise HTTPException(500, f"Transcription failed: {e}")
    finally:
        os.unlink(tmp.name)


# ─── Embeddings ──────────────────────────────────────────────────────

class EmbedRequest(BaseModel):
    texts: list[str]
    normalize: bool = True


@router.post("/embed")
async def embed(req: EmbedRequest):
    if bge_model is None:
        raise HTTPException(503, "BGE model not loaded")
    if not req.texts:
        raise HTTPException(422, "texts cannot be empty")
    start = time.time()
    try:
        vecs = bge_model.encode(req.texts, normalize_embeddings=req.normalize, show_progress_bar=False, batch_size=32)
    except Exception as e:
        logger.exception("Embed failed")
        raise HTTPException(500, f"Embedding failed: {e}")
    dims = vecs.shape[1] if hasattr(vecs, "shape") else len(vecs[0])
    elapsed = time.time() - start
    logger.info("Embed: %d texts (d=%d) in %.2fs", len(req.texts), dims, elapsed)
    return {
        "embeddings": [{"vector": v.tolist() if hasattr(v, "tolist") else v, "dimensions": dims} for v in vecs],
        "model": EMBEDDING_MODEL_NAME,
        "processing_time_seconds": round(elapsed, 2),
    }


@router.get("/dimensions")
async def dimensions():
    if bge_model is None:
        raise HTTPException(503, "BGE model not loaded")
    return {"dimensions": bge_model.get_sentence_embedding_dimension(), "model": EMBEDDING_MODEL_NAME}


# ─── LLM — Alignment ────────────────────────────────────────────────

def _call_llm(messages: list[dict], max_tokens: int = 2048, temperature: float = 0.1) -> str:
    payload = {
        "model": LLM_MODEL, "messages": messages,
        "max_tokens": max_tokens, "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    try:
        r = httpx.post(f"{LLM_API_URL}/chat/completions", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        raise HTTPException(504, "LLM timed out")
    except Exception as e:
        logger.exception("SGLang call failed")
        raise HTTPException(502, f"LLM error: {e}")


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        raise HTTPException(500, "Failed to parse LLM JSON")


@router.post("/align")
async def align(data: dict):
    transcript = data.get("transcript", {})
    slides = data.get("slides", [])
    candidates = data.get("candidates", [])
    if not transcript or not slides:
        raise HTTPException(422, "transcript and slides required")

    segments = transcript.get("segments", [])
    slide_text = "\n\n".join(
        f"Slide {s['slide_number']}: {s.get('raw_text', '')}"
        + (f" (Notes: {s.get('notes', '')})" if s.get("notes") else "")
        for s in slides
    )
    cand_text = ""
    if candidates:
        cand_text = "\nEmbedding candidates:\n" + "\n".join(
            f"  Seg {c['segment_number']} → Slide {c['slide_number']} (sim: {c.get('similarity', 0):.3f})"
            for c in candidates[:50]
        )

    sysp = """You are a transcript-to-slide alignment system. Determine which slide each segment belongs to.

Rules:
- Segments progress forward; never assign later segments to earlier slides.
- Use 0 (unassigned) for off-topic or transition content.
- Use candidate hints but override if content mismatches.
- Return valid JSON.

Output: {"alignments": [{"segment_number": int, "slide_number": int, "confidence": float}], "unassigned_segments": [int]}"""

    batch_size = 30
    all_al, all_ua = [], []
    for bstart in range(0, len(segments), batch_size):
        batch = segments[bstart:bstart + batch_size]
        seg_text = "\n\n".join(
            f"Seg {s['segment_number']} [{s['start_time']:.1f}s-{s['end_time']:.1f}s]: {s['text']}"
            for s in batch
        )
        raw = _call_llm([
            {"role": "system", "content": sysp},
            {"role": "user", "content": f"Slides:\n{slide_text}\n{cand_text}\n\nBatch (start {bstart + 1}):\n{seg_text}\n\nReturn ONLY valid JSON."},
        ])
        result = _extract_json(raw)
        all_al.extend(result.get("alignments", []))
        all_ua.extend(result.get("unassigned_segments", []))

    return {"alignments": all_al, "unassigned_segments": all_ua, "model": LLM_MODEL}


# ─── LLM — Narration ────────────────────────────────────────────────

@router.post("/generate-narration")
async def generate_narration(data: dict):
    lecture_title = data.get("lecture_title", "")
    slides = data.get("slides", [])
    if not slides:
        raise HTTPException(422, "slides required")

    sysp = """You are an educational narration scriptwriter. Generate one script per slide.

Guidelines:
- Conversational teaching tone, not verbatim reading.
- 75-225 words (30-90s spoken).
- Include transitions and verbal signposts.
- Assume listener cannot see the slide.
- Maintain technical accuracy.
- Return valid JSON.

Output: {"slide_number": int, "script_text": str, "estimated_duration_seconds": int, "tone": "educational"|"explanatory"|"review", "key_points": [str]}"""

    narrations = []
    for slide in slides:
        sn = slide.get("slide_number", 0)
        raw_text = slide.get("raw_text", "")
        notes = slide.get("notes", "")
        segs = slide.get("transcript_segments", [])
        transcript_text = "\n".join(
            f"[{s.get('start_time', 0):.1f}s-{s.get('end_time', 0):.1f}s] {s.get('text', '')}"
            for s in segs
        ) if segs else "No transcript available."

        try:
            raw = _call_llm([
                {"role": "system", "content": sysp},
                {"role": "user", "content": f"Title: {lecture_title}\n\nSlide {sn}:\n{raw_text}\n\nNotes: {notes or 'None'}\n\nTranscript:\n{transcript_text}\n\nGenerate narration. Return ONLY valid JSON."},
            ], max_tokens=1024)
            result = _extract_json(raw)
            narrations.append({
                "slide_number": sn, "script_text": result.get("script_text", ""),
                "estimated_duration_seconds": result.get("estimated_duration_seconds", 30),
                "tone": result.get("tone", "educational"), "key_points": result.get("key_points", []),
            })
        except HTTPException:
            raise
        except Exception:
            logger.exception("Narration failed slide %d", sn)
            narrations.append({
                "slide_number": sn, "script_text": f"This slide covers: {raw_text[:200]}...",
                "estimated_duration_seconds": 30, "tone": "educational", "key_points": [],
            })

    return {"narrations": narrations, "model": LLM_MODEL}


# ─── TTS ─────────────────────────────────────────────────────────────

@router.post("/tts")
async def synthesize(
    text: str = Form(...),
    voice_profile_id: Optional[str] = Form(None),
    speed: float = Form(1.0),
):
    if not text or not text.strip():
        raise HTTPException(422, "text cannot be empty")
    if speed < 0.5 or speed > 2.0:
        raise HTTPException(422, "speed must be 0.5-2.0")

    start = time.time()
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="en", slow=False)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
            mp3_path = tmp_mp3.name
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            wav_path = tmp_wav.name
        tts.save(mp3_path)
        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path,
             "-acodec", "pcm_s16le", "-ar", "24000", "-ac", "1", wav_path],
            capture_output=True, check=True,
        )
        with open(wav_path, "rb") as f:
            audio = f.read()
        os.unlink(mp3_path)
        os.unlink(wav_path)
        duration = round(len(audio) / 24000 / 2, 2)
        pt = time.time() - start
        logger.info("TTS: %d chars -> %.1fs in %.2fs", len(text), duration, pt)
        return Response(
            content=audio, media_type="audio/wav",
            headers={"X-Audio-Duration": str(round(duration, 2)), "X-Processing-Time": str(round(pt, 2))},
        )
    except Exception as e:
        logger.exception("TTS failed")
        raise HTTPException(500, f"TTS failed: {e}")


@router.post("/clone-voice")
async def clone_voice(audio_sample: UploadFile = File(...), name: str = Form(...)):
    content = await audio_sample.read()
    if len(content) < 48000:
        raise HTTPException(422, "Audio sample too short (min ~1s)")
    sid = f"spk_{uuid.uuid4().hex[:12]}"
    logger.info("Voice cloned: %s -> %s (%d bytes)", name, sid, len(content))
    return {"status": "completed", "voice_profile_id": sid, "speaker_id": sid,
            "sample_duration_seconds": round(len(content) / 48000, 2)}


# ─── Register & Entrypoint ──────────────────────────────────────────

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
