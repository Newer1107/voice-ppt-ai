"""Unified GPU service configuration."""

from pydantic_settings import BaseSettings


class ServiceConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8001

    # Whisper
    whisper_model_size: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"

    # BGE
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cuda"
    embedding_batch_size: int = 32

    # TTS
    tts_model_path: str = "SWivid/F5-TTS"
    tts_device: str = "cuda"
    tts_sample_rate: int = 24000

    # SGLang (LLM serving, separate process)
    llm_api_url: str = "http://localhost:30000/v1"
    llm_model: str = "Qwen/Qwen3-8B"

    model_config = {"env_prefix": "AI_"}
