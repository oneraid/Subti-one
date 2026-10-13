import json
import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AudioProcessingError(Exception):
    """Raised when audio extraction or media probing fails."""

    pass


def probe_media(file_path: Path) -> dict[str, Any]:
    """
    Probe media file using ffprobe.
    Returns:
        {
            "duration": float,
            "has_audio": bool,
            "has_video": bool,
            "format_name": str,
        }
    Raises AudioProcessingError if media is invalid or unreadable.
    """
    if not file_path.exists():
        raise AudioProcessingError(f"File tidak ditemukan: {file_path}")

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name:stream=codec_type",
        "-of",
        "json",
        str(file_path.resolve()),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise AudioProcessingError(f"ffprobe gagal membaca file: {proc.stderr.strip()}")

        data = json.loads(proc.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])

        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        has_video = any(s.get("codec_type") == "video" for s in streams)

        if not has_audio:
            raise AudioProcessingError("File media tidak memiliki trek/stream audio.")

        duration_str = fmt.get("duration")
        duration = float(duration_str) if duration_str else 0.0

        return {
            "duration": duration,
            "has_audio": has_audio,
            "has_video": has_video,
            "format_name": fmt.get("format_name", ""),
        }
    except json.JSONDecodeError as err:
        raise AudioProcessingError("Format keluaran ffprobe tidak valid") from err
    except FileNotFoundError as err:
        raise AudioProcessingError("ffprobe tidak ditemukan di sistem (PATH)") from err


def extract_audio(input_path: Path, output_wav_path: Path) -> None:
    """
    Extract single-channel 16kHz WAV audio suitable for faster-whisper.
    ffmpeg -i input -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav
    """
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path.resolve()),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output_wav_path.resolve()),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            err_msg = proc.stderr.strip()
            raise AudioProcessingError(f"Gagal mengekstrak audio dengan ffmpeg: {err_msg}")
    except FileNotFoundError as err:
        raise AudioProcessingError("ffmpeg tidak ditemukan di sistem (PATH)") from err


def burn_subtitles(
    video_path: Path,
    srt_path: Path,
    output_video_path: Path,
    lang: str = "en",
    duration: float | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> None:
    """
    Burn subtitles into video container using ffmpeg subtitles filter.
    Properly handles Windows path escaping for ffmpeg vf filter.
    Tracks real-time progress via ffmpeg -progress pipe:1.
    """
    output_video_path.parent.mkdir(parents=True, exist_ok=True)

    # ffmpeg subtitles filter path escaping:
    # On Windows: C:\path\sub.srt -> C\:/path/sub.srt (replace \ with /, escape :)
    srt_posix = str(srt_path.resolve()).replace("\\", "/")
    if len(srt_posix) >= 2 and srt_posix[1] == ":":
        escaped_srt = srt_posix[0] + "\\:" + srt_posix[2:]
    else:
        escaped_srt = srt_posix

    # Style: Arial / Noto Sans, size 18, outline 1.5, shadow 1, margin 25
    font_family = "Arial"
    style = f"FontName={font_family},FontSize=18,Outline=1.5,Shadow=1,MarginV=25,PrimaryColour=&H00FFFFFF"
    sub_filter = f"subtitles='{escaped_srt}':force_style='{style}'"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path.resolve()),
        "-vf",
        sub_filter,
        "-c:a",
        "copy",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "22",
        "-progress",
        "pipe:1",
        "-nostats",
        "-loglevel",
        "error",
        str(output_video_path.resolve()),
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        if proc.stdout:
            while True:
                line = proc.stdout.readline()
                if not line:
                    if proc.poll() is not None:
                        break
                    continue
                line_str = line.strip()
                if line_str.startswith("out_time_us="):
                    val = line_str.split("=")[1]
                    if val.isdigit() and duration and duration > 0:
                        cur_sec = int(val) / 1_000_000.0
                        prog = min(0.99, max(0.01, cur_sec / duration))
                        if on_progress:
                            on_progress(prog)
                elif line_str == "progress=end":
                    if on_progress:
                        on_progress(1.0)

        proc.wait()
        if proc.returncode != 0:
            raise AudioProcessingError(f"Gagal burn-in subtitle (ffmpeg returncode {proc.returncode})")
    except FileNotFoundError as err:
        raise AudioProcessingError("ffmpeg tidak ditemukan di sistem (PATH)") from err


def embed_soft_subtitles(
    video_path: Path,
    srt_path: Path,
    output_video_path: Path,
    lang: str = "en",
) -> None:
    """
    Embed soft subtitles into MP4 container as mov_text subtitle stream.
    Zero video re-encoding: completes in 1-2 seconds.
    """
    output_video_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path.resolve()),
        "-i",
        str(srt_path.resolve()),
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        "-c:s",
        "mov_text",
        "-metadata:s:s:0",
        f"language={lang}",
        str(output_video_path.resolve()),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            logger.error("ffmpeg softsub error: %s", proc.stderr)
            raise AudioProcessingError(f"Gagal membuat softsub video: {proc.stderr.strip()}")
    except FileNotFoundError as err:
        raise AudioProcessingError("ffmpeg tidak ditemukan di sistem (PATH)") from err

