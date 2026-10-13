import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.jobs import job_manager
from app.models import JobStatus
from app.routers import jobs, meta
from app.storage import ensure_data_dirs, list_jobs, save_meta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("autosub")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    logger.info("Starting AutoSub backend...")
    ensure_data_dirs()

    # Recovery: Mark any unfinished jobs from prior run as failed
    try:
        existing_jobs = list_jobs()
        for job in existing_jobs:
            if job.status in {
                JobStatus.QUEUED,
                JobStatus.EXTRACTING_AUDIO,
                JobStatus.TRANSCRIBING,
                JobStatus.SEGMENTING,
                JobStatus.TRANSLATING,
            }:
                job.status = JobStatus.FAILED
                job.error = "Dihentikan karena server restart"
                save_meta(job)
                logger.info("Marked unfinished job %s as failed due to restart", job.id)
    except Exception as err:
        logger.error("Error during startup job recovery: %s", err)

    # Start JobManager workers
    job_manager.start()

    yield

    # Shutdown
    logger.info("Shutting down AutoSub backend...")
    await job_manager.stop()


app = FastAPI(
    title="AutoSub API",
    description="Speech-to-text and subtitle auto-translation service",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    code = "http_error"
    message = str(detail)
    if isinstance(detail, dict):
        code = detail.get("code", "http_error")
        message = detail.get("message", str(detail))
    elif exc.status_code == 404:
        code = "not_found"
    elif exc.status_code == 413:
        code = "file_too_large"
    elif exc.status_code == 415:
        code = "unsupported_media"
    elif exc.status_code == 422:
        code = "invalid_option"

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    formatted_errors = [
        f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in errors
    ]
    message = "; ".join(formatted_errors)
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid_option", "message": message}},
    )


# Include Routers
app.include_router(meta.router)
app.include_router(jobs.router)
