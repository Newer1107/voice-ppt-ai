"""Domain value objects — immutable, self-validating primitives."""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EmailAddress:
    """Validated email address value object."""

    value: str

    def __post_init__(self) -> None:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, self.value):
            raise ValueError(f"Invalid email address: {self.value}")
        if len(self.value) > 255:
            raise ValueError("Email too long (max 255 chars)")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class FilePath:
    """Validated filesystem path value object with traversal protection."""

    value: Path

    def __post_init__(self) -> None:
        # Guard against path traversal
        try:
            self.value.resolve().relative_to(self.value.anchor)
        except ValueError:
            raise ValueError(f"Invalid path: {self.value}")

    @property
    def extension(self) -> str:
        return self.value.suffix.lower()

    @property
    def exists(self) -> bool:
        return self.value.exists()

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class TimestampRange:
    """A time range with start and end in seconds."""

    start: float
    end: float

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError(f"Start time cannot be negative: {self.start}")
        if self.end <= self.start:
            raise ValueError(
                f"End time ({self.end}) must be greater than start ({self.start})"
            )

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class Transcript:
    """A single transcript segment with timing and text."""

    segment_number: int
    start_time: float
    end_time: float
    text: str
    confidence: float
    speaker: str | None = None

    def __post_init__(self) -> None:
        if self.segment_number < 1:
            raise ValueError(
                f"Segment number must be >= 1: {self.segment_number}"
            )
        if self.start_time < 0:
            raise ValueError(
                f"Start time cannot be negative: {self.start_time}"
            )
        if self.end_time <= self.start_time:
            raise ValueError(
                f"End time ({self.end_time}) must be > start ({self.start_time})"
            )
