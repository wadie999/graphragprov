"""Tests for offline RDF artifact transformations."""

from __future__ import annotations

import json
from pathlib import Path

from graphragprov.cli.main import main
from graphragprov.domain import SourceUnit
from graphragprov.extraction import (
    ExtractionResult,
    GroundedStatement,
    GroundedValue,
    TextSegment,
    TextSpan,
)
from graphragprov.hashing import source_unit_id
from graphragprov.rdf import serialize_extraction_trig_star


def _value(value: str, *, segment: TextSegment, start: int, end: int, quote: str) -> GroundedValue:
    return GroundedValue(
        value=value, evidence=(TextSpan(segment=segment, start=start, end=end, quote=quote),)
    )


def _run_payload(source: SourceUnit, extraction: ExtractionResult) -> dict[str, object]:
    return {
        "source": {"unit_id": source.unit_id, "title": source.title, "text": source.text},
        "extraction": extraction.to_dict(),
    }


def test_export_run_reconstructs_combined_trig_star_from_persisted_extractions(
    tmp_path: Path,
) -> None:
    album = SourceUnit(
        unit_id=source_unit_id(
            title="Album Alpha", text="Album Alpha was performed by Artist Beta."
        ),
        title="Album Alpha",
        text="Album Alpha was performed by Artist Beta.",
    )
    album_extraction = ExtractionResult(
        unit_id=album.unit_id,
        statements=(
            GroundedStatement(
                subject=_value(
                    "Album Alpha", segment=TextSegment.TITLE, start=0, end=11, quote="Album Alpha"
                ),
                predicate=_value(
                    "performer", segment=TextSegment.TEXT, start=16, end=28, quote="performed by"
                ),
                object=_value(
                    "Artist Beta", segment=TextSegment.TEXT, start=29, end=40, quote="Artist Beta"
                ),
            ),
        ),
    )

    artist = SourceUnit(
        unit_id=source_unit_id(title="Artist Beta", text="Artist Beta was born in City Gamma."),
        title="Artist Beta",
        text="Artist Beta was born in City Gamma.",
    )
    artist_extraction = ExtractionResult(
        unit_id=artist.unit_id,
        statements=(
            GroundedStatement(
                subject=_value(
                    "Artist Beta", segment=TextSegment.TITLE, start=0, end=11, quote="Artist Beta"
                ),
                predicate=_value(
                    "placeOfBirth", segment=TextSegment.TEXT, start=16, end=23, quote="born in"
                ),
                object=_value(
                    "City Gamma", segment=TextSegment.TEXT, start=24, end=34, quote="City Gamma"
                ),
            ),
        ),
    )

    case_directory = tmp_path / "case-a"
    support_directory = case_directory / "support"
    support_directory.mkdir(parents=True)

    result_path = support_directory / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "status": "success",
                "graph_extractions": {
                    "items": [
                        {"run": _run_payload(album, album_extraction)},
                        {"run": _run_payload(artist, artist_extraction)},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(("rdf", "export-run", str(case_directory)))

    assert exit_code == 0

    graph_path = support_directory / "graph.trig"

    assert graph_path.read_text(encoding="utf-8") == (
        serialize_extraction_trig_star(album, album_extraction)
        + "\n"
        + serialize_extraction_trig_star(artist, artist_extraction)
    )
