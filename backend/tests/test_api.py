import asyncio
import io
import subprocess

import pytest
from httpx import ASGITransport, AsyncClient

from app.jobs import job_manager
from app.main import app
from app.transcribe import FakeTranscriber
from app.translate.claude import FakeTranslator


@pytest.fixture
async def fake_pipeline():
    """
    Inject FakeTranscriber and FakeTranslator into JobManager during tests
    and ensure workers run.
    """
    original_transcriber = job_manager.pipeline.transcriber
    original_translator = job_manager.pipeline.translator
    job_manager.pipeline.transcriber = FakeTranscriber(
        words=[
            (0.5, 1.5, "Halo"),
            (1.6, 2.5, "dunia."),
            (3.0, 4.0, "AutoSub."),
        ],
        detected_lang="id",
    )
    job_manager.pipeline.translator = FakeTranslator()
    if not job_manager.workers:
        job_manager.start()
    try:
        yield
    finally:
        job_manager.pipeline.transcriber = original_transcriber
        job_manager.pipeline.translator = original_translator
        await job_manager.stop()


@pytest.fixture
def test_wav_bytes() -> bytes:
    """Generate minimal valid WAV audio bytes."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:duration=1.0",
        "-c:a",
        "pcm_s16le",
        "-f",
        "wav",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    return proc.stdout


@pytest.mark.asyncio
async def test_upload_and_pipeline_flow(fake_pipeline, test_wav_bytes):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Upload valid media
        files = {"file": ("test_clip.wav", io.BytesIO(test_wav_bytes), "audio/wav")}
        data = {
            "source_lang": "auto",
            "model_size": "tiny",
        }
        res = await client.post("/api/jobs", files=files, data=data)
        assert res.status_code == 201
        job_data = res.json()
        job_id = job_data["id"]
        assert job_data["status"] == "queued"

        # 2. Poll until done (FakeTranscriber completes in background worker)
        for _ in range(20):
            res_poll = await client.get(f"/api/jobs/{job_id}")
            assert res_poll.status_code == 200
            current_job = res_poll.json()
            if current_job["status"] == "done":
                break
            await asyncio.sleep(0.2)

        assert current_job["status"] == "done"
        assert "id" in current_job["available_langs"]

        # 3. Get Subtitles
        sub_res = await client.get(f"/api/jobs/{job_id}/subtitles/id")
        assert sub_res.status_code == 200
        sub_json = sub_res.json()
        assert len(sub_json["segments"]) >= 1

        # 4. Download SRT
        dl_res = await client.get(f"/api/jobs/{job_id}/subtitles/id/download?format=srt")
        assert dl_res.status_code == 200
        assert "-->" in dl_res.text

        # 5. Download VTT
        dl_vtt = await client.get(f"/api/jobs/{job_id}/subtitles/id/download?format=vtt")
        assert dl_vtt.status_code == 200
        assert "WEBVTT" in dl_vtt.text

        # 6. Edit Subtitles PUT
        updated_segments = [
            {"index": 1, "start": 0.5, "end": 2.0, "text": "Halo Indonesia"},
            {"index": 2, "start": 2.5, "end": 4.0, "text": "Subtitle diedit"},
        ]
        put_res = await client.put(
            f"/api/jobs/{job_id}/subtitles/id",
            json={"segments": updated_segments},
        )
        assert put_res.status_code == 200
        assert put_res.json()["segments"][0]["text"] == "Halo Indonesia"


@pytest.mark.asyncio
async def test_upload_invalid_media_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Non-media text file with .mp4 extension
        files = {"file": ("fake.mp4", io.BytesIO(b"this is plain text not media"), "video/mp4")}
        res = await client.post("/api/jobs", files=files)
        assert res.status_code == 415
        assert res.json()["error"]["code"] == "unsupported_media"


@pytest.mark.asyncio
async def test_invalid_source_lang_rejected(test_wav_bytes):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = {"file": ("test.wav", io.BytesIO(test_wav_bytes), "audio/wav")}
        data = {"source_lang": "klingon"}
        res = await client.post("/api/jobs", files=files, data=data)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "invalid_option"


@pytest.mark.asyncio
async def test_path_traversal_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/jobs/../../etc/passwd")
        assert res.status_code in {404, 422}


@pytest.mark.asyncio
async def test_cancel_job(fake_pipeline, test_wav_bytes):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = {"file": ("cancel_test.wav", io.BytesIO(test_wav_bytes), "audio/wav")}
        res = await client.post("/api/jobs", files=files)
        assert res.status_code == 201
        job_id = res.json()["id"]

        cancel_res = await client.post(f"/api/jobs/{job_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_translate_job_flow(fake_pipeline, test_wav_bytes):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Upload valid media
        files = {"file": ("test_clip.wav", io.BytesIO(test_wav_bytes), "audio/wav")}
        data = {"source_lang": "auto", "model_size": "tiny"}
        res = await client.post("/api/jobs", files=files, data=data)
        assert res.status_code == 201
        job_id = res.json()["id"]

        # Poll until done
        for _ in range(30):
            res_poll = await client.get(f"/api/jobs/{job_id}")
            if res_poll.json()["status"] == "done":
                break
            await asyncio.sleep(0.2)
        assert res_poll.json()["status"] == "done"

        # Trigger on-demand translation to 'en'
        trans_res = await client.post(
            f"/api/jobs/{job_id}/translate",
            json={"target_langs": ["en"]},
        )
        assert trans_res.status_code == 202

        # Poll until translation finishes
        current = {}
        for _ in range(20):
            res_poll = await client.get(f"/api/jobs/{job_id}")
            current = res_poll.json()
            if "en" in current.get("available_langs", []):
                break
            await asyncio.sleep(0.2)

        assert "en" in current["available_langs"]

        # Check translated subtitles
        sub_en = await client.get(f"/api/jobs/{job_id}/subtitles/en")
        assert sub_en.status_code == 200
        assert len(sub_en.json()["segments"]) > 0

        # Check bilingual download
        dl_bilingual = await client.get(f"/api/jobs/{job_id}/subtitles/en/download?bilingual=true")
        assert dl_bilingual.status_code == 200
        assert "-->" in dl_bilingual.text
