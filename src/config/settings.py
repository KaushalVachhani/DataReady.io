"""
Application settings and configuration management.

Uses pydantic-settings for environment variable loading.
"""

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "DataReady.io"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Databricks AI Gateway (for Gemini models)
    databricks_host: str = ""
    databricks_token: str = ""
    
    # Model endpoints
    gemini_pro_endpoint: str = "/serving-endpoints/databricks-gemini-3-pro/invocations"
    gemini_flash_endpoint: str = "/serving-endpoints/databricks-gemini-flash/invocations"
    
    # Whisper configuration (for STT)
    whisper_model: str = "whisper-large-v3"
    whisper_api_url: str = ""  # If using API, otherwise local
    use_local_whisper: bool = True
    
    # TTS configuration
    tts_model: str = "kokoro"  # Options: kokoro, piper, edge-tts
    tts_voice: str = "af_heart"  # Kokoro voice
    tts_rate: int = 16000
    
    # Interview settings
    max_questions: int = 10
    max_follow_ups_per_question: int = 2
    response_timeout_seconds: int = 180  # 3 minutes max per response
    min_response_seconds: int = 5
    
    # Audio settings
    audio_sample_rate: int = 16000
    audio_chunk_duration_ms: int = 100
    
    # CORS - stored as comma-separated string in env
    # Uses validation_alias to read from CORS_ORIGINS env var
    cors_origins_str: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        validation_alias="cors_origins"
    )
    
    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
