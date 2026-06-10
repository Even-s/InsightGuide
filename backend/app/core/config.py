"""Application configuration management."""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Application
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Database
    DATABASE_URL: str = "postgresql://insightguide:insightguide_password@localhost:5432/insightguide"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # OpenAI
    OPENAI_API_KEY: str = ""
    DOCUMENT_ANALYSIS_MODEL: str = "gpt-5.5"  # For requirements document analysis
    REALTIME_TRANSCRIPTION_MODEL: str = "gpt-realtime-whisper"  # Realtime Whisper model for transcription
    SEMANTIC_UNDERSTANDING_MODEL: str = "gpt-5.4-mini"  # GPT-5.4-mini - 10x faster and cheaper for answer evaluation
    EMBEDDING_MODEL: str = "text-embedding-3-large"

    # S3 Storage
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_PUBLIC_ENDPOINT_URL: str = ""  # Public URL for presigned URLs (e.g., https://your-domain.com:9000)
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "insightguide-uploads"
    S3_REGION: str = "us-east-1"

    @property
    def s3_presigned_endpoint_url(self) -> str:
        """Get the endpoint URL to use for presigned URLs (public or internal)."""
        return self.S3_PUBLIC_ENDPOINT_URL or self.S3_ENDPOINT_URL

    # File Processing
    MAX_UPLOAD_SIZE: int = 50000000  # 50MB
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "doc", "md", "txt"]

    # Session
    SESSION_TIMEOUT_SECONDS: int = 7200
    REALTIME_SESSION_TIMEOUT_SECONDS: int = 3600

    @property
    def database_url_async(self) -> str:
        """Get async database URL."""
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")


settings = Settings()
