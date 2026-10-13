import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from anthropic import AsyncAnthropic

from app.config import settings
from app.models import Segment
from app.segment import split_long_segments, wrap_lines
from app.translate.batching import (
    TranslationBatch,
    clean_json_response,
    create_translation_batches,
    format_system_prompt,
    validate_batch_output,
)

logger = logging.getLogger(__name__)

TRANSLATE_TOOL_SCHEMA: dict[str, Any] = {
    "name": "submit_translated_subtitles",
    "description": "Submit translated subtitle items matching the input IDs",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "The exact ID from input item"},
                        "text": {"type": "string", "description": "The translated subtitle text"},
                    },
                    "required": ["id", "text"],
                },
            }
        },
        "required": ["items"],
    },
}


class ClaudeTranslator:
    def __init__(self, client: AsyncAnthropic | None = None, model: str | None = None):
        self.client = client
        self.model = model or settings.anthropic_model
        self.semaphore = asyncio.Semaphore(3)  # Max 3 concurrent batches

    def _get_client(self) -> AsyncAnthropic:
        if not self.client:
            api_key = settings.anthropic_api_key
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY tidak dikonfigurasi di file .env")
            self.client = AsyncAnthropic(api_key=api_key)
        return self.client

    async def translate(
        self,
        segments: list[Segment],
        source: str,
        target: str,
        glossary: dict[str, str] | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> list[Segment]:
        if not segments or source == target:
            return segments

        batches = create_translation_batches(segments)
        total_batches = len(batches)
        completed_batches = 0

        translated_items_by_id: dict[int, str] = {}
        is_target_cjk = target == "zh"

        async def process_single_batch(batch: TranslationBatch) -> None:
            nonlocal completed_batches
            async with self.semaphore:
                items_result = await self._translate_batch_with_retry_and_split(
                    batch=batch,
                    source=source,
                    target=target,
                    glossary=glossary,
                )
                for item in items_result:
                    # Enforce max lines / length wrapping
                    wrapped = wrap_lines(item["text"], is_cjk=is_target_cjk)
                    translated_items_by_id[item["id"]] = wrapped

                completed_batches += 1
                if on_progress and total_batches > 0:
                    on_progress(completed_batches / total_batches)

        # Run batches in parallel (concurrency managed by semaphore)
        tasks = [process_single_batch(b) for b in batches]
        await asyncio.gather(*tasks)

        # Assemble final segments preserving exact order, timestamps, and indexes
        result_segments: list[Segment] = []
        for seg in segments:
            translated_text = translated_items_by_id.get(seg.index, seg.text)
            result_segments.append(
                Segment(
                    index=seg.index,
                    start=seg.start,
                    end=seg.end,
                    text=translated_text,
                )
            )

        return split_long_segments(result_segments, lang=target)

    async def _translate_batch_with_retry_and_split(
        self,
        batch: TranslationBatch,
        source: str,
        target: str,
        glossary: dict[str, str] | None,
        attempt: int = 1,
    ) -> list[dict[str, Any]]:
        client = self._get_client()
        system_prompt = format_system_prompt(source, target)

        user_content: dict[str, Any] = {
            "items": batch.items,
        }
        if batch.context_before:
            user_content["context_before"] = batch.context_before
        if batch.context_after:
            user_content["context_after"] = batch.context_after
        if glossary:
            user_content["glossary"] = glossary

        user_message = json.dumps(user_content, ensure_ascii=False)

        # Try API call with exponential backoff
        for retry in range(3):
            try:
                response = await client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    temperature=0.2,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                    tools=[TRANSLATE_TOOL_SCHEMA],
                    tool_choice={"type": "tool", "name": "submit_translated_subtitles"},
                    timeout=60.0,
                )

                output_items: list[dict[str, Any]] | None = None
                for block in response.content:
                    if (
                        getattr(block, "type", "") == "tool_use"
                        and getattr(block, "name", "") == "submit_translated_subtitles"
                    ):
                        input_data = getattr(block, "input", {})
                        output_items = input_data.get("items")
                        break
                    elif hasattr(block, "text") and block.text:
                        parsed = clean_json_response(block.text)
                        output_items = parsed.get("items")
                        break

                if output_items:
                    is_valid, err_msg = validate_batch_output(batch.items, output_items)
                    if is_valid:
                        return output_items
                    logger.warning(
                        "Batch %d validation failed: %s (retry %d)", batch.batch_idx, err_msg, retry
                    )

            except Exception as err:
                logger.warning(
                    "Batch %d API call failed: %s (retry %d)", batch.batch_idx, err, retry
                )

            await asyncio.sleep(2**retry)

        # If retries failed and batch has more than 1 item -> Split batch in two
        if len(batch.items) > 1:
            mid = len(batch.items) // 2
            sub_batch_1 = TranslationBatch(
                batch_idx=batch.batch_idx * 10 + 1,
                items=batch.items[:mid],
                context_before=batch.context_before,
                context_after=[item["text"] for item in batch.items[mid:]],
            )
            sub_batch_2 = TranslationBatch(
                batch_idx=batch.batch_idx * 10 + 2,
                items=batch.items[mid:],
                context_before=[item["text"] for item in batch.items[:mid]],
                context_after=batch.context_after,
            )

            res1 = await self._translate_batch_with_retry_and_split(
                sub_batch_1, source, target, glossary, attempt=attempt + 1
            )
            res2 = await self._translate_batch_with_retry_and_split(
                sub_batch_2, source, target, glossary, attempt=attempt + 1
            )
            return res1 + res2

        # 1-item batch that still failed: fallback to source text
        logger.error(
            "Batch %d item %s completely failed to translate, falling back to source",
            batch.batch_idx,
            batch.items,
        )
        return [{"id": item["id"], "text": item["text"]} for item in batch.items]


class FakeTranslator:
    """Mock Translator for unit testing."""

    def __init__(self, mapping: dict[str, str] | None = None):
        self.mapping = mapping or {
            "Halo": "Hello",
            "dunia.": "world.",
            "AutoSub.": "AutoSub.",
            "Selamat pagi": "Good morning",
        }

    async def translate(
        self,
        segments: list[Segment],
        source: str,
        target: str,
        glossary: dict[str, str] | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> list[Segment]:
        if on_progress:
            on_progress(0.5)
            on_progress(1.0)

        result: list[Segment] = []
        for s in segments:
            # Simple translated string
            trans_words = [self.mapping.get(w, f"[{w}]") for w in s.text.split()]
            text = " ".join(trans_words)
            result.append(
                Segment(
                    index=s.index,
                    start=s.start,
                    end=s.end,
                    text=text,
                )
            )
        return result
