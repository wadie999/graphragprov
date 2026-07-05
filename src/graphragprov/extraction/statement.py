from dataclasses import dataclass
from typing import Any

from graphragprov.extraction.grounded_value import GroundedValue


@dataclass(frozen=True, slots=True)
class GroundedStatement:
    subject: GroundedValue
    predicate: GroundedValue
    object: GroundedValue

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject.to_dict(),
            "predicate": self.predicate.to_dict(),
            "object": self.object.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GroundedStatement":
        return cls(
            subject=GroundedValue.from_dict(data["subject"]),
            predicate=GroundedValue.from_dict(data["predicate"]),
            object=GroundedValue.from_dict(data["object"]),
        )
