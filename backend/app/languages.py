from typing import Final, Literal

SourceLangCode = Literal["auto", "id", "en", "zh"]
TargetLangCode = Literal["en", "id"]

SOURCE_LANGUAGES: Final[list[dict[str, str]]] = [
    {"code": "auto", "label": "Otomatis"},
    {"code": "id", "label": "Indonesia"},
    {"code": "en", "label": "English"},
    {"code": "zh", "label": "中文"},
]

TARGET_LANGUAGES: Final[list[dict[str, str]]] = [
    {"code": "en", "label": "English"},
    {"code": "id", "label": "Indonesia"},
]

SUPPORTED_SOURCE_CODES: Final[set[str]] = {lang["code"] for lang in SOURCE_LANGUAGES}
SUPPORTED_TARGET_CODES: Final[set[str]] = {lang["code"] for lang in TARGET_LANGUAGES}
STT_LANGUAGES: Final[set[str]] = {"id", "en", "zh"}

LANGUAGE_NAMES: Final[dict[str, str]] = {
    "auto": "Otomatis",
    "id": "Indonesia",
    "en": "Inggris",
    "zh": "Mandarin",
}

WHISPER_MODELS: Final[list[str]] = ["tiny", "base", "small", "medium", "large-v3"]
DEFAULT_WHISPER_MODEL: Final[str] = "small"
