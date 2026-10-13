from pathlib import Path

import pytest

from app.transcribe import FakeTranscriber


def test_fake_transcriber():
    transcriber = FakeTranscriber(
        words=[(0.0, 1.0, "Test"), (1.2, 2.5, "Whisper")],
        detected_lang="en",
    )
    progress_calls = []

    def on_prog(p: float):
        progress_calls.append(p)

    words, lang, prob = transcriber.transcribe(
        audio_path=Path("dummy.wav"),
        source_lang="auto",
        duration=3.0,
        on_progress=on_prog,
    )

    assert len(words) == 2
    assert lang == "en"
    assert prob > 0.9
    assert len(progress_calls) == 3
    assert progress_calls[-1] == 1.0


@pytest.mark.slow
def test_transcriber_unsupported_language():
    # Verify rejection when detection probability is high for unsupported lang
    from app.languages import STT_LANGUAGES

    assert "es" not in STT_LANGUAGES
    assert "fr" not in STT_LANGUAGES
