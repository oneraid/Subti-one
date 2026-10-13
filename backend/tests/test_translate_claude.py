from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Segment
from app.translate.claude import ClaudeTranslator, FakeTranslator


@pytest.mark.asyncio
async def test_fake_translator():
    translator = FakeTranslator()
    segments = [
        Segment(index=1, start=0.0, end=1.5, text="Halo dunia."),
        Segment(index=2, start=1.5, end=3.0, text="Selamat pagi"),
    ]
    progs = []
    res = await translator.translate(
        segments=segments,
        source="id",
        target="en",
        on_progress=lambda p: progs.append(p),
    )
    assert len(res) == 2
    assert res[0].index == 1
    assert res[0].start == 0.0
    assert res[0].end == 1.5
    assert "Hello world." in res[0].text
    assert len(progs) > 0


@pytest.mark.asyncio
async def test_claude_translator_skip_identical_language():
    translator = ClaudeTranslator()
    segments = [Segment(index=1, start=0.0, end=1.0, text="Test")]
    res = await translator.translate(segments, source="id", target="id")
    assert res == segments


@pytest.mark.asyncio
async def test_claude_translator_with_mock_tool_call():
    mock_client = MagicMock()
    mock_messages = AsyncMock()
    mock_client.messages = mock_messages

    # Create mock tool use response block
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = "submit_translated_subtitles"
    tool_use_block.input = {
        "items": [
            {"id": 1, "text": "Good morning"},
            {"id": 2, "text": "Welcome to AutoSub"},
        ]
    }

    mock_response = MagicMock()
    mock_response.content = [tool_use_block]
    mock_messages.create.return_value = mock_response

    translator = ClaudeTranslator(client=mock_client)
    segments = [
        Segment(index=1, start=0.0, end=2.0, text="Selamat pagi"),
        Segment(index=2, start=2.0, end=4.0, text="Selamat datang di AutoSub"),
    ]

    progs = []
    res = await translator.translate(
        segments=segments,
        source="id",
        target="en",
        on_progress=lambda p: progs.append(p),
    )

    assert len(res) == 2
    assert res[0].text == "Good morning"
    assert res[1].text == "Welcome to AutoSub"
    assert len(progs) == 1
    assert progs[-1] == 1.0


@pytest.mark.asyncio
async def test_claude_translator_fallback_to_source_on_failure():
    mock_client = MagicMock()
    mock_messages = AsyncMock()
    mock_client.messages = mock_messages

    # Mock raises exception on all calls
    mock_messages.create.side_effect = RuntimeError("API unavailable")

    translator = ClaudeTranslator(client=mock_client)
    segments = [
        Segment(index=1, start=0.0, end=2.0, text="Kalimat satu"),
        Segment(index=2, start=2.0, end=4.0, text="Kalimat dua"),
    ]

    with patch("asyncio.sleep", new_callable=AsyncMock):
        res = await translator.translate(
            segments=segments,
            source="id",
            target="en",
        )
    assert len(res) == 2
    assert res[0].text == "Kalimat satu"
    assert res[1].text == "Kalimat dua"
