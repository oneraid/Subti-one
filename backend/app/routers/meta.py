import shutil

from fastapi import APIRouter

from app.config import settings
from app.languages import (
    DEFAULT_WHISPER_MODEL,
    SOURCE_LANGUAGES,
    TARGET_LANGUAGES,
    WHISPER_MODELS,
)
from app.models import ConfigResponse, HealthResponse, LanguageOption

router = APIRouter(prefix="/api", tags=["meta"])


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    if settings.translator_backend == "google":
        translator_ready = True
    else:
        translator_ready = bool(settings.anthropic_api_key and settings.anthropic_api_key.strip())

    return HealthResponse(
        status="ok",
        ffmpeg=check_ffmpeg(),
        whisper_model=settings.whisper_model,
        translator=settings.translator_backend,
        translator_ready=translator_ready,
    )


@router.get("/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    return ConfigResponse(
        source_languages=[LanguageOption(**item) for item in SOURCE_LANGUAGES],
        target_languages=[LanguageOption(**item) for item in TARGET_LANGUAGES],
        whisper_models=WHISPER_MODELS,
        default_model=DEFAULT_WHISPER_MODEL,
        max_upload_mb=settings.max_upload_mb,
    )
