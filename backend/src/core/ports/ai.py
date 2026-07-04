"""AI service port interfaces.

All AI capabilities are abstracted behind interfaces so the application
never depends on a specific model or provider.
"""

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


# ─── Data Transfer Objects ─────────────────────────────────────────────


class TranscriptSegment(BaseModel):
    """A single transcript segment from transcription."""

    segment_number: int
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None
    speaker: Optional[str] = None


class TranscriptionResult(BaseModel):
    """Result from a transcription request."""

    segments: list[TranscriptSegment]
    language: str
    duration_seconds: float
    processing_time_seconds: float = 0.0


class SlideData(BaseModel):
    """Slide data for alignment and narration."""

    slide_number: int
    raw_text: str
    notes: Optional[str] = None


class SlideAlignment(BaseModel):
    """A single slide alignment result."""

    slide_number: int
    segment_numbers: list[int]
    confidence: float
    start_time: float = 0.0
    end_time: float = 0.0


class AlignmentResult(BaseModel):
    """Result from transcript-to-slide alignment."""

    alignments: list[SlideAlignment]
    unassigned_segments: list[int]
    model: str = ""


class SlideNarrationInput(BaseModel):
    """Input for narration generation per slide."""

    slide_number: int
    raw_text: str
    notes: Optional[str] = None
    transcript_segments: list[dict] = []


class NarrationResult(BaseModel):
    """Result from narration generation per slide."""

    slide_number: int
    script_text: str
    estimated_duration_seconds: int
    tone: str = "educational"
    key_points: list[str] = []


class EmbeddingResult(BaseModel):
    """Result from a single embedding request."""

    vector: list[float]
    dimensions: int
    model: str = ""


class EmbeddingSearchResult(BaseModel):
    """Result from a similarity search."""

    source_index: int
    target_index: int
    similarity: float


# ─── Port Interfaces ───────────────────────────────────────────────────


class TranscriptionPort(ABC):
    """Interface for speech-to-text providers."""

    @abstractmethod
    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        vad_filter: bool = True,
    ) -> TranscriptionResult:
        """Transcribe audio file to text with timestamps."""
        ...

    @abstractmethod
    async def health(self) -> dict:
        """Check transcription service health."""
        ...


class EmbeddingPort(ABC):
    """Interface for embedding providers."""

    @abstractmethod
    async def embed_text(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate embeddings for a list of text strings."""
        ...

    @abstractmethod
    async def embed_dimensions(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        ...

    @abstractmethod
    async def health(self) -> dict:
        """Check embedding service health."""
        ...


class LLMPort(ABC):
    """Interface for LLM providers (narration, alignment)."""

    @abstractmethod
    async def align_transcript(
        self,
        transcript: dict,
        slides: list[SlideData],
    ) -> AlignmentResult:
        """Align transcript segments to slides."""
        ...

    @abstractmethod
    async def generate_narration(
        self,
        lecture_title: str,
        slides: list[SlideNarrationInput],
    ) -> list[NarrationResult]:
        """Generate narration scripts for each slide."""
        ...

    @abstractmethod
    async def health(self) -> dict:
        """Check LLM service health."""
        ...


class TTSPort(ABC):
    """Interface for text-to-speech providers."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_profile_id: Optional[str] = None,
        speed: float = 1.0,
    ) -> bytes:
        """Synthesize text to speech audio."""
        ...

    @abstractmethod
    async def clone_voice(
        self,
        audio_sample: bytes,
        name: str,
    ) -> str:
        """Clone a voice from an audio sample."""
        ...

    @abstractmethod
    async def health(self) -> dict:
        """Check TTS service health."""
        ...
