import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.audio import extract_audio, probe_media
from app.config import settings
from app.models import Job, JobStatus
from app.segment import segment_words
from app.storage import (
    get_job_file,
    save_meta,
    save_segments,
)
from app.subtitle import segments_to_srt, segments_to_vtt
from app.transcribe import FasterWhisperTranscriber, Transcriber
from app.translate import ClaudeTranslator, get_default_translator

logger = logging.getLogger(__name__)


class PipelineCancelled(Exception):
    """Raised when pipeline execution was cancelled by user."""

    pass


class SubtitlePipeline:
    def __init__(
        self,
        transcriber: Transcriber | None = None,
        translator: Any | None = None,
    ):
        self.transcriber = transcriber or FasterWhisperTranscriber()
        self.translator = translator or get_default_translator()

    async def run(
        self,
        job: Job,
        input_path: Path,
        on_event: Callable[[Job], None] | None = None,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> Job:
        """
        Executes the end-to-end subtitle pipeline:
        1. Extract Audio
        2. Transcribe (speech-to-text with Faster-Whisper)
        3. Segment (words -> cues)
        4. Save source SRT and VTT
        5. Translate (if target_langs requested and translator available)
        """
        job_id = job.id
        wav_path = get_job_file(job_id, "audio.wav")

        def emit():
            save_meta(job)
            if on_event:
                on_event(job)

        def verify_cancelled():
            if check_cancelled and check_cancelled():
                job.status = JobStatus.CANCELLED
                emit()
                raise PipelineCancelled("Pekerjaan dibatalkan pengguna")

        try:
            verify_cancelled()

            # ---------------------------------------------------------
            # Stage 1: Extract Audio (5% weight)
            # ---------------------------------------------------------
            job.status = JobStatus.EXTRACTING_AUDIO
            job.stage_progress = 0.1
            job.progress = 0.01
            emit()

            # Probe media duration
            probe_info = await asyncio.to_thread(probe_media, input_path)
            job.duration_sec = probe_info.get("duration", 0.0)
            job.stage_progress = 0.5
            job.progress = 0.03
            emit()

            verify_cancelled()

            # Extract audio
            await asyncio.to_thread(extract_audio, input_path, wav_path)
            job.stage_progress = 1.0
            job.progress = 0.05
            emit()

            verify_cancelled()

            # ---------------------------------------------------------
            # Stage 2: Transcribe (60% weight if translation, else 93%)
            # ---------------------------------------------------------
            has_translation = len(job.target_langs) > 0
            transcribe_weight = 0.60 if has_translation else 0.93

            job.status = JobStatus.TRANSCRIBING
            job.stage_progress = 0.0
            job.progress = 0.05
            emit()

            def on_transcribe_progress(prog: float):
                verify_cancelled()
                job.stage_progress = prog
                job.progress = 0.05 + (prog * transcribe_weight)
                emit()

            words, detected_lang, _prob = await asyncio.to_thread(
                self.transcriber.transcribe,
                audio_path=wav_path,
                source_lang=job.source_lang_requested,
                model_size=job.model_size,
                duration=job.duration_sec,
                on_progress=on_transcribe_progress,
            )

            job.source_lang_detected = detected_lang
            verify_cancelled()

            # ---------------------------------------------------------
            # Stage 3: Segment (2% weight)
            # ---------------------------------------------------------
            job.status = JobStatus.SEGMENTING
            job.stage_progress = 0.5
            job.progress = 0.05 + transcribe_weight + 0.01
            emit()

            segments = await asyncio.to_thread(segment_words, words, lang=detected_lang)

            # Save source segments, SRT, and VTT
            await asyncio.to_thread(save_segments, job_id, detected_lang, segments)
            src_srt = await asyncio.to_thread(segments_to_srt, segments)
            src_vtt = await asyncio.to_thread(segments_to_vtt, segments)

            srt_file = get_job_file(job_id, f"subtitle.{detected_lang}.srt")
            vtt_file = get_job_file(job_id, f"subtitle.{detected_lang}.vtt")
            srt_file.write_text(src_srt, encoding="utf-8")
            vtt_file.write_text(src_vtt, encoding="utf-8")

            if detected_lang not in job.available_langs:
                job.available_langs.append(detected_lang)

            job.stage_progress = 1.0
            job.progress = 0.05 + transcribe_weight + 0.02
            emit()

            verify_cancelled()

            # ---------------------------------------------------------
            # Stage 4: Translate (Fase 4: 33% weight)
            # ---------------------------------------------------------
            valid_targets = [t for t in job.target_langs if t != detected_lang]
            if valid_targets and self.translator:
                if isinstance(self.translator, ClaudeTranslator) and not settings.anthropic_api_key:
                    warn_msg = (
                        "Terjemahan dilewati: ANTHROPIC_API_KEY belum dikonfigurasi di file .env"
                    )
                    logger.warning(warn_msg)
                    job.warnings.append(warn_msg)
                    emit()
                else:
                    job.status = JobStatus.TRANSLATING
                    translate_weight = 0.33 / len(valid_targets)
                    base_progress = 0.05 + transcribe_weight + 0.02

                    for idx, target_lang in enumerate(valid_targets):
                        verify_cancelled()
                        job.stage_progress = 0.0
                        emit()

                        def on_translate_prog(p: float, current_idx: int = idx):
                            verify_cancelled()
                            job.stage_progress = p
                            job.progress = (
                                base_progress
                                + (current_idx * translate_weight)
                                + (p * translate_weight)
                            )
                            emit()

                        try:
                            translated_segs = await self.translator.translate(
                                segments=segments,
                                source=detected_lang,
                                target=target_lang,
                                glossary=None,
                                on_progress=on_translate_prog,
                            )

                            await asyncio.to_thread(
                                save_segments, job_id, target_lang, translated_segs
                            )
                            tgt_srt = await asyncio.to_thread(segments_to_srt, translated_segs)
                            tgt_vtt = await asyncio.to_thread(segments_to_vtt, translated_segs)

                            t_srt_file = get_job_file(job_id, f"subtitle.{target_lang}.srt")
                            t_vtt_file = get_job_file(job_id, f"subtitle.{target_lang}.vtt")
                            t_srt_file.write_text(tgt_srt, encoding="utf-8")
                            t_vtt_file.write_text(tgt_vtt, encoding="utf-8")

                            if target_lang not in job.available_langs:
                                job.available_langs.append(target_lang)

                        except Exception as err:
                            logger.error("Terjemahan ke %s gagal: %s", target_lang, err)
                            job.warnings.append(f"Gagal menerjemahkan ke {target_lang}: {err}")

            # ---------------------------------------------------------
            # Completed
            # ---------------------------------------------------------
            job.status = JobStatus.DONE
            job.stage_progress = 1.0
            job.progress = 1.0
            emit()
            return job

        except PipelineCancelled:
            job.status = JobStatus.CANCELLED
            emit()
            return job
        except Exception as err:
            logger.exception("Pipeline failed for job %s: %s", job_id, err)
            job.status = JobStatus.FAILED
            job.error = str(err)
            emit()
            return job
