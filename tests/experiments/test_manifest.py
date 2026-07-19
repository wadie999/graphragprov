"""Tests for the MuSiQue materialization experiment contract."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from graphragprov.benchmarks.musique import (
    MusiqueCase,
    MusiqueHop,
    MusiqueParagraph,
)
from graphragprov.domain import SourceUnit
from graphragprov.experiments import (
    MUSIQUE_MATERIALIZATION_FORMAT,
    MusiqueMaterializationManifest,
    load_musique_materialization_manifest,
    write_musique_materialization_manifest,
)
from graphragprov.extraction import (
    ExtractionResult,
    GroundedExtractionBatchItem,
    GroundedExtractionBatchResult,
)
from graphragprov.extraction.prompt import build_extraction_prompt
from graphragprov.extraction.run import GroundedExtractionRun
from graphragprov.graphdb import (
    GraphDBClient,
    GraphMaterializationSummary,
)
from graphragprov.rdf import unit_graph_iri


def test_manifest_is_built_from_existing_application_results() -> None:
    manifest = _manifest()

    assert manifest.to_dict() == {
        "format": MUSIQUE_MATERIALIZATION_FORMAT,
        "status": "complete",
        "created_at": "2026-07-18T16:07:40+00:00",
        "dataset_path": "/datasets/musique.jsonl",
        "prompt_version": "grounded-rdf-v2",
        "model": "test-model",
        "max_tokens": 4096,
        "cache_root": "runs/test/extractions",
        "graphdb": {
            "base_url": "http://localhost:7200",
            "repository": "test-repository",
            "statements_before_run": 0,
        },
        "cases": [
            {
                "case_id": "case-1",
                "hop_count": 1,
                "question": "Where was the person born?",
                "answer": "Toulouse",
                "answer_aliases": [],
                "answerable": True,
                "paragraph_indices": [0],
                "gold_support_indices": [0],
            }
        ],
        "paragraph_occurrence_count": 1,
        "requested_source_count": 1,
        "successful_extraction_count": 1,
        "failed_extraction_count": 0,
        "new_outcome_count": 1,
        "reused_outcome_count": 0,
        "source_unit_ids": ["u_c0a6b304b29f5aca50037fd196b85c825bacb4d708496bd0cda55d2b8ab70766"],
        "failures": [],
        "materialization": {
            "source_count": 1,
            "statement_count": 0,
            "graph_iris": ["urn:graphragprov:unit:u_c0a6b304b29f5aca"],
        },
    }

def test_manifest_json_round_trip_preserves_contract() -> None:
    manifest = _manifest()

    restored = MusiqueMaterializationManifest.from_json(manifest.to_json())

    assert restored == manifest
    assert restored.to_dict() == manifest.to_dict()


def test_manifest_file_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "materialization.json"
    manifest = _manifest()

    write_musique_materialization_manifest(path, manifest)

    assert load_musique_materialization_manifest(path) == manifest
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_manifest_rejects_inconsistent_counts() -> None:
    payload = _manifest().to_dict()
    payload["successful_extraction_count"] = 0

    with pytest.raises(
        ValueError,
        match="extraction counts are inconsistent",
    ):
        MusiqueMaterializationManifest.from_json(json.dumps(payload))


def test_manifest_rejects_unknown_format() -> None:
    payload = _manifest().to_dict()
    payload["format"] = "unknown-format"

    with pytest.raises(
        ValueError,
        match="unsupported materialization manifest format",
    ):
        MusiqueMaterializationManifest.from_json(json.dumps(payload))


def _manifest() -> MusiqueMaterializationManifest:
    paragraph = MusiqueParagraph(
        index=0,
        title="Person",
        text="The person was born in Toulouse.",
    )

    case = MusiqueCase(
        case_id="case-1",
        question="Where was the person born?",
        answer="Toulouse",
        answer_aliases=(),
        answerable=True,
        paragraphs=(paragraph,),
        decomposition=(
            MusiqueHop(
                hop_id=0,
                question="Where was the person born?",
                answer="Toulouse",
                paragraph_support_index=0,
            ),
        ),
        gold_support_indices=(0,),
    )

    source = SourceUnit(
        unit_id=paragraph.unit_id,
        title=paragraph.title,
        text=paragraph.text,
    )

    run = GroundedExtractionRun(
        source=source,
        prompt=build_extraction_prompt(source),
        response='{"statements":[]}',
        extraction=ExtractionResult(
            unit_id=source.unit_id,
            statements=(),
        ),
    )

    batch = GroundedExtractionBatchResult(
        items=(
            GroundedExtractionBatchItem(
                outcome=run,
                reused=False,
            ),
        )
    )

    materialization = GraphMaterializationSummary(
        source_count=1,
        statement_count=0,
        graph_iris=(str(unit_graph_iri(source.unit_id)),),
    )

    return MusiqueMaterializationManifest.from_execution(
        dataset_path=Path("/datasets/musique.jsonl"),
        cases=(case,),
        batch=batch,
        materialization=materialization,
        prompt_version="grounded-rdf-v2",
        model="test-model",
        max_tokens=4096,
        cache_root=Path("runs/test/extractions"),
        graphdb=GraphDBClient(
            base_url="http://localhost:7200",
            repository="test-repository",
        ),
        existing_statement_count=0,
        created_at=datetime(
            2026,
            7,
            18,
            16,
            7,
            40,
            tzinfo=UTC,
        ),
    )
