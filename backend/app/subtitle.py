import re

from app.models import Segment


def format_timestamp_srt(seconds: float) -> str:
    """Format seconds into SRT timestamp HH:MM:SS,mmm."""
    seconds = max(0.0, seconds)
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_seconds = total_ms // 1000
    s = total_seconds % 60
    total_minutes = total_seconds // 60
    m = total_minutes % 60
    h = total_minutes // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Format seconds into WebVTT timestamp HH:MM:SS.mmm."""
    seconds = max(0.0, seconds)
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_seconds = total_ms // 1000
    s = total_seconds % 60
    total_minutes = total_seconds // 60
    m = total_minutes % 60
    h = total_minutes // 60
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def parse_timestamp(ts: str) -> float:
    """Parse SRT (HH:MM:SS,mmm) or VTT (HH:MM:SS.mmm or MM:SS.mmm) into seconds."""
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        h = float(parts[0])
        m = float(parts[1])
        s = float(parts[2])
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m = float(parts[0])
        s = float(parts[1])
        return m * 60 + s
    return float(parts[0])


def segments_to_srt(segments: list[Segment]) -> str:
    """Convert a list of Segment objects to an SRT formatted string."""
    blocks: list[str] = []
    for i, seg in enumerate(segments, start=1):
        start_str = format_timestamp_srt(seg.start)
        end_str = format_timestamp_srt(seg.end)
        text = seg.text.strip()
        blocks.append(f"{i}\n{start_str} --> {end_str}\n{text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def segments_to_vtt(segments: list[Segment]) -> str:
    """Convert a list of Segment objects to a WebVTT formatted string."""
    lines = ["WEBVTT", ""]
    for i, seg in enumerate(segments, start=1):
        start_str = format_timestamp_vtt(seg.start)
        end_str = format_timestamp_vtt(seg.end)
        text = seg.text.strip()
        lines.append(str(i))
        lines.append(f"{start_str} --> {end_str}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def srt_to_segments(srt_text: str) -> list[Segment]:
    """Parse an SRT formatted string into a list of Segment objects."""
    clean_text = srt_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not clean_text:
        return []

    # Match blocks separated by blank lines
    blocks = re.split(r"\n\s*\n", clean_text)
    segments: list[Segment] = []

    time_pattern = re.compile(
        r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3}|\d{1,2}:\d{2}[,\.]\d{1,3})"
        r"\s*-->\s*"
        r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3}|\d{1,2}:\d{2}[,\.]\d{1,3})"
    )

    idx = 1
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        time_line_idx = -1
        time_match = None
        for i, line in enumerate(lines):
            m = time_pattern.search(line)
            if m:
                time_match = m
                time_line_idx = i
                break

        if not time_match or time_line_idx < 0:
            continue

        start_sec = parse_timestamp(time_match.group(1))
        end_sec = parse_timestamp(time_match.group(2))
        text_lines = lines[time_line_idx + 1 :]
        text = "\n".join(text_lines).strip()

        if text:
            segments.append(
                Segment(
                    index=idx,
                    start=start_sec,
                    end=end_sec,
                    text=text,
                )
            )
            idx += 1

    return segments


def vtt_to_segments(vtt_text: str) -> list[Segment]:
    """Parse a WebVTT formatted string into a list of Segment objects."""
    clean_text = vtt_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    # Remove header
    clean_text = re.sub(r"^WEBVTT.*?\n", "", clean_text, flags=re.IGNORECASE).strip()
    return srt_to_segments(clean_text)


def combine_bilingual_subtitles(
    source_segments: list[Segment],
    target_segments: list[Segment],
    order: str = "source_first",
) -> list[Segment]:
    """
    Combine source and target segments into bilingual cues.
    Matches segments by index or nearest start timestamp.
    """
    if len(source_segments) == len(target_segments):
        bilingual: list[Segment] = []
        paired = zip(source_segments, target_segments, strict=False)
        for i, (src, tgt) in enumerate(paired, start=1):
            if order == "target_first":
                text = f"{tgt.text.strip()}\n{src.text.strip()}"
            else:
                text = f"{src.text.strip()}\n{tgt.text.strip()}"
            bilingual.append(
                Segment(
                    index=i,
                    start=src.start,
                    end=src.end,
                    text=text,
                )
            )
        return bilingual

    # Fallback timestamp matching if segment lengths differ
    bilingual = []
    tgt_idx = 0
    for i, src in enumerate(source_segments, start=1):
        # find target segment closest to src.start
        best_tgt = None
        min_diff = float("inf")
        while tgt_idx < len(target_segments):
            tgt = target_segments[tgt_idx]
            diff = abs(tgt.start - src.start)
            if diff < min_diff:
                min_diff = diff
                best_tgt = tgt
                tgt_idx += 1
            else:
                break

        tgt_text = best_tgt.text.strip() if best_tgt else ""
        if order == "target_first" and tgt_text:
            text = f"{tgt_text}\n{src.text.strip()}"
        elif tgt_text:
            text = f"{src.text.strip()}\n{tgt_text}"
        else:
            text = src.text.strip()

        bilingual.append(
            Segment(
                index=i,
                start=src.start,
                end=src.end,
                text=text,
            )
        )

    return bilingual
