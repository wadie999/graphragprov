"""Resolution of compact provenance source identifiers."""

from __future__ import annotations

import re
from collections.abc import Iterable

from graphragprov.domain import SourceUnit
from graphragprov.hashing import source_unit_id, validate_source_unit_id
from graphragprov.rdf.provenance import compact_unit_id

_COMPACT_UNIT_ID_PATTERN = re.compile(r"u_[0-9a-f]{16}")


class SourceRegistry:
    """Map compact provenance identifiers to validated source units."""

    def __init__(self, sources: Iterable[SourceUnit] = ()) -> None:
        self._sources: dict[str, SourceUnit] = {}

        for source in sources:
            self.register(source)

    def register(self, source: SourceUnit) -> None:
        """Register one content-addressed source unit."""

        validate_source_unit_id(source.unit_id)

        expected_unit_id = source_unit_id(
            title=source.title,
            text=source.text,
        )

        if source.unit_id != expected_unit_id:
            raise ValueError("source unit ID does not match its exact title and text")

        compact_id = compact_unit_id(source.unit_id)
        existing = self._sources.get(compact_id)

        if existing is None:
            self._sources[compact_id] = source
            return

        if existing != source:
            raise ValueError(f"compact source-unit ID collision for {compact_id}")

    def resolve(self, compact_id: str) -> SourceUnit:
        """Return the unique source unit identified by a compact ID."""

        if _COMPACT_UNIT_ID_PATTERN.fullmatch(compact_id) is None:
            raise ValueError(
                "compact unit ID must contain 'u_' followed by 16 lowercase hexadecimal characters"
            )

        try:
            return self._sources[compact_id]
        except KeyError:
            raise KeyError(f"unknown compact source-unit ID: {compact_id}") from None

    def __len__(self) -> int:
        return len(self._sources)
