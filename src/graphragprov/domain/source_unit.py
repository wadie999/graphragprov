from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceUnit:
    """Exact source content presented to an extractor."""

    unit_id: str
    title: str
    text: str
