"""Benchmark reference resources."""

from pydantic import BaseModel


class ReasoningStep(BaseModel):
    step_id: str
    question: str | None = None
    answer: str | None = None
    subject: str | None = None
    relation: str | None = None
    object: str | None = None
    source_index: int | None = None


class BenchmarkRecord(BaseModel):
    case_id: str
    benchmark: str
    question: str
    expected_answers: tuple[str, ...]
    hop_count: int
    answerable: bool | None
    reasoning_steps: tuple[ReasoningStep, ...]
    support_source_ids: tuple[str, ...]
    metadata: dict[str, object]
