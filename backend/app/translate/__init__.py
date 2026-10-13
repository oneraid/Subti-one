"""Translation module for AutoSub."""

from app.config import settings
from app.translate.base import Translator
from app.translate.claude import ClaudeTranslator, FakeTranslator
from app.translate.google import GoogleTranslator


def get_default_translator() -> Translator:
    if settings.translator_backend == "google":
        return GoogleTranslator()
    return ClaudeTranslator()


__all__ = [
    "Translator",
    "GoogleTranslator",
    "ClaudeTranslator",
    "FakeTranslator",
    "get_default_translator",
]
