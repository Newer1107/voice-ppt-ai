"""Unit tests for domain entities and value objects."""

import pytest

from backend.src.core.domain.value_objects import EmailAddress, Transcript, TimestampRange


class TestEmailAddress:
    """Test EmailAddress value object."""

    def test_valid_email(self):
        email = EmailAddress("test@example.com")
        assert str(email) == "test@example.com"

    def test_invalid_email(self):
        with pytest.raises(ValueError):
            EmailAddress("not-an-email")

    def test_email_too_long(self):
        long = "a" * 256 + "@example.com"
        with pytest.raises(ValueError):
            EmailAddress(long)


class TestTimestampRange:
    """Test TimestampRange value object."""

    def test_valid_range(self):
        tr = TimestampRange(start=0.0, end=10.0)
        assert tr.duration == 10.0

    def test_negative_start(self):
        with pytest.raises(ValueError):
            TimestampRange(start=-1.0, end=10.0)

    def test_end_before_start(self):
        with pytest.raises(ValueError):
            TimestampRange(start=5.0, end=3.0)


class TestTranscript:
    """Test Transcript value object."""

    def test_valid_transcript(self):
        t = Transcript(
            segment_number=1,
            start_time=0.0,
            end_time=5.2,
            text="Hello world",
            confidence=0.98,
        )
        assert t.segment_number == 1
        assert t.text == "Hello world"

    def test_negative_segment_number(self):
        with pytest.raises(ValueError):
            Transcript(segment_number=0, start_time=0.0, end_time=1.0, text="x", confidence=0.5)
