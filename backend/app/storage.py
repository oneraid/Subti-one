import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from app.config import settings
from app.models import Job, Segment

logger = logging.getLogger(__name__)


def ensure_data_dirs() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.whisper_model_dir.mkdir(parents=True, exist_ok=True)
    jobs_root = settings.data_dir / "jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)


def validate_uuid(job_id: UUID | str) -> UUID:
    if isinstance(job_id, UUID):
        return job_id
    try:
        return UUID(str(job_id))
    except (ValueError, TypeError, AttributeError) as err:
        raise ValueError(f"Invalid job ID: {job_id}") from err


def get_job_dir(job_id: UUID | str) -> Path:
    valid_id = validate_uuid(job_id)
    jobs_root = (settings.data_dir / "jobs").resolve()
    job_dir = (jobs_root / str(valid_id)).resolve()

    # Prevent path traversal
    if not job_dir.is_relative_to(jobs_root):
        raise ValueError("Invalid job directory path traversal detected")

    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def save_meta(job: Job) -> None:
    job_dir = get_job_dir(job.id)
    meta_path = job_dir / "meta.json"
    temp_fd, temp_path = tempfile.mkstemp(dir=job_dir, prefix="meta_", suffix=".tmp")
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            f.write(job.model_dump_json(indent=2))
        os.replace(temp_path, meta_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def load_meta(job_id: UUID | str) -> Job | None:
    try:
        job_dir = get_job_dir(job_id)
        meta_path = job_dir / "meta.json"
        if not meta_path.exists():
            return None
        with open(meta_path, encoding="utf-8") as f:
            data = json.load(f)
            return Job.model_validate(data)
    except Exception as err:
        logger.warning("Failed to load meta for job %s: %s", job_id, err)
        return None


def list_jobs() -> list[Job]:
    ensure_data_dirs()
    jobs_root = settings.data_dir / "jobs"
    jobs: list[Job] = []
    if not jobs_root.exists():
        return jobs

    for item in jobs_root.iterdir():
        if item.is_dir():
            meta_path = item / "meta.json"
            if meta_path.is_file():
                try:
                    with open(meta_path, encoding="utf-8") as f:
                        data = json.load(f)
                        jobs.append(Job.model_validate(data))
                except Exception as err:
                    logger.debug("Skipping unparseable job in %s: %s", item, err)

    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return jobs


def delete_job_dir(job_id: UUID | str) -> bool:
    try:
        job_dir = get_job_dir(job_id)
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
            return True
        return False
    except Exception as err:
        logger.error("Failed to delete job %s: %s", job_id, err)
        return False


def save_segments(job_id: UUID | str, lang: str, segments: list[Segment]) -> None:
    job_dir = get_job_dir(job_id)
    file_path = job_dir / f"segments.{lang}.json"
    temp_fd, temp_path = tempfile.mkstemp(dir=job_dir, prefix=f"seg_{lang}_", suffix=".tmp")
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            data = [s.model_dump() for s in segments]
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, file_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def load_segments(job_id: UUID | str, lang: str) -> list[Segment] | None:
    job_dir = get_job_dir(job_id)
    file_path = job_dir / f"segments.{lang}.json"
    if not file_path.exists():
        return None
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
            return [Segment.model_validate(item) for item in data]
    except Exception as err:
        logger.error("Failed to read segments for job %s lang %s: %s", job_id, lang, err)
        return None


def get_job_file(job_id: UUID | str, filename: str) -> Path:
    job_dir = get_job_dir(job_id)
    file_path = (job_dir / filename).resolve()
    if not file_path.is_relative_to(job_dir):
        raise ValueError("Invalid file access path traversal")
    return file_path
