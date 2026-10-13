from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Translation
    translator_backend: str = "google"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"

    # Speech to text
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
    whisper_model_dir: Path = Path("./data/models")

    # Application
    data_dir: Path = Path("./data")
    max_upload_mb: int = 2048
    max_concurrent_jobs: int = 1
    cors_origins: str | list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    file_retention_hours: int = 72

    @field_validator("cors_origins", mode="after")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return list(v)

    @field_validator("data_dir", "whisper_model_dir", mode="after")
    @classmethod
    def resolve_paths(cls, v: Path) -> Path:
        return v.resolve()


settings = Settings()
