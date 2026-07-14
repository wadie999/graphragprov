from unittest.mock import patch

import pytest

from graphragprov.domain import SourceUnit
from graphragprov.hashing import source_unit_id
from graphragprov.provenance import SourceRegistry
from graphragprov.rdf.provenance import compact_unit_id


def make_source(
    *,
    title: str = "Albert Einstein",
    text: str = "He was born in Ulm.",
) -> SourceUnit:
    return SourceUnit(
        unit_id=source_unit_id(title=title, text=text),
        title=title,
        text=text,
    )


def test_registers_and_resolves_source_unit() -> None:
    source = make_source()
    registry = SourceRegistry((source,))

    assert registry.resolve(compact_unit_id(source.unit_id)) == source
    assert len(registry) == 1


def test_exact_source_can_be_registered_idempotently() -> None:
    source = make_source()
    registry = SourceRegistry()

    registry.register(source)
    registry.register(source)

    assert len(registry) == 1


def test_rejects_malformed_full_unit_id() -> None:
    source = SourceUnit(
        unit_id="u_invalid",
        title="Albert Einstein",
        text="He was born in Ulm.",
    )

    with pytest.raises(ValueError, match="full 64-character"):
        SourceRegistry((source,))


def test_rejects_unit_id_inconsistent_with_content() -> None:
    source = make_source()
    inconsistent = SourceUnit(
        unit_id=source.unit_id,
        title=source.title,
        text="Different text.",
    )

    with pytest.raises(ValueError, match="does not match"):
        SourceRegistry((inconsistent,))


def test_rejects_compact_identifier_collision() -> None:
    first = make_source(
        title="First",
        text="First text.",
    )
    second = make_source(
        title="Second",
        text="Second text.",
    )

    with patch(
        "graphragprov.provenance.registry.compact_unit_id",
        return_value="u_0000000000000000",
    ):
        registry = SourceRegistry((first,))

        with pytest.raises(ValueError, match="collision"):
            registry.register(second)


def test_rejects_malformed_compact_identifier() -> None:
    registry = SourceRegistry()

    with pytest.raises(ValueError, match="16 lowercase hexadecimal"):
        registry.resolve("u_invalid")


def test_rejects_unknown_compact_identifier() -> None:
    registry = SourceRegistry()

    with pytest.raises(KeyError, match="unknown compact"):
        registry.resolve("u_0000000000000000")
