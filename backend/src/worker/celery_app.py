"""Celery application configuration."""

from celery import Celery

from backend.src.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "lecture_narrator",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_RESULT_URL),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600 * 24 * 7,  # 7 days
)

# Queue configuration
celery_app.conf.task_queues = {
    "default": {"exchange": "default", "routing_key": "default"},
    "audio": {"exchange": "audio", "routing_key": "audio"},
    "transcription": {"exchange": "transcription", "routing_key": "transcription"},
    "llm": {"exchange": "llm", "routing_key": "llm"},
    "tts": {"exchange": "tts", "routing_key": "tts"},
    "pptx": {"exchange": "pptx", "routing_key": "pptx"},
    "priority_high": {"exchange": "priority_high", "routing_key": "priority_high"},
}

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_routing_key = "default"
