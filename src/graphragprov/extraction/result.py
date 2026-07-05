import json
from dataclasses import dataclass
from typing import Any, cast

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.grounded_value import GroundedValue
from graphragprov.extraction.statement import GroundedStatement


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    unit_id: str
    statements: tuple[GroundedStatement, ...]

    def validate_against(self, source: SourceUnit) -> None:
        if self.unit_id != source.unit_id:
            raise ValueError(
                f"extraction unit ID {self.unit_id!r} "
                f"does not match source unit ID {source.unit_id!r}"
            )

        for statement_index, statement in enumerate(self.statements):
            self._validate_value(
                statement.subject,
                source,
                f"statements[{statement_index}].subject",
            )
            self._validate_value(
                statement.predicate,
                source,
                f"statements[{statement_index}].predicate",
            )
            self._validate_value(
                statement.object,
                source,
                f"statements[{statement_index}].object",
            )

    @staticmethod
    def _validate_value(
        grounded_value: GroundedValue,
        source: SourceUnit,
        location: str,
    ) -> None:
        for evidence_index, span in enumerate(grounded_value.evidence):
            try:
                span.validate_against(source)
            except ValueError as error:
                raise ValueError(f"{location}.evidence[{evidence_index}]: {error}") from error

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "statements": [statement.to_dict() for statement in self.statements],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExtractionResult":
        return cls(
            unit_id=data["unit_id"],
            statements=tuple(
                GroundedStatement.from_dict(statement) for statement in data["statements"]
            ),
        )

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2,
        )

    @classmethod
    def from_json(cls, payload: str) -> "ExtractionResult":
        data = json.loads(payload)

        if not isinstance(data, dict):
            raise ValueError("extraction JSON must contain an object")

        return cls.from_dict(cast(dict[str, Any], data))
