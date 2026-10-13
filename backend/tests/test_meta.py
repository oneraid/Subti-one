import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "ffmpeg" in data
        assert "whisper_model" in data
        assert "translator" in data
        assert "translator_ready" in data


@pytest.mark.asyncio
async def test_config_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert len(data["source_languages"]) == 4
        assert [s["code"] for s in data["source_languages"]] == ["auto", "id", "en", "zh"]
        assert [t["code"] for t in data["target_languages"]] == ["en", "id"]
        assert "tiny" in data["whisper_models"]
        assert data["default_model"] == "small"
        assert data["max_upload_mb"] > 0
