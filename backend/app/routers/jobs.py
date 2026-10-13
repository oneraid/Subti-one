import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from uuid import UUID


def format_content_disposition(filename: str, disposition_type: str = "attachment") -> str:
    """
    Format Content-Disposition header conforming to RFC 6266 and RFC 5987.
    Ensures safe ASCII fallback while preserving full Unicode (Chinese, Japanese, etc.)
    in modern browsers without raising UnicodeEncodeError in Starlette/uvicorn.
    """
    ascii_name = re.sub(r"[^\x20-\x7E]", "_", filename).replace('"', "_").replace("\\", "_")
    encoded_name = quote(filename, encoding="utf-8")
    return f"{disposition_type}; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.audio import burn_subtitles, embed_soft_subtitles, probe_media
from app.config import settings
from app.jobs import job_manager
from app.languages import (
    SUPPORTED_SOURCE_CODES,
    SUPPORTED_TARGET_CODES,
    WHISPER_MODELS,
    TargetLangCode,
)
from app.models import (
    BurnRequest,
    Job,
    JobStatus,
    SubtitleResponse,
    SubtitleUpdateRequest,
    TranslateRequest,
)
from app.storage import (
    delete_job_dir,
    get_job_dir,
    get_job_file,
    list_jobs,
    load_meta,
    load_segments,
    save_meta,
    save_segments,
)
from app.subtitle import (
    combine_bilingual_subtitles,
    segments_to_srt,
    segments_to_vtt,
)
from app.translate import ClaudeTranslator, get_default_translator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def validate_job_id(job_id_str: str) -> UUID:
    try:
        return UUID(job_id_str)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"Job {job_id_str} tidak ditemukan"},
        ) from err


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Job)
async def create_job(
    file: UploadFile = File(...),
    source_lang: str = Form("auto"),
    target_langs: str = Form(""),
    model_size: str = Form("small"),
    glossary: str | None = Form(None),
) -> Job:
    # 1. Validate options
    if source_lang not in SUPPORTED_SOURCE_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_option",
                "message": f"Bahasa sumber tidak valid: {source_lang}",
            },
        )

    parsed_targets: list[TargetLangCode] = []
    if target_langs.strip():
        for t in target_langs.split(","):
            t_clean = t.strip()
            if t_clean:
                if t_clean not in SUPPORTED_TARGET_CODES:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "code": "invalid_option",
                            "message": f"Target bahasa tidak valid: {t_clean}",
                        },
                    )
                parsed_targets.append(t_clean)  # type: ignore

    if model_size not in WHISPER_MODELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_option",
                "message": f"Model Whisper tidak valid: {model_size}",
            },
        )

    # 2. Check extension
    filename = file.filename or "media_upload"
    ext = Path(filename).suffix.lower()
    allowed_exts = {
        ".mp4",
        ".mkv",
        ".mov",
        ".avi",
        ".webm",
        ".flv",
        ".mp3",
        ".wav",
        ".m4a",
        ".flac",
        ".aac",
        ".ogg",
    }
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"code": "unsupported_media", "message": f"Format file {ext} tidak didukung"},
        )

    # 3. Create Job
    job = Job(
        filename=filename,
        status=JobStatus.QUEUED,
        source_lang_requested=source_lang,  # type: ignore
        target_langs=parsed_targets,
        model_size=model_size,
    )

    job_dir = get_job_dir(job.id)
    input_save_path = job_dir / f"input{ext}"

    # 4. Stream upload to disk with size check
    max_bytes = settings.max_upload_mb * 1024 * 1024
    total_written = 0

    try:
        with open(input_save_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                total_written += len(chunk)
                if total_written > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail={
                            "code": "file_too_large",
                            "message": f"Ukuran file melebihi batas {settings.max_upload_mb} MB",
                        },
                    )
                f.write(chunk)
    except Exception:
        if input_save_path.exists():
            input_save_path.unlink()
        raise

    # 5. Verify media with ffprobe
    try:
        probe = probe_media(input_save_path)
        job.duration_sec = probe.get("duration", 0.0)
    except Exception as err:
        if input_save_path.exists():
            input_save_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "code": "unsupported_media",
                "message": f"File bukan media audio/video valid: {err}",
            },
        ) from err

    # 6. Enqueue
    await job_manager.enqueue(job, input_save_path.name)
    return job


@router.get("", response_model=list[Job])
def get_jobs() -> list[Job]:
    return list_jobs()


@router.get("/{id}", response_model=Job)
def get_job(id: str) -> Job:
    valid_id = validate_job_id(id)
    job = job_manager.get_active_job(valid_id) or load_meta(valid_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Pekerjaan tidak ditemukan"},
        )
    return job


@router.get("/{id}/events")
async def get_job_events(id: str):
    valid_id = validate_job_id(id)

    async def event_generator():
        try:
            subscriber = job_manager.subscribe(valid_id)
            while True:
                try:
                    job = await asyncio.wait_for(subscriber.__anext__(), timeout=15.0)
                    is_done = job.status == JobStatus.DONE
                    is_err = job.status in {JobStatus.FAILED, JobStatus.CANCELLED}
                    evt = "done" if is_done else ("error" if is_err else "progress")
                    yield f"event: {evt}\ndata: {job.model_dump_json()}\n\n"
                    if evt in {"done", "error"}:
                        break
                except TimeoutError:
                    yield ": keepalive\n\n"
                except StopAsyncIteration:
                    break
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{id}/cancel", response_model=Job)
def cancel_job(id: str) -> Job:
    valid_id = validate_job_id(id)
    job = job_manager.cancel(valid_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Pekerjaan tidak ditemukan"},
        )
    return job


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(id: str) -> Response:
    valid_id = validate_job_id(id)
    job_manager.cancel(valid_id)
    delete_job_dir(valid_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -----------------------------------------------------------------------------
# Subtitles Endpoints
# -----------------------------------------------------------------------------


@router.get("/{id}/subtitles/{lang}", response_model=SubtitleResponse)
def get_subtitles(id: str, lang: str) -> SubtitleResponse:
    valid_id = validate_job_id(id)
    segments = load_segments(valid_id, lang)
    if segments is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"Subtitle bahasa {lang} belum tersedia"},
        )
    return SubtitleResponse(lang=lang, segments=segments)


@router.put("/{id}/subtitles/{lang}", response_model=SubtitleResponse)
def update_subtitles(id: str, lang: str, payload: SubtitleUpdateRequest) -> SubtitleResponse:
    valid_id = validate_job_id(id)
    job = load_meta(valid_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Pekerjaan tidak ditemukan"},
        )

    segments = payload.segments

    for i, seg in enumerate(segments):
        if seg.end <= seg.start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "invalid_option",
                    "message": f"Cue #{seg.index}: waktu akhir harus > awal",
                },
            )
        if seg.text.count("\n") > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "invalid_option",
                    "message": f"Cue #{seg.index}: teks melebihi 2 baris",
                },
            )
        if i > 0 and seg.start < segments[i - 1].end:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "invalid_option",
                    "message": f"Cue #{seg.index}: tumpang tindih dengan cue sebelumnya",
                },
            )

    save_segments(valid_id, lang, segments)
    srt_content = segments_to_srt(segments)
    vtt_content = segments_to_vtt(segments)

    srt_file = get_job_file(valid_id, f"subtitle.{lang}.srt")
    vtt_file = get_job_file(valid_id, f"subtitle.{lang}.vtt")
    srt_file.write_text(srt_content, encoding="utf-8")
    vtt_file.write_text(vtt_content, encoding="utf-8")

    return SubtitleResponse(lang=lang, segments=segments)


@router.get("/{id}/subtitles/{lang}/download")
def download_subtitles(
    id: str,
    lang: str,
    format: Literal["srt", "vtt"] = "srt",
    bilingual: bool = False,
    order: Literal["source_first", "target_first"] = "source_first",
):
    valid_id = validate_job_id(id)
    job = load_meta(valid_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Pekerjaan tidak ditemukan"},
        )

    target_segments = load_segments(valid_id, lang)
    if target_segments is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"Subtitle bahasa {lang} belum tersedia"},
        )

    base_name = Path(job.filename).stem

    if bilingual:
        src_lang = job.source_lang_detected or job.source_lang_requested
        if src_lang == lang:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "invalid_option",
                    "message": "Subtitle dwibahasa butuh bahasa target berbeda dari sumber",
                },
            )
        src_segments = load_segments(valid_id, src_lang) or []
        segments = combine_bilingual_subtitles(src_segments, target_segments, order=order)
        filename = f"{base_name}.{src_lang}_{lang}.{format}"
    else:
        segments = target_segments
        filename = f"{base_name}.{lang}.{format}"

    if format == "vtt":
        content = segments_to_vtt(segments)
        media_type = "text/vtt; charset=utf-8"
    else:
        content = segments_to_srt(segments)
        media_type = "application/x-subrip; charset=utf-8"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": format_content_disposition(filename)},
    )


@router.post("/{id}/translate", status_code=status.HTTP_202_ACCEPTED, response_model=Job)
async def translate_job(id: str, payload: TranslateRequest) -> Job:
    valid_id = validate_job_id(id)
    job = load_meta(valid_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Pekerjaan tidak ditemukan"},
        )

    if job.status in {
        JobStatus.EXTRACTING_AUDIO,
        JobStatus.TRANSCRIBING,
        JobStatus.SEGMENTING,
        JobStatus.TRANSLATING,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "job_busy",
                "message": "Pekerjaan sedang berjalan, tunggu hingga selesai",
            },
        )

    src_lang = job.source_lang_detected or job.source_lang_requested
    if src_lang == "auto" or src_lang not in job.available_langs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "source_unavailable",
                "message": "Subtitle bahasa sumber belum tersedia",
            },
        )

    targets = [t for t in payload.target_langs if t in SUPPORTED_TARGET_CODES and t != src_lang]
    if not targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_option",
                "message": "Target bahasa harus berbeda dari bahasa sumber dan didukung",
            },
        )

    src_segments = load_segments(valid_id, src_lang)
    if not src_segments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Segmen subtitle sumber tidak ditemukan"},
        )

    for t in targets:
        if t not in job.target_langs:
            job.target_langs.append(t)

    job.status = JobStatus.TRANSLATING
    job.stage_progress = 0.0
    job.progress = 0.70
    save_meta(job)
    job_manager.emit(job)

    async def run_on_demand_translation():
        translator = job_manager.pipeline.translator or get_default_translator()

        if isinstance(translator, ClaudeTranslator) and not settings.anthropic_api_key:
            warn = "Terjemahan dilewati: ANTHROPIC_API_KEY belum dikonfigurasi di file .env"
            logger.warning(warn)
            job.warnings.append(warn)
            job.status = JobStatus.DONE
            job.stage_progress = 1.0
            job.progress = 1.0
            save_meta(job)
            job_manager.emit(job)
            return

        total_targets = len(targets)
        for idx, tgt in enumerate(targets):

            def on_prog(p: float, cur_idx: int = idx):
                job.stage_progress = p
                job.progress = 0.70 + (0.30 * ((cur_idx + p) / total_targets))
                save_meta(job)
                job_manager.emit(job)

            try:
                translated_segs = await translator.translate(
                    segments=src_segments,
                    source=src_lang,
                    target=tgt,
                    on_progress=on_prog,
                )
                save_segments(valid_id, tgt, translated_segs)
                srt_content = segments_to_srt(translated_segs)
                vtt_content = segments_to_vtt(translated_segs)
                get_job_file(valid_id, f"subtitle.{tgt}.srt").write_text(
                    srt_content, encoding="utf-8"
                )
                get_job_file(valid_id, f"subtitle.{tgt}.vtt").write_text(
                    vtt_content, encoding="utf-8"
                )
                if tgt not in job.available_langs:
                    job.available_langs.append(tgt)
            except Exception as err:
                logger.error("Terjemahan ke %s gagal: %s", tgt, err)
                job.warnings.append(f"Gagal menerjemahkan ke {tgt}: {err}")

        job.status = JobStatus.DONE
        job.stage_progress = 1.0
        job.progress = 1.0
        save_meta(job)
        job_manager.emit(job)

    asyncio.create_task(run_on_demand_translation())
    return job


# -----------------------------------------------------------------------------
# Media Stream (with HTTP 206 Range support)
# -----------------------------------------------------------------------------


@router.get("/{id}/media")
async def stream_media(id: str, request: Request):
    valid_id = validate_job_id(id)
    job_dir = get_job_dir(valid_id)

    media_path: Path | None = None
    for item in job_dir.glob("input.*"):
        if item.is_file():
            media_path = item
            break

    if not media_path or not media_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "File media tidak ditemukan"},
        )

    file_size = media_path.stat().st_size
    range_header = request.headers.get("range")

    if not range_header:
        return FileResponse(media_path, filename=media_path.name)

    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not range_match:
        return FileResponse(media_path, filename=media_path.name)

    start = int(range_match.group(1))
    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1

    if start >= file_size or end >= file_size or start > end:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_size = (end - start) + 1

    def iter_file():
        with open(media_path, "rb") as f:
            f.seek(start)
            bytes_left = chunk_size
            while bytes_left > 0:
                read_size = min(bytes_left, 64 * 1024)
                data = f.read(read_size)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
    }

    return StreamingResponse(
        iter_file(),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        headers=headers,
    )


# -----------------------------------------------------------------------------
# Media Subtitle Export (Hardsub Burn-in & Softsub MP4)
# -----------------------------------------------------------------------------


def get_media_download_filename(job_filename: str, lang: str) -> str:
    base_name = Path(job_filename).stem
    lang_map = {
        "id": "ID",
        "en": "ENG",
        "zh": "CN",
    }
    tag = lang_map.get(lang.lower(), lang.upper())
    return f"{base_name} SUB-{tag}.mp4"


@router.post("/{id}/burn", status_code=status.HTTP_202_ACCEPTED, response_model=Job)
async def burn_job_subtitle(id: str, payload: BurnRequest) -> Job:
    valid_id = validate_job_id(id)
    job = load_meta(valid_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Pekerjaan tidak ditemukan"},
        )

    lang = payload.lang
    mode = payload.mode.lower() if payload.mode else "hard"
    if not lang or lang not in job.available_langs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "message": f"Subtitle bahasa {lang} belum tersedia untuk ekspor media",
            },
        )

    job_dir = get_job_dir(valid_id)
    input_file: Path | None = None
    for cand in job_dir.glob("input.*"):
        if cand.is_file():
            input_file = cand
            break

    if not input_file:
        raise HTTPException(status_code=404, detail="Input media tidak ditemukan")

    srt_file = get_job_file(valid_id, f"subtitle.{lang}.srt")

    if mode == "soft":
        softsub_file = get_job_file(valid_id, f"softsub.{lang}.mp4")

        async def run_softsub():
            try:
                await asyncio.to_thread(embed_soft_subtitles, input_file, srt_file, softsub_file, lang=lang)
                if lang not in job.softsub_langs:
                    job.softsub_langs.append(lang)
                save_meta(job)
                job_manager.emit(job)
            except Exception as err:
                logger.error("Softsub export failed: %s", err)

        asyncio.create_task(run_softsub())
        return job

    # Hard sub (burn-in re-encode)
    burned_file = get_job_file(valid_id, f"burned.{lang}.mp4")
    job.burn_progress[lang] = 0.01
    save_meta(job)
    job_manager.emit(job)

    async def run_burn():
        try:
            last_save = 0.0

            def on_burn_prog(p: float):
                nonlocal last_save
                job.burn_progress[lang] = round(p, 2)
                now = time.monotonic()
                if now - last_save >= 1.0 or p >= 0.99:
                    last_save = now
                    save_meta(job)
                job_manager.emit(job)

            await asyncio.to_thread(
                burn_subtitles,
                input_file,
                srt_file,
                burned_file,
                lang=lang,
                duration=job.duration_sec,
                on_progress=on_burn_prog,
            )
            job.burn_progress[lang] = 1.0
            if lang not in job.burned_langs:
                job.burned_langs.append(lang)
            save_meta(job)
            job_manager.emit(job)
        except Exception as err:
            logger.error("Burn subtitle failed: %s", err)
            job.burn_progress.pop(lang, None)
            job.warnings.append(f"Gagal burn-in subtitle {lang}: {err}")
            save_meta(job)
            job_manager.emit(job)

    asyncio.create_task(run_burn())
    return job


@router.get("/{id}/burned/{lang}")
def get_burned_video(id: str, lang: str):
    valid_id = validate_job_id(id)
    job = load_meta(valid_id)
    if not job:
        raise HTTPException(status_code=404, detail="Pekerjaan tidak ditemukan")

    burned_path = get_job_file(valid_id, f"burned.{lang}.mp4")
    if not burned_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"Video burn-in {lang} belum tersedia"},
        )

    download_name = get_media_download_filename(job.filename, lang)
    return FileResponse(
        burned_path,
        media_type="video/mp4",
        headers={"Content-Disposition": format_content_disposition(download_name)},
    )


@router.get("/{id}/softsub/{lang}")
def get_softsub_video(id: str, lang: str):
    valid_id = validate_job_id(id)
    job = load_meta(valid_id)
    if not job:
        raise HTTPException(status_code=404, detail="Pekerjaan tidak ditemukan")

    softsub_path = get_job_file(valid_id, f"softsub.{lang}.mp4")
    if not softsub_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"Video softsub {lang} belum tersedia"},
        )

    download_name = get_media_download_filename(job.filename, lang)
    return FileResponse(
        softsub_path,
        media_type="video/mp4",
        headers={"Content-Disposition": format_content_disposition(download_name)},
    )
