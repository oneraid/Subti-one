from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.models import Segment
from app.translate.google import GoogleTranslator


@pytest.mark.asyncio
async def test_google_translator_empty_and_same_lang():
    translator = GoogleTranslator()
    assert await translator.translate([], source="en", target="id") == []

    segs = [Segment(index=1, start=0.0, end=1.0, text="Test")]
    assert await translator.translate(segs, source="id", target="id") == segs


@pytest.mark.asyncio
async def test_google_translator_success():
    translator = GoogleTranslator()
    segs = [
        Segment(index=1, start=0.0, end=2.0, text="Hello world"),
        Segment(index=2, start=2.0, end=4.0, text="Welcome"),
    ]

    req = httpx.Request("GET", "https://translate.googleapis.com")
    mock_resp = httpx.Response(status_code=200, json=[[["Halo dunia", "Hello world"]]], request=req)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        progs = []
        result = await translator.translate(
            segs,
            source="en",
            target="id",
            on_progress=lambda p: progs.append(p),
        )

        assert len(result) == 2
        assert result[0].index == 1
        assert result[0].start == 0.0
        assert result[0].end == 2.0
        assert result[0].text == "Halo dunia"
        assert len(progs) == 2
        assert progs[-1] == 1.0


@pytest.mark.asyncio
async def test_google_translator_fallback_on_network_error():
    translator = GoogleTranslator()
    segs = [
        Segment(index=1, start=0.0, end=2.0, text="Original text"),
    ]

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = RuntimeError("Network timeout")
        result = await translator.translate(segs, source="en", target="id")
        assert len(result) == 1
        # Falls back to original text safely
        assert result[0].text == "Original text"
