import re
from typing import Any

from app.models import Segment

# Constants for optimal readability and mobile/vertical video safety
LATIN_MAX_CHARS_PER_LINE = 38
CJK_MAX_CHARS_PER_LINE = 16
MAX_CUE_DURATION = 5.0
MIN_CUE_DURATION = 0.8
SILENCE_GAP_SPLIT = 0.5
SENTENCE_MIN_DURATION = 0.8

SENTENCE_ENDINGS = re.compile(r"[\.\?!。？！]$")
PUNCTUATION_ONLY = re.compile(r"^[\s\.\?!,;:\-，、；：—…\"\(\)\[\]]+$")



def is_cjk_lang(lang: str) -> bool:
    return lang.lower() == "zh" or lang.lower().startswith("zh-")


def wrap_lines(text: str, is_cjk: bool = False) -> str:
    """
    Wrap text into at most 2 balanced lines satisfying max character constraints:
    Latin <= 42 chars/line, CJK <= 16 chars/line.
    Minimizes the difference in line lengths while avoiding breaking words (Latin).
    """
    clean_text = text.strip()
    if not clean_text:
        return ""

    max_chars = CJK_MAX_CHARS_PER_LINE if is_cjk else LATIN_MAX_CHARS_PER_LINE

    # If already has newline, check if valid and <= 2 lines
    if "\n" in clean_text:
        existing_lines = [line.strip() for line in clean_text.split("\n") if line.strip()]
        if len(existing_lines) <= 2 and all(len(line) <= max_chars for line in existing_lines):
            return "\n".join(existing_lines)
        clean_text = " ".join(existing_lines) if not is_cjk else "".join(existing_lines)

    # Fits on a single line
    if len(clean_text) <= max_chars:
        return clean_text

    # Needs to be split into 2 lines
    if is_cjk:
        # CJK: can split at punctuation or character boundary
        best_split = len(clean_text) // 2
        best_score = float("inf")

        for idx in range(1, len(clean_text)):
            line1 = clean_text[:idx].strip()
            line2 = clean_text[idx:].strip()
            diff = abs(len(line1) - len(line2))

            penalty = 0
            if len(line1) > max_chars:
                penalty += (len(line1) - max_chars) * 10
            if len(line2) > max_chars:
                penalty += (len(line2) - max_chars) * 10

            if clean_text[idx - 1] in "，、；：。？！":
                penalty -= 4  # Prefer splitting after punctuation

            score = diff + penalty
            if score < best_score:
                best_score = score
                best_split = idx

        line1 = clean_text[:best_split].strip()
        line2 = clean_text[best_split:].strip()
        if line1 and line2:
            return f"{line1}\n{line2}"
        return clean_text

    # Latin: split at space / word boundary
    words = clean_text.split()
    if len(words) <= 1:
        return clean_text

    best_split_idx = len(words) // 2
    best_score = float("inf")

    for i in range(1, len(words)):
        line1 = " ".join(words[:i])
        line2 = " ".join(words[i:])
        diff = abs(len(line1) - len(line2))

        penalty = 0
        if len(line1) > max_chars:
            penalty += (len(line1) - max_chars) * 10
        if len(line2) > max_chars:
            penalty += (len(line2) - max_chars) * 10

        if line1 and line1[-1] in ",;:-":
            penalty -= 3

        score = diff + penalty
        if score < best_score:
            best_score = score
            best_split_idx = i

    return f"{' '.join(words[:best_split_idx])}\n{' '.join(words[best_split_idx:])}"


def parse_word_item(w: Any) -> tuple[float, float, str]:
    """Helper to extract (start, end, word) from dict, tuple, or object."""
    if isinstance(w, tuple | list) and len(w) >= 3:
        return float(w[0]), float(w[1]), str(w[2])
    elif isinstance(w, dict):
        return float(w.get("start", 0.0)), float(w.get("end", 0.0)), str(w.get("word", ""))
    elif hasattr(w, "start") and hasattr(w, "end") and hasattr(w, "word"):
        return float(w.start), float(w.end), str(w.word)
    raise ValueError(f"Unrecognized word item structure: {w}")


def segment_words(words: list[Any], lang: str = "en") -> list[Segment]:
    """
    Transform timestamped words from Whisper into reading-friendly subtitle cues.
    Follows ARCHITECTURE.md §4 rules:
    - Max 2 lines per cue, line char limits (42 Latin / 16 CJK)
    - Max duration 7.0s, Min duration 1.0s
    - Split on silence >= 0.8s
    - Split at sentence endings (. ? ! 。？！) if cue >= 1.5s
    - Deduplicate hallucination repetitions (>= 3 consecutive identical cues)
    - Non-overlapping cues
    """
    if not words:
        return []

    parsed_words = [parse_word_item(w) for w in words]
    # Filter empty or pure punctuation standalone tokens
    filtered_words = []
    for s, e, w in parsed_words:
        w_clean = w.strip()
        if not w_clean or PUNCTUATION_ONLY.match(w_clean):
            continue
        filtered_words.append((s, max(s + 0.01, e), w_clean))

    if not filtered_words:
        return []

    is_cjk = is_cjk_lang(lang)
    max_line_chars = CJK_MAX_CHARS_PER_LINE if is_cjk else LATIN_MAX_CHARS_PER_LINE
    max_cue_chars = max_line_chars * 2

    raw_cues: list[dict[str, Any]] = []
    current_words: list[tuple[float, float, str]] = []

    def flush_current():
        if not current_words:
            return
        start = current_words[0][0]
        end = current_words[-1][1]

        if is_cjk:
            text = "".join(w[2] for w in current_words)
        else:
            text = " ".join(w[2] for w in current_words)

        raw_cues.append(
            {
                "start": start,
                "end": end,
                "text": text,
            }
        )
        current_words.clear()

    for _i, word in enumerate(filtered_words):
        start, end, text = word

        if not current_words:
            current_words.append(word)
            continue

        prev_end = current_words[-1][1]
        cue_start = current_words[0][0]
        silence_gap = start - prev_end
        projected_duration = end - cue_start

        # Check Silence gap >= 0.8s
        if silence_gap >= SILENCE_GAP_SPLIT:
            flush_current()
            current_words.append(word)
            continue

        # Check sentence boundary
        prev_text = current_words[-1][2]
        current_duration = prev_end - cue_start
        if current_duration >= SENTENCE_MIN_DURATION and SENTENCE_ENDINGS.search(prev_text):
            flush_current()
            current_words.append(word)
            continue

        # Check CJK clause boundary (， 、 ；) if cue has duration >= 2.0s or words >= 6
        if is_cjk and (current_duration >= 2.0 or len(current_words) >= 6):
            if re.search(r"[，、；：]$", prev_text):
                flush_current()
                current_words.append(word)
                continue

        # Check max duration
        if projected_duration >= MAX_CUE_DURATION:
            flush_current()
            current_words.append(word)
            continue

        # Check max characters (2 lines max)
        test_words = current_words + [word]
        if is_cjk:
            test_text = "".join(w[2] for w in test_words)
        else:
            test_text = " ".join(w[2] for w in test_words)
        if len(test_text) > max_cue_chars:
            flush_current()
            current_words.append(word)
            continue

        current_words.append(word)

    flush_current()

    # Post-processing:
    # 1. Clean punctuation-only cues
    valid_cues = []
    for c in raw_cues:
        cleaned_text = c["text"].strip()
        if not cleaned_text or PUNCTUATION_ONLY.match(cleaned_text):
            continue
        valid_cues.append(c)

    if not valid_cues:
        return []

    # 2. Wrap lines
    for c in valid_cues:
        c["text"] = wrap_lines(c["text"], is_cjk=is_cjk)

    # 3. Remove hallucination loops (>= 3 identical consecutive cues)
    deduped_cues: list[dict[str, Any]] = []
    repeat_count = 1
    last_text = None

    for c in valid_cues:
        if c["text"] == last_text:
            repeat_count += 1
            if repeat_count >= 3:
                continue
        else:
            repeat_count = 1
            last_text = c["text"]

        deduped_cues.append(c)

    # 4. Enforce non-overlapping and min duration
    final_segments: list[Segment] = []
    for i, c in enumerate(deduped_cues):
        start = round(c["start"], 3)
        end = round(c["end"], 3)

        next_start = deduped_cues[i + 1]["start"] if i + 1 < len(deduped_cues) else float("inf")
        if (end - start) < MIN_CUE_DURATION:
            candidate_end = start + MIN_CUE_DURATION
            if candidate_end <= next_start:
                end = candidate_end
            elif next_start > start:
                end = next_start

        if end > next_start:
            end = next_start

        if end <= start:
            end = start + 0.1

        final_segments.append(
            Segment(
                index=i + 1,
                start=round(start, 3),
                end=round(end, 3),
                text=c["text"],
            )
        )

    # 5. Split any long / multi-sentence segments
    return split_long_segments(final_segments, lang=lang)


def split_text_into_chunks(text: str, is_cjk: bool = False, max_chars: int = LATIN_MAX_CHARS_PER_LINE) -> list[str]:
    """
    Split text into chunks that each fit comfortably into at most 2 subtitle lines.
    Splits first on sentence terminators (. ? ! 。 ？ ！), then on clause boundaries (, ; : ， 、),
    and finally on word/character boundaries if still exceeding max_chars * 2.
    """
    clean = text.strip()
    if not clean:
        return []

    if is_cjk:
        raw_sentences = [s.strip() for s in re.split(r"(?<=[。？！])", clean) if s.strip()]
    else:
        raw_sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", clean) if s.strip()]

    max_chunk_chars = max_chars * 2
    candidates = raw_sentences if len(raw_sentences) > 1 else [clean]
    chunks: list[str] = []

    for candidate in candidates:
        if len(candidate) <= max_chunk_chars:
            chunks.append(candidate)
            continue

        if is_cjk:
            clauses = [c.strip() for c in re.split(r"(?<=[，、；：])", candidate) if c.strip()]
            if len(clauses) > 1:
                sub_acc = ""
                for cl in clauses:
                    if len(sub_acc) + len(cl) <= max_chunk_chars:
                        sub_acc += cl
                    else:
                        if sub_acc:
                            chunks.append(sub_acc)
                        sub_acc = cl
                if sub_acc:
                    chunks.append(sub_acc)
            else:
                mid = len(candidate) // 2
                chunks.append(candidate[:mid].strip())
                chunks.append(candidate[mid:].strip())
        else:
            clauses = [c.strip() for c in re.split(r"(?<=[,;:\-])\s+", candidate) if c.strip()]
            if len(clauses) > 1:
                sub_acc = ""
                for cl in clauses:
                    potential = f"{sub_acc} {cl}".strip() if sub_acc else cl
                    if len(potential) <= max_chunk_chars:
                        sub_acc = potential
                    else:
                        if sub_acc:
                            chunks.append(sub_acc)
                        sub_acc = cl
                if sub_acc:
                    chunks.append(sub_acc)
            else:
                words = candidate.split()
                if len(words) <= 1:
                    chunks.append(candidate)
                else:
                    mid_w = len(words) // 2
                    chunks.append(" ".join(words[:mid_w]))
                    chunks.append(" ".join(words[mid_w:]))

    return [c for c in chunks if c.strip()]


def split_long_segments(segments: list[Segment], lang: str = "id") -> list[Segment]:
    """
    Split subtitle segments that contain multiple sentences or exceed character limits.
    Distributes start and end timestamps proportionally across the sub-cues.
    Enforces non-overlapping, sequential timestamps and re-indexes segments 1..N.
    """
    if not segments:
        return []

    is_cjk = is_cjk_lang(lang)
    max_line_chars = CJK_MAX_CHARS_PER_LINE if is_cjk else LATIN_MAX_CHARS_PER_LINE
    max_cue_chars = max_line_chars * 2

    expanded: list[Segment] = []

    for seg in segments:
        flat_text = " ".join(seg.text.split("\n")).strip() if not is_cjk else "".join(seg.text.split("\n")).strip()
        if not flat_text:
            continue

        if is_cjk:
            has_multiple_sentences = len(re.findall(r"[。？！]", flat_text)) >= 2
        else:
            has_multiple_sentences = len([s for s in re.split(r"(?<=[.?!])\s+", flat_text) if s.strip()]) >= 2

        is_overlength = len(flat_text) > max_cue_chars

        if not has_multiple_sentences and not is_overlength:
            expanded.append(
                Segment(
                    index=len(expanded) + 1,
                    start=round(seg.start, 3),
                    end=round(seg.end, 3),
                    text=wrap_lines(flat_text, is_cjk=is_cjk),
                )
            )
            continue

        chunks = split_text_into_chunks(flat_text, is_cjk=is_cjk, max_chars=max_line_chars)
        if len(chunks) <= 1:
            expanded.append(
                Segment(
                    index=len(expanded) + 1,
                    start=round(seg.start, 3),
                    end=round(seg.end, 3),
                    text=wrap_lines(flat_text, is_cjk=is_cjk),
                )
            )
            continue

        duration = max(0.2, seg.end - seg.start)
        weights = [max(1, len(c.replace(" ", ""))) for c in chunks]
        total_weight = sum(weights)

        cur_start = seg.start
        for i, (chunk, w) in enumerate(zip(chunks, weights)):
            if i == len(chunks) - 1:
                cur_end = seg.end
            else:
                portion = duration * (w / total_weight)
                cur_end = round(cur_start + portion, 3)

                remaining = len(chunks) - 1 - i
                max_end = seg.end - (remaining * 0.4)
                if cur_end > max_end:
                    cur_end = max_end
                if cur_end <= cur_start:
                    cur_end = round(cur_start + 0.4, 3)

            wrapped_chunk = wrap_lines(chunk, is_cjk=is_cjk)
            expanded.append(
                Segment(
                    index=len(expanded) + 1,
                    start=round(cur_start, 3),
                    end=round(cur_end, 3),
                    text=wrapped_chunk,
                )
            )
            cur_start = cur_end

    for idx, s in enumerate(expanded, start=1):
        s.index = idx

    return expanded

