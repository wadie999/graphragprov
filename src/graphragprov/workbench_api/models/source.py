"""Source and grounding resources."""

from typing import Literal

from pydantic import BaseModel


class EvidenceSpan(BaseModel):
    segment: Literal["title", "text"]
    start: int
    end: int
    quote: str
    role: Literal["subject", "predicate", "object"]


class SourceUnitView(BaseModel):
    source_id: str
    ordinal: int
    paragraph_index: int | None
    title: str
    text: str
    statement_count: int
    extraction_prompt: str | None = None
    extraction_response: str | None = None
