import asyncio
import logging
from collections.abc import Callable

import httpx

from app.models import Segment
from app.segment import split_long_segments, wrap_lines

logger = logging.getLogger(__name__)


class GoogleTranslator:
    """
    Free Google Translate client using the public translation API.
    Does not require an API key.
    Translates subtitle segments preserving index, start, and end timestamps.
    """

    def __init__(self, timeout: float = 15.0, concurrency: int = 5):
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(concurrency)

    async def translate_text(self, text: str, source: str, target: str) -> str:
        clean = text.strip()
        if not clean:
            return text

        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": source if source != "auto" else "auto",
            "tl": target,
            "dt": "t",
            "q": clean,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                translated_parts = [
                    part[0] for part in data[0] if part and len(part) > 0 and part[0]
                ]
                return "".join(translated_parts).strip()
            return clean

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

        total = len(segments)
        completed = 0
        is_target_cjk = target == "zh"
        result_segments: list[Segment] = [None] * total  # type: ignore

        async def translate_single(index: int, seg: Segment) -> None:
            nonlocal completed
            async with self.semaphore:
                try:
                    text_to_translate = seg.text
                    if glossary:
                        for term, repl in glossary.items():
                            text_to_translate = text_to_translate.replace(term, repl)

                    translated = await self.translate_text(text_to_translate, source, target)
                    wrapped = wrap_lines(translated, is_cjk=is_target_cjk)
                    result_segments[index] = Segment(
                        index=seg.index,
                        start=seg.start,
                        end=seg.end,
                        text=wrapped,
                    )
                except Exception as err:
                    logger.warning(
                        "Gagal menerjemahkan segmen #%d (%s): %s. Menggunakan teks sumber.",
                        seg.index,
                        seg.text,
                        err,
                    )
                    result_segments[index] = Segment(
                        index=seg.index,
                        start=seg.start,
                        end=seg.end,
                        text=seg.text,
                    )
                finally:
                    completed += 1
                    if on_progress:
                        on_progress(completed / total)

        tasks = [translate_single(i, seg) for i, seg in enumerate(segments)]
        await asyncio.gather(*tasks)

        # Split any segments that translated into multiple sentences or exceed safe display length
        return split_long_segments(result_segments, lang=target)
