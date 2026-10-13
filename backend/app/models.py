from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.languages import SourceLangCode, TargetLangCode


class Segment(BaseModel):
    index: int = Field(ge=1, description="1-based sequence index")
    start: float = Field(ge=0.0, description="Start timestamp in seconds")
    end: float = Field(ge=0.0, description="End timestamp in seconds")
    text: str = Field(description="Subtitle text, at most 2 lines")


class JobStatus(StrEnum):
    QUEUED = "queued"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    SEGMENTING = "segmenting"
    TRANSLATING = "translating"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    filename: str
    status: JobStatus = JobStatus.QUEUED
    stage_progress: float = 0.0
    progress: float = 0.0
    source_lang_requested: SourceLangCode = "auto"
    source_lang_detected: str | None = None
    target_langs: list[TargetLangCode] = []
    model_size: str = "small"
    duration_sec: float | None = None
    available_langs: list[str] = []
    burned_langs: list[str] = []
    softsub_langs: list[str] = []
    burn_progress: dict[str, float] = {}
    warnings: list[str] = []
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HealthResponse(BaseModel):
    status: str = "ok"
    ffmpeg: bool
    whisper_model: str
    translator: str
    translator_ready: bool


class LanguageOption(BaseModel):
    code: str
    label: str


class ConfigResponse(BaseModel):
    source_languages: list[LanguageOption]
    target_languages: list[LanguageOption]
    whisper_models: list[str]
    default_model: str
    max_upload_mb: int


class SubtitleResponse(BaseModel):
    lang: str
    segments: list[Segment]


class SubtitleUpdateRequest(BaseModel):
    segments: list[Segment]


class TranslateRequest(BaseModel):
    target_langs: list[TargetLangCode]


class BurnRequest(BaseModel):
    lang: str
    mode: str = "hard"  # "hard" | "soft"


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
