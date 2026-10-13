import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from app.config import settings
from app.languages import STT_LANGUAGES

logger = logging.getLogger(__name__)

# Cache loaded models: model_size -> WhisperModel instance
_model_cache: dict[str, Any] = {}


class Transcriber(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        source_lang: str = "auto",
        model_size: str = "small",
        duration: float | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> tuple[list[tuple[float, float, str]], str, float]:
        """
        Transcribe audio file.
        Returns:
            (words, detected_language, language_probability)
        where words is a list of (start_sec, end_sec, word_text).
        """
        ...


def get_whisper_model(model_size: str = "small") -> Any:
    """Lazy load and cache faster-whisper WhisperModel."""
    from faster_whisper import WhisperModel

    if model_size not in _model_cache:
        device = settings.whisper_device
        compute_type = settings.whisper_compute_type
        model_dir = str(settings.whisper_model_dir.resolve())

        logger.info(
            "Loading Whisper model '%s' (device=%s, compute=%s, download_root=%s)...",
            model_size,
            device,
            compute_type,
            model_dir,
        )

        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=model_dir,
        )
        _model_cache[model_size] = model

    return _model_cache[model_size]


class FasterWhisperTranscriber:
    def transcribe(
        self,
        audio_path: Path,
        source_lang: str = "auto",
        model_size: str = "small",
        duration: float | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> tuple[list[tuple[float, float, str]], str, float]:
        """
        Transcribe audio using faster-whisper.
        Handles word timestamps, VAD filtering, hallucination reduction flags,
        and unsupported language detection.
        """
        model = get_whisper_model(model_size)
        lang_code = None if source_lang == "auto" else source_lang

        segments_iter, info = model.transcribe(
            str(audio_path.resolve()),
            language=lang_code,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,
            beam_size=5,
        )

        detected_lang = info.language
        lang_prob = info.language_probability

        # Check if detected language is supported
        if detected_lang not in STT_LANGUAGES:
            # Check if probability is weak or completely unsupported
            if lang_prob > 0.8:
                raise ValueError(
                    f"Bahasa yang terdeteksi ({detected_lang}) tidak didukung. "
                    f"AutoSub hanya mendukung bahasa: Indonesia (id), Inggris (en), Mandarin (zh)."
                )
            logger.warning(
                "Detected language '%s' (prob %.2f) unsupported, defaulting to English (en)",
                detected_lang,
                lang_prob,
            )
            detected_lang = "en"

        total_duration = duration or (info.duration if hasattr(info, "duration") else 1.0)
        words: list[tuple[float, float, str]] = []

        for segment in segments_iter:
            if hasattr(segment, "words") and segment.words:
                for w in segment.words:
                    words.append((w.start, w.end, w.word))
            else:
                # Fallback if no word tokens in segment
                words.append((segment.start, segment.end, segment.text))

            if on_progress and total_duration > 0:
                prog = min(1.0, max(0.0, segment.end / total_duration))
                on_progress(prog)

        if on_progress:
            on_progress(1.0)

        return words, detected_lang, lang_prob


class FakeTranscriber:
    """Mock Transcriber for testing pipeline and jobs without downloading models."""

    def __init__(
        self,
        words: list[tuple[float, float, str]] | None = None,
        detected_lang: str = "id",
        lang_prob: float = 0.98,
    ):
        self.words = words or [
            (0.0, 1.2, "Halo"),
            (1.3, 2.5, "semuanya"),
            (2.8, 4.0, "selamat"),
            (4.1, 5.0, "datang."),
        ]
        self.detected_lang = detected_lang
        self.lang_prob = lang_prob

    def transcribe(
        self,
        audio_path: Path,
        source_lang: str = "auto",
        model_size: str = "small",
        duration: float | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> tuple[list[tuple[float, float, str]], str, float]:
        if on_progress:
            on_progress(0.2)
            on_progress(0.6)
            on_progress(1.0)
        chosen_lang = self.detected_lang if source_lang == "auto" else source_lang
        return self.words, chosen_lang, self.lang_prob
