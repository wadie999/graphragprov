from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from graphragprov.domain.source_unit import SourceUnit


class TextSegment(StrEnum):
    TITLE = "title"
    TEXT = "text"


@dataclass(frozen=True, slots=True)
class TextSpan:
    """Start-inclusive, end-exclusive character offsets."""

    segment: TextSegment
    start: int
    end: int
    quote: str

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("span start must be greater than or equal to zero")

        if self.end <= self.start:
            raise ValueError("span end must be greater than span start")

    def validate_against(self, source: SourceUnit) -> None:
        content = source.title if self.segment is TextSegment.TITLE else source.text

        if self.end > len(content):
            raise ValueError(
                f"{self.segment} span [{self.start}:{self.end}] "
                f"exceeds segment length {len(content)}"
            )

        actual_quote = content[self.start : self.end]

        if actual_quote != self.quote:
            raise ValueError(
                f"{self.segment} span [{self.start}:{self.end}] "
                f"expected {actual_quote!r}, received {self.quote!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment": self.segment.value,
            "start": self.start,
            "end": self.end,
            "quote": self.quote,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TextSpan":
        return cls(
            segment=TextSegment(data["segment"]),
            start=data["start"],
            end=data["end"],
            quote=data["quote"],
        )
