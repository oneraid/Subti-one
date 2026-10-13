from app.models import Segment
from app.subtitle import (
    combine_bilingual_subtitles,
    format_timestamp_srt,
    format_timestamp_vtt,
    parse_timestamp,
    segments_to_srt,
    segments_to_vtt,
    srt_to_segments,
    vtt_to_segments,
)


def test_timestamp_formatting_and_parsing():
    assert format_timestamp_srt(0.0) == "00:00:00,000"
    assert format_timestamp_srt(65.123) == "00:01:05,123"
    assert format_timestamp_srt(3661.05) == "01:01:01,050"

    assert format_timestamp_vtt(0.0) == "00:00:00.000"
    assert format_timestamp_vtt(65.123) == "00:01:05.123"

    assert parse_timestamp("01:01:01,050") == 3661.05
    assert parse_timestamp("00:01:05.123") == 65.123
    assert parse_timestamp("05:10.500") == 310.5
    assert parse_timestamp("45.2") == 45.2


def test_empty_srt_and_vtt():
    assert srt_to_segments("") == []
    assert srt_to_segments("   \n\n  ") == []
    assert vtt_to_segments("") == []
    assert segments_to_srt([]) == ""


def test_srt_roundtrip():
    original = [
        Segment(index=1, start=0.5, end=2.0, text="Halo semuanya!\nSelamat datang."),
        Segment(index=2, start=2.5, end=5.2, text="Hari ini kita belajar auto subtitle."),
    ]
    srt_content = segments_to_srt(original)
    assert "00:00:00,500 --> 00:00:02,000" in srt_content
    assert "Halo semuanya!\nSelamat datang." in srt_content

    parsed = srt_to_segments(srt_content)
    assert len(parsed) == 2
    assert parsed[0].start == 0.5
    assert parsed[0].end == 2.0
    assert parsed[0].text == "Halo semuanya!\nSelamat datang."
    assert parsed[1].text == "Hari ini kita belajar auto subtitle."


def test_vtt_roundtrip():
    original = [
        Segment(index=1, start=1.0, end=3.5, text="Hello world"),
        Segment(index=2, start=4.0, end=6.0, text="This is WebVTT"),
    ]
    vtt_content = segments_to_vtt(original)
    assert "WEBVTT" in vtt_content
    assert "00:00:01.000 --> 00:00:03.500" in vtt_content

    parsed = vtt_to_segments(vtt_content)
    assert len(parsed) == 2
    assert parsed[0].text == "Hello world"
    assert parsed[1].text == "This is WebVTT"


def test_combine_bilingual():
    source = [
        Segment(index=1, start=1.0, end=3.0, text="Good morning"),
        Segment(index=2, start=3.5, end=5.0, text="How are you?"),
    ]
    target = [
        Segment(index=1, start=1.0, end=3.0, text="Selamat pagi"),
        Segment(index=2, start=3.5, end=5.0, text="Apa kabar?"),
    ]

    # Source first
    bilingual_src_first = combine_bilingual_subtitles(source, target, order="source_first")
    assert len(bilingual_src_first) == 2
    assert bilingual_src_first[0].text == "Good morning\nSelamat pagi"
    assert bilingual_src_first[1].text == "How are you?\nApa kabar?"

    # Target first
    bilingual_tgt_first = combine_bilingual_subtitles(source, target, order="target_first")
    assert bilingual_tgt_first[0].text == "Selamat pagi\nGood morning"


def test_combine_bilingual_differing_lengths():
    source = [
        Segment(index=1, start=1.0, end=3.0, text="Good morning"),
        Segment(index=2, start=3.5, end=5.0, text="How are you?"),
        Segment(index=3, start=6.0, end=7.0, text="See you later"),
    ]
    target = [
        Segment(index=1, start=1.0, end=3.0, text="Selamat pagi"),
        Segment(index=2, start=3.5, end=5.0, text="Apa kabar?"),
    ]

    bilingual = combine_bilingual_subtitles(source, target, order="source_first")
    assert len(bilingual) == 3
    assert "Selamat pagi" in bilingual[0].text
    assert "Apa kabar?" in bilingual[1].text
    assert bilingual[2].text == "See you later"

    # target first differing lengths
    bilingual_tf = combine_bilingual_subtitles(source, target, order="target_first")
    assert len(bilingual_tf) == 3
    assert bilingual_tf[0].text.startswith("Selamat pagi")
