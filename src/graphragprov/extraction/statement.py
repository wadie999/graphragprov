from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

from graphragprov.extraction.grounded_value import GroundedValue


class LiteralDatatype(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    YEAR = "year"
    YEAR_MONTH = "yearMonth"
    DATE = "date"
    DATE_TIME = "dateTime"


@dataclass(frozen=True, slots=True)
class GroundedStatement:
    subject: GroundedValue
    predicate: GroundedValue
    object: GroundedValue
    object_datatype: LiteralDatatype | None = None

    @property
    def object_is_literal(self) -> bool:
        return self.object_datatype is not None

    def to_dict(self) -> dict[str, Any]:
        object_data = self.object.to_dict()

        if self.object_datatype is not None:
            object_data["datatype"] = self.object_datatype.value

        return {
            "subject": self.subject.to_dict(),
            "predicate": self.predicate.to_dict(),
            "object": object_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GroundedStatement":
        subject_data = cast(dict[str, Any], data["subject"])
        predicate_data = cast(dict[str, Any], data["predicate"])
        object_data = cast(dict[str, Any], data["object"])

        raw_datatype = object_data.get("datatype")
        object_datatype: LiteralDatatype | None = None

        if raw_datatype is not None:
            if not isinstance(raw_datatype, str):
                raise ValueError("object datatype must be a string")

            object_datatype = LiteralDatatype(raw_datatype)

        return cls(
            subject=GroundedValue.from_dict(subject_data),
            predicate=GroundedValue.from_dict(predicate_data),
            object=GroundedValue.from_dict(object_data),
            object_datatype=object_datatype,
        )
