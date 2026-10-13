from collections.abc import Callable
from typing import Protocol

from app.models import Segment


class Translator(Protocol):
    async def translate(
        self,
        segments: list[Segment],
        source: str,
        target: str,
        glossary: dict[str, str] | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> list[Segment]:
        """
        Translates a list of Segments into the target language.
        Must return exactly the same number of Segments with identical timestamps and indices.
        """
        ...
