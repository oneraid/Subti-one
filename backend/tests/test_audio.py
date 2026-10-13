import subprocess
from pathlib import Path

import pytest

from app.audio import AudioProcessingError, extract_audio, probe_media


@pytest.fixture
def sample_audio_file(tmp_path: Path) -> Path:
    """Generate a 2-second sine wave audio using ffmpeg for testing."""
    out_file = tmp_path / "test_sine.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:duration=2.0",
        "-c:a",
        "pcm_s16le",
        str(out_file),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out_file


def test_probe_media(sample_audio_file: Path):
    info = probe_media(sample_audio_file)
    assert info["has_audio"] is True
    assert info["duration"] >= 1.9


def test_probe_invalid_media(tmp_path: Path):
    corrupt_file = tmp_path / "corrupt.mp4"
    corrupt_file.write_text("not a real video file", encoding="utf-8")
    with pytest.raises(AudioProcessingError):
        probe_media(corrupt_file)


def test_extract_audio(sample_audio_file: Path, tmp_path: Path):
    out_wav = tmp_path / "extracted.wav"
    extract_audio(sample_audio_file, out_wav)
    assert out_wav.exists()
    assert out_wav.stat().st_size > 0
    info = probe_media(out_wav)
    assert info["has_audio"] is True
