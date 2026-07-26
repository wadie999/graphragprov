from dataclasses import dataclass
from typing import Any

from graphragprov.extraction.span import TextSpan


@dataclass(frozen=True, slots=True)
class GroundedValue:
    value: str
    evidence: tuple[TextSpan, ...]

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("grounded value must not be empty")

        if not self.evidence:
            raise ValueError("grounded value must contain evidence")

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "evidence": [span.to_dict() for span in self.evidence]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GroundedValue":
        return cls(
            value=data["value"],
            evidence=tuple(TextSpan.from_dict(span) for span in data["evidence"]),
        )
