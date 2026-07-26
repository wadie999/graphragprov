"""Tests for durable MuSiQue source catalogs."""

from pathlib import Path

import pytest

from graphragprov.benchmarks.musique import MusiqueSourceUnit, MusiqueUnitOccurrence
from graphragprov.experiments import (
    MUSIQUE_SOURCE_CATALOG_FORMAT,
    MusiqueSourceCatalog,
    SourceOccurrenceNotFoundError,
    load_musique_source_catalog,
    write_musique_source_catalog,
)
from graphragprov.hashing import source_unit_id


def test_source_catalog_round_trip_preserves_occurrences() -> None:
    catalog = _catalog()

    restored = MusiqueSourceCatalog.from_json(catalog.to_json())

    assert restored == catalog
    assert restored.occurrence_count == 2
    assert restored.to_dict()["format"] == (MUSIQUE_SOURCE_CATALOG_FORMAT)


def test_source_catalog_resolves_occurrence() -> None:
    catalog = _catalog()

    source = catalog.get_source_for_occurrence(case_id="case-2", paragraph_index=7)

    assert source.title == "Shared source"
    assert source.text == ("The same paragraph occurs in two cases.")


def test_source_catalog_reports_missing_occurrence() -> None:
    catalog = _catalog()

    with pytest.raises(
        SourceOccurrenceNotFoundError, match="source catalog has no occurrence case-3:0"
    ):
        catalog.get_source_for_occurrence(case_id="case-3", paragraph_index=0)


def test_source_catalog_rejects_duplicate_occurrence() -> None:
    occurrence = MusiqueUnitOccurrence(case_id="case-1", paragraph_index=3, is_supporting=True)

    first = _source(title="First", text="First source.", occurrences=(occurrence,))
    second = _source(title="Second", text="Second source.", occurrences=(occurrence,))

    with pytest.raises(ValueError, match="duplicate MuSiQue paragraph occurrence"):
        MusiqueSourceCatalog(sources=(first, second))


def test_source_catalog_rejects_tampered_identity() -> None:
    source = MusiqueSourceUnit(
        unit_id="u_" + ("0" * 64),
        title="Title",
        text="Text",
        occurrences=(
            MusiqueUnitOccurrence(case_id="case-1", paragraph_index=0, is_supporting=False),
        ),
    )

    with pytest.raises(ValueError, match="source-unit ID does not match source content"):
        MusiqueSourceCatalog(sources=(source,))


def test_source_catalog_file_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "source-units.json"
    catalog = _catalog()

    write_musique_source_catalog(path, catalog)

    assert load_musique_source_catalog(path) == catalog
    assert path.read_text(encoding="utf-8").endswith("\n")


def _catalog() -> MusiqueSourceCatalog:
    source = _source(
        title="Shared source",
        text="The same paragraph occurs in two cases.",
        occurrences=(
            MusiqueUnitOccurrence(case_id="case-1", paragraph_index=3, is_supporting=True),
            MusiqueUnitOccurrence(case_id="case-2", paragraph_index=7, is_supporting=False),
        ),
    )

    return MusiqueSourceCatalog(sources=(source,))


def _source(
    *, title: str, text: str, occurrences: tuple[MusiqueUnitOccurrence, ...]
) -> MusiqueSourceUnit:
    return MusiqueSourceUnit(
        unit_id=source_unit_id(title=title, text=text),
        title=title,
        text=text,
        occurrences=occurrences,
    )
