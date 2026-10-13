from app.segment import (
    CJK_MAX_CHARS_PER_LINE,
    LATIN_MAX_CHARS_PER_LINE,
    parse_word_item,
    segment_words,
    wrap_lines,
)


class DummyWord:
    def __init__(self, start: float, end: float, word: str):
        self.start = start
        self.end = end
        self.word = word


def test_parse_word_item():
    assert parse_word_item((1.0, 2.0, "hi")) == (1.0, 2.0, "hi")
    assert parse_word_item({"start": 1.0, "end": 2.0, "word": "hi"}) == (1.0, 2.0, "hi")
    d = DummyWord(1.0, 2.0, "hi")
    assert parse_word_item(d) == (1.0, 2.0, "hi")


def test_wrap_lines_latin():
    assert wrap_lines("") == ""
    short_text = "Hello world"
    assert wrap_lines(short_text, is_cjk=False) == "Hello world"

    # Already wrapped
    already = "Line one\nLine two"
    assert wrap_lines(already, is_cjk=False) == already

    long_text = "This is a sentence that exceeds forty-two chars and must wrap cleanly."
    wrapped = wrap_lines(long_text, is_cjk=False)
    lines = wrapped.split("\n")
    assert len(lines) == 2
    for line in lines:
        assert len(line) <= LATIN_MAX_CHARS_PER_LINE

    # Single long word
    assert wrap_lines("Supercalifragilisticexpialidocious_unbreakable_word") != ""


def test_wrap_lines_cjk():
    short_zh = "你好世界"
    assert wrap_lines(short_zh, is_cjk=True) == "你好世界"

    long_zh = "这是一个中文句子，用于测试换行逻辑是否正确在字数限制内折行。"
    wrapped = wrap_lines(long_zh, is_cjk=True)
    lines = wrapped.split("\n")
    assert len(lines) == 2
    for line in lines:
        assert len(line) <= CJK_MAX_CHARS_PER_LINE


def test_silence_gap_split():
    assert segment_words([]) == []
    words = [
        (0.0, 0.4, "Halo"),
        (0.5, 0.9, "teman"),
        (2.0, 2.5, "semua"),  # gap = 2.0 - 0.9 = 1.1s >= 0.8s -> forced split
    ]
    segments = segment_words(words, lang="id")
    assert len(segments) == 2
    assert "Halo" in segments[0].text
    assert "semua" in segments[1].text


def test_duration_split():
    # Words without pause exceeding 7.0s duration
    words = [(float(i), float(i + 0.8), f"kata{i}") for i in range(10)]
    segments = segment_words(words, lang="id")
    assert len(segments) >= 2
    for seg in segments:
        assert seg.end - seg.start <= 7.5


def test_sentence_boundary_split():
    words = [
        (0.0, 0.5, "Halo"),
        (0.6, 1.8, "dunia."),  # sentence ending with duration >= 1.5s
        (1.9, 2.4, "Ini"),
        (2.5, 3.0, "AutoSub."),
    ]
    segments = segment_words(words, lang="id")
    assert len(segments) == 2
    assert segments[0].text == "Halo dunia."
    assert segments[1].text == "Ini AutoSub."


def test_non_overlapping_and_min_duration():
    words = [
        (0.0, 0.2, "Satu"),
        (0.3, 0.5, "Dua"),
        (1.5, 2.0, "Tiga"),
    ]
    segments = segment_words(words, lang="id")
    for i in range(len(segments) - 1):
        assert segments[i].end <= segments[i + 1].start
        assert segments[i].end > segments[i].start


def test_hallucination_deduplication():
    # Simulate Whisper hallucination repeating 4 times
    words = [
        (0.0, 1.0, "Terima kasih."),
        (1.2, 2.2, "Terima kasih."),
        (2.4, 3.4, "Terima kasih."),
        (3.6, 4.6, "Terima kasih."),
        (4.8, 5.8, "Sampai jumpa."),
    ]
    segments = segment_words(words, lang="id")
    # Repetition >= 3 times should be filtered to at most 2
    repeated = [s for s in segments if "Terima kasih" in s.text]
    assert len(repeated) == 2
    assert segments[-1].text == "Sampai jumpa."


def test_discard_punctuation_only():
    words = [
        (0.0, 0.5, "..."),
        (0.6, 1.2, "Halo"),
        (1.3, 1.5, "!?"),
    ]
    segments = segment_words(words, lang="id")
    assert len(segments) == 1
    assert segments[0].text == "Halo"


def test_split_long_segments_multiple_sentences():
    from app.models import Segment
    from app.segment import split_long_segments

    # The user's exact case: 3 sentences crammed into 1 segment
    raw_seg = Segment(
        index=1,
        start=31.34,
        end=35.58,
        text="Sebentar lagi ulang tahunmu. Biarkan aku memberimu hadiah. Bagaimana kamu tahu kalau rahasia ulang tahunku tidak boleh diungkapkan?",
    )

    split_segs = split_long_segments([raw_seg], lang="id")
    assert len(split_segs) == 3

    # Check timestamps: consecutive, non-overlapping, preserving bounds
    assert split_segs[0].start == 31.34
    assert split_segs[-1].end == 35.58
    for i in range(len(split_segs) - 1):
        assert split_segs[i].end <= split_segs[i + 1].start

    # Check text content
    assert "ulang tahunmu" in split_segs[0].text
    assert "memberimu hadiah" in split_segs[1].text
    assert "tidak boleh diungkapkan" in split_segs[2].text

    # None of the cues should have more than 2 lines, nor lines exceeding LATIN_MAX_CHARS_PER_LINE
    for s in split_segs:
        lines = s.text.split("\n")
        assert len(lines) <= 2
        for line in lines:
            assert len(line) <= 42


def test_split_long_segments_cjk():
    from app.models import Segment
    from app.segment import split_long_segments

    raw_seg = Segment(
        index=1,
        start=1.0,
        end=5.0,
        text="你快生日了吧。送你件礼物！天机不可泄露。",
    )
    split_segs = split_long_segments([raw_seg], lang="zh")
    assert len(split_segs) == 3
    assert split_segs[0].start == 1.0
    assert split_segs[-1].end == 5.0

