import json
import re
from dataclasses import dataclass
from typing import Any

from app.languages import LANGUAGE_NAMES
from app.models import Segment

BATCH_CUE_LIMIT = 40
BATCH_CHAR_LIMIT = 3000
CONTEXT_SIZE = 5


@dataclass
class TranslationBatch:
    batch_idx: int
    items: list[dict[str, Any]]  # [{"id": int, "text": str}]
    context_before: list[str]
    context_after: list[str]


def create_translation_batches(
    segments: list[Segment],
    batch_size: int = BATCH_CUE_LIMIT,
    max_chars: int = BATCH_CHAR_LIMIT,
    context_size: int = CONTEXT_SIZE,
) -> list[TranslationBatch]:
    """
    Split subtitle segments into batches with context before and after.
    Respects batch_size cue count and max_chars limit.
    """
    if not segments:
        return []

    batches: list[TranslationBatch] = []
    current_items: list[dict[str, Any]] = []
    current_char_count = 0
    current_start_idx = 0

    for i, seg in enumerate(segments):
        item = {"id": seg.index, "text": seg.text}
        item_chars = len(seg.text)

        should_split = False
        if len(current_items) >= batch_size:
            should_split = True
        elif current_char_count + item_chars > max_chars and current_items:
            should_split = True

        if should_split:
            # Context before: up to context_size cues before current_start_idx
            ctx_before_start = max(0, current_start_idx - context_size)
            context_before = [
                s.text.replace("\n", " ") for s in segments[ctx_before_start:current_start_idx]
            ]

            # Context after: up to context_size cues after current batch
            ctx_after_end = min(len(segments), i + context_size)
            context_after = [s.text.replace("\n", " ") for s in segments[i:ctx_after_end]]

            batches.append(
                TranslationBatch(
                    batch_idx=len(batches),
                    items=list(current_items),
                    context_before=context_before,
                    context_after=context_after,
                )
            )

            current_items = [item]
            current_char_count = item_chars
            current_start_idx = i
        else:
            current_items.append(item)
            current_char_count += item_chars

    if current_items:
        ctx_before_start = max(0, current_start_idx - context_size)
        context_before = [
            s.text.replace("\n", " ") for s in segments[ctx_before_start:current_start_idx]
        ]
        context_after = []

        batches.append(
            TranslationBatch(
                batch_idx=len(batches),
                items=list(current_items),
                context_before=context_before,
                context_after=context_after,
            )
        )

    return batches


def validate_batch_output(
    input_items: list[dict[str, Any]],
    output_items: list[dict[str, Any]],
) -> tuple[bool, str | None]:
    """
    Validates translation output from LLM:
    1. Output is a list of items with 'id' and 'text'.
    2. Exact match between input IDs and output IDs.
    3. Output text is not empty when input text is not empty.
    """
    if not isinstance(output_items, list):
        return False, "Keluaran bukan list/daftar item"

    input_ids = {item["id"] for item in input_items}
    output_dict: dict[int, str] = {}

    for item in output_items:
        if not isinstance(item, dict) or "id" not in item or "text" not in item:
            return False, "Item keluaran tidak memiliki kunci 'id' dan 'text'"
        try:
            item_id = int(item["id"])
            output_dict[item_id] = str(item["text"])
        except (ValueError, TypeError):
            return False, f"ID item tidak valid: {item.get('id')}"

    output_ids = set(output_dict.keys())
    if input_ids != output_ids:
        missing = input_ids - output_ids
        extra = output_ids - input_ids
        return False, f"ID tidak cocok. Kurang: {missing}, Lebih: {extra}"

    for inp in input_items:
        inp_id = inp["id"]
        inp_text = str(inp.get("text", "")).strip()
        out_text = output_dict[inp_id].strip()
        if inp_text and not out_text:
            return False, f"Teks terjemahan kosong untuk id {inp_id}"

    return True, None


def clean_json_response(raw_text: str) -> dict[str, Any]:
    """Extract and parse JSON from LLM response string with markdown tolerance."""
    text = raw_text.strip()

    # Strip markdown code blocks
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if code_block_match:
        text = code_block_match.group(1).strip()

    # Sometimes LLM outputs raw JSON object { ... }
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        text = json_match.group(0)

    return json.loads(text)


def format_system_prompt(source: str, target: str) -> str:
    src_name = LANGUAGE_NAMES.get(source, source)
    tgt_name = LANGUAGE_NAMES.get(target, target)

    return f"""Kamu penerjemah subtitle profesional. Terjemahkan dari {src_name} ke {tgt_name}.
Aturan:
- Terjemahkan makna dan nada ujaran, bukan kata per kata;
  hasil harus terdengar alami seperti ucapan lisan.
- Satu item masukan menghasilkan tepat satu item keluaran dengan id yang sama.
  Jangan menggabung, memecah, menambah, atau menghapus item.
- Singkat dan padat: subtitle dibaca cepat. Hindari penjelasan.
- Pertahankan nama orang, merek, dan istilah teknis; ikuti glosarium bila ada.
- Pertahankan tanda baca penting dan "\\n" bila relevan; jangan menambahkan tag atau catatan.
- context_before/context_after hanya untuk memahami alur; JANGAN diterjemahkan.
- Bahasa Indonesia: baku-santai, natural (bukan kaku).
  Mandarin: gunakan nama dan istilah umum; jangan sertakan pinyin.
Keluarkan hanya JSON sesuai skema: {{"items": [{{"id": 1, "text": "..."}}]}}."""
