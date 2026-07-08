"""Stage 5: Align transcript segments to slides using embedding + LLM.

Process:
1. Generate embeddings for slide text and transcript chunks
2. Compute similarity matrix between segments and slides
3. Select candidate slides per segment via embedding similarity
4. Send candidates + context to LLM for final verification
5. Apply temporal constraints (segments only go forward)
6. Store final alignment

Verifies: Every segment assigned OR explicitly marked unassigned
"""

import logging
from typing import Optional

from pydantic import BaseModel

from backend.src.config.settings import get_settings
from backend.src.worker.pipeline.generate_embeddings import generate_embeddings

logger = logging.getLogger(__name__)


class SlideAlignment(BaseModel):
    slide_number: int
    segment_numbers: list[int]
    confidence: float
    start_time: float = 0.0
    end_time: float = 0.0


class AlignmentResult(BaseModel):
    alignments: list[SlideAlignment]
    unassigned_segments: list[int]
    model: str = ""


def align_transcript(
    transcript_segments: list[dict],
    slides: list[dict],
) -> AlignmentResult:
    """Align transcript segments to slides.

    Two-phase approach:
    1. Embedding similarity search (BGE-M3) for candidate selection
    2. LLM verification for final alignment
    """
    if not transcript_segments:
        raise ValueError("No transcript segments to align")
    if not slides:
        raise ValueError("No slides to align against")

    # Phase 1: Generate embeddings for slide text
    slide_texts = []
    for s in slides:
        text = s.get("raw_text", "")
        notes = s.get("notes", "")
        combined = f"{text}\n{notes}" if notes else text
        slide_texts.append(combined)

    slide_emb_result = generate_embeddings(slide_texts)

    # Phase 2: Generate embeddings for transcript segments (batched)
    seg_texts = [seg.get("text", "") for seg in transcript_segments]
    seg_emb_result = generate_embeddings(seg_texts)

    # Phase 3: Compute similarity matrix (cosine similarity on normalized vectors)
    import math
    candidates = []
    for si, s_vec in enumerate(seg_emb_result.vectors):
        best_slide = 0
        best_sim = -1.0
        for ti, t_vec in enumerate(slide_emb_result.vectors):
            dot = sum(a * b for a, b in zip(s_vec, t_vec))
            sim = max(-1.0, min(1.0, dot))
            if sim > best_sim:
                best_sim = sim
                best_slide = ti

        seg = transcript_segments[si]
        seg_number = seg.get("segment_number", si + 1)
        candidates.append({
            "segment_number": seg_number,
            "slide_number": best_slide + 1,
            "similarity": round(best_sim, 4),
            "text": seg.get("text", ""),
        })

    # Phase 4: Call LLM for verification with candidates
    settings = get_settings()
    import httpx
    llm_url = f"{settings.AI_SERVICE_URL}/ai/v1/align"

    transcript_dict = {"segments": transcript_segments}
    slides_list = [{
        "slide_number": s.get("slide_number", i + 1),
        "raw_text": s.get("raw_text", ""),
        "notes": s.get("notes"),
    } for i, s in enumerate(slides)]

    try:
        resp = httpx.post(
            llm_url,
            json={
                "transcript": transcript_dict,
                "slides": slides_list,
                "candidates": candidates,
            },
            timeout=600,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("LLM alignment failed (%s), falling back to embedding-only alignment", e)
        # Fallback: use embedding candidates directly
        data = _embedding_only_fallback(candidates, transcript_segments)

    # Apply temporal constraints
    alignments = _enforce_temporal_constraints(data.get("alignments", []))
    unassigned = data.get("unassigned_segments", [])

    # Verify: every segment should be either assigned or explicitly unassigned
    assigned_numbers = set()
    for a in alignments:
        assigned_numbers.update(a.get("segment_numbers", []))
    all_numbers = {s.get("segment_number", i + 1) for i, s in enumerate(transcript_segments)}
    missing = all_numbers - assigned_numbers - set(unassigned)
    if missing:
        logger.warning("Segments not assigned or marked unassigned: %s", missing)
        unassigned.extend(list(missing))

    result = AlignmentResult(
        alignments=[
            SlideAlignment(
                slide_number=a.get("slide_number", 1),
                segment_numbers=a.get("segment_numbers", []),
                confidence=a.get("confidence", 0.5),
                start_time=a.get("start_time", 0),
                end_time=a.get("end_time", 0),
            )
            for a in alignments
        ],
        unassigned_segments=unassigned,
        model=data.get("model", "bge-m3+qwen"),
    )

    logger.info(
        "Alignment complete: %d slides, %d segments aligned, %d unassigned",
        len(slides), len(assigned_numbers), len(unassigned),
    )

    return result


def _embedding_only_fallback(
    candidates: list[dict],
    transcript_segments: list[dict],
) -> dict:
    """Fallback alignment using only embedding similarity (no LLM)."""
    alignments = {}
    for c in candidates:
        sn = c["slide_number"]
        if sn not in alignments:
            alignments[sn] = {"slide_number": sn, "segment_numbers": [], "confidence": 1.0, "start_time": 0, "end_time": 0}
        alignments[sn]["segment_numbers"].append(c["segment_number"])

    return {
        "alignments": list(alignments.values()),
        "unassigned_segments": [],
        "model": "bge-m3 (fallback)",
    }


def _enforce_temporal_constraints(alignments: list[dict]) -> list[dict]:
    """Ensure slide numbers are non-decreasing over time."""
    sorted_al = sorted(alignments, key=lambda x: min(x.get("segment_numbers", [0])))
    current_slide = 1
    for a in sorted_al:
        slide = a.get("slide_number", current_slide)
        if slide < current_slide:
            a["slide_number"] = current_slide
            a["confidence"] = min(a.get("confidence", 1.0), 0.5)
        else:
            current_slide = slide
    return sorted_al
