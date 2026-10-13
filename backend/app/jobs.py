import asyncio
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from app.config import settings
from app.models import Job, JobStatus
from app.pipeline import SubtitlePipeline
from app.storage import (
    delete_job_dir,
    get_job_file,
    list_jobs,
    load_meta,
    save_meta,
)

logger = logging.getLogger(__name__)


class JobManager:
    def __init__(self, pipeline: SubtitlePipeline | None = None):
        self.pipeline = pipeline or SubtitlePipeline()
        self.queue: asyncio.Queue[UUID] = asyncio.Queue()
        self.workers: list[asyncio.Task] = []
        self.cancelled_jobs: set[UUID] = set()
        self.listeners: dict[UUID, list[asyncio.Queue[Job]]] = {}
        self.active_jobs: dict[UUID, Job] = {}
        self.cleanup_task: asyncio.Task | None = None

    def start(self) -> None:
        """Start worker loop and retention cleanup tasks."""
        self.queue = asyncio.Queue()
        self.cancelled_jobs.clear()
        self.active_jobs.clear()
        for i in range(settings.max_concurrent_jobs):
            task = asyncio.create_task(self._worker(i))
            self.workers.append(task)
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("JobManager started with %d workers", settings.max_concurrent_jobs)

    async def stop(self) -> None:
        """Gracefully stop workers."""
        for task in self.workers:
            task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        if self.cleanup_task:
            await asyncio.gather(self.cleanup_task, return_exceptions=True)
        self.workers.clear()
        self.cleanup_task = None

    async def enqueue(self, job: Job, input_file_name: str) -> None:
        """Queue a new job for execution."""
        save_meta(job)
        self.emit(job)
        await self.queue.put(job.id)

    def cancel(self, job_id: UUID) -> Job | None:
        """Mark a job as cancelled."""
        self.cancelled_jobs.add(job_id)
        job = load_meta(job_id)
        if job and job.status not in {JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED}:
            job.status = JobStatus.CANCELLED
            save_meta(job)
            self.emit(job)
        return job

    def get_active_job(self, job_id: UUID) -> Job | None:
        """Return the current in-memory job if active."""
        return self.active_jobs.get(job_id)

    def emit(self, job: Job) -> None:
        """Broadcast job updates to all SSE subscribers and update active job memory."""
        self.active_jobs[job.id] = job
        queues = self.listeners.get(job.id, [])
        for q in queues:
            try:
                q.put_nowait(job)
            except asyncio.QueueFull:
                pass

    async def subscribe(self, job_id: UUID) -> AsyncGenerator[Job, None]:
        """Subscribe to real-time events for a specific job."""
        q: asyncio.Queue[Job] = asyncio.Queue(maxsize=50)
        if job_id not in self.listeners:
            self.listeners[job_id] = []
        self.listeners[job_id].append(q)

        # Emit initial current state immediately
        current_job = load_meta(job_id)
        if current_job:
            yield current_job

        try:
            while True:
                job = await q.get()
                yield job
                if job.status in {JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED}:
                    break
        finally:
            if job_id in self.listeners and q in self.listeners[job_id]:
                self.listeners[job_id].remove(q)
                if not self.listeners[job_id]:
                    del self.listeners[job_id]

    async def _worker(self, worker_id: int) -> None:
        logger.info("Worker %d ready", worker_id)
        while True:
            try:
                job_id = await self.queue.get()
                job = load_meta(job_id)
                if not job:
                    self.queue.task_done()
                    continue

                if job_id in self.cancelled_jobs:
                    job.status = JobStatus.CANCELLED
                    save_meta(job)
                    self.emit(job)
                    self.queue.task_done()
                    continue

                # Locate stored input file
                input_path: Path | None = None
                job_dir = get_job_file(job_id, "meta.json").parent
                for candidate in job_dir.glob("input.*"):
                    if candidate.is_file():
                        input_path = candidate
                        break

                if not input_path:
                    job.status = JobStatus.FAILED
                    job.error = "File masukan tidak ditemukan di direktori pekerjaan"
                    save_meta(job)
                    self.emit(job)
                    self.queue.task_done()
                    continue

                logger.info("Worker %d starting pipeline for job %s", worker_id, job_id)

                def check_cancelled(jid: UUID = job_id) -> bool:
                    return jid in self.cancelled_jobs

                await self.pipeline.run(
                    job=job,
                    input_path=input_path,
                    on_event=self.emit,
                    check_cancelled=check_cancelled,
                )

                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as err:
                logger.exception("Worker %d uncaught error: %s", worker_id, err)

    async def _cleanup_loop(self) -> None:
        """Periodically clean up jobs older than FILE_RETENTION_HOURS."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                retention_cutoff = datetime.now(UTC) - timedelta(
                    hours=settings.file_retention_hours
                )
                jobs = list_jobs()
                for job in jobs:
                    if job.created_at < retention_cutoff:
                        logger.info(
                            "Cleaning up expired job %s (created %s)", job.id, job.created_at
                        )
                        delete_job_dir(job.id)
            except asyncio.CancelledError:
                break
            except Exception as err:
                logger.error("Cleanup loop error: %s", err)


# Global singleton instance
job_manager = JobManager()
