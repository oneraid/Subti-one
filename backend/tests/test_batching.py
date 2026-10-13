from app.models import Segment
from app.translate.batching import (
    clean_json_response,
    create_translation_batches,
    format_system_prompt,
    validate_batch_output,
)


def test_create_batches_empty():
    assert create_translation_batches([]) == []


def test_create_batches_limit_cues():
    # 50 segments, batch_size=20 -> should produce 3 batches (20, 20, 10)
    segs = [
        Segment(index=i, start=float(i), end=float(i + 1), text=f"Sentence {i}")
        for i in range(1, 51)
    ]
    batches = create_translation_batches(segs, batch_size=20)
    assert len(batches) == 3
    assert len(batches[0].items) == 20
    assert len(batches[1].items) == 20
    assert len(batches[2].items) == 10

    # Context before on batch 0 should be empty
    assert batches[0].context_before == []
    # Context after on batch 0 should contain up to 5 cues
    assert len(batches[0].context_after) == 5
    # Context before on batch 1 should contain 5 cues
    assert len(batches[1].context_before) == 5
    # Context after on batch 2 should be empty
    assert batches[2].context_after == []


def test_create_batches_limit_chars():
    # 3 segments with 50 chars each, max_chars=80 -> each batch should have 1 segment
    segs = [
        Segment(index=1, start=0.0, end=1.0, text="A" * 50),
        Segment(index=2, start=1.0, end=2.0, text="B" * 50),
        Segment(index=3, start=2.0, end=3.0, text="C" * 50),
    ]
    batches = create_translation_batches(segs, max_chars=80)
    assert len(batches) == 3


def test_validate_batch_output_success():
    inputs = [{"id": 1, "text": "Hello"}, {"id": 2, "text": "World"}]
    outputs = [{"id": 1, "text": "Halo"}, {"id": 2, "text": "Dunia"}]
    valid, err = validate_batch_output(inputs, outputs)
    assert valid is True
    assert err is None


def test_validate_batch_output_id_mismatch():
    inputs = [{"id": 1, "text": "Hello"}, {"id": 2, "text": "World"}]
    outputs = [{"id": 1, "text": "Halo"}, {"id": 3, "text": "Dunia"}]
    valid, err = validate_batch_output(inputs, outputs)
    assert valid is False
    assert "ID tidak cocok" in str(err)


def test_validate_batch_output_empty_text():
    inputs = [{"id": 1, "text": "Hello"}]
    outputs = [{"id": 1, "text": "   "}]
    valid, err = validate_batch_output(inputs, outputs)
    assert valid is False
    assert "kosong" in str(err)


def test_validate_batch_output_not_list():
    inputs = [{"id": 1, "text": "Hello"}]
    outputs = {"id": 1, "text": "Halo"}  # type: ignore
    valid, err = validate_batch_output(inputs, outputs)
    assert valid is False


def test_clean_json_response():
    # Plain JSON
    raw = '{"items": [{"id": 1, "text": "Halo"}]}'
    assert clean_json_response(raw)["items"][0]["text"] == "Halo"

    # Markdown fenced code block
    fenced = '```json\n{"items": [{"id": 1, "text": "Halo"}]}\n```'
    assert clean_json_response(fenced)["items"][0]["text"] == "Halo"

    # Code block without json tag
    fenced2 = 'Here is the result:\n```\n{"items": [{"id": 2, "text": "Dunia"}]}\n```'
    assert clean_json_response(fenced2)["items"][0]["text"] == "Dunia"


def test_format_system_prompt():
    prompt = format_system_prompt("en", "id")
    assert "Inggris" in prompt
    assert "Indonesia" in prompt
    assert "submit_translated_subtitles" not in prompt  # tools are separate
