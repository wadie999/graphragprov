import json

import pytest

from graphragprov.domain import SourceUnit
from graphragprov.extraction.run import GroundedExtractionRun, run_grounded_extraction
from graphragprov.graphdb import GraphMaterializationSummary, materialize_grounded_extractions
from graphragprov.hashing import source_unit_id
from graphragprov.rdf.star import serialize_extraction_trig_star
from graphragprov.rdf.terms import unit_graph_iri


class RecordingUploader:
    """In-memory implementation of the upload contract."""

    def __init__(self) -> None:
        self.contents: list[str | bytes] = []

    def upload_trig_star(self, content: str | bytes) -> None:
        self.contents.append(content)


def make_source(*, title: str, text: str) -> SourceUnit:
    return SourceUnit(unit_id=source_unit_id(title=title, text=text), title=title, text=text)


FIRST_SOURCE = make_source(title="Albert Einstein", text="He was born in Ulm.")

SECOND_SOURCE = make_source(title="Marie Curie", text="She was born in Warsaw.")

FIRST_RESPONSE = json.dumps(
    {
        "statements": [
            {
                "subject": {
                    "value": "Albert Einstein",
                    "evidence": [
                        {"segment": "title", "quote": "Albert Einstein", "occurrence": 1},
                        {"segment": "text", "quote": "He", "occurrence": 1},
                    ],
                },
                "predicate": {
                    "value": "bornIn",
                    "evidence": [{"segment": "text", "quote": "born in", "occurrence": 1}],
                },
                "object": {
                    "value": "Ulm",
                    "evidence": [{"segment": "text", "quote": "Ulm", "occurrence": 1}],
                },
            }
        ]
    }
)

SECOND_RESPONSE = json.dumps(
    {
        "statements": [
            {
                "subject": {
                    "value": "Marie Curie",
                    "evidence": [
                        {"segment": "title", "quote": "Marie Curie", "occurrence": 1},
                        {"segment": "text", "quote": "She", "occurrence": 1},
                    ],
                },
                "predicate": {
                    "value": "bornIn",
                    "evidence": [{"segment": "text", "quote": "born in", "occurrence": 1}],
                },
                "object": {
                    "value": "Warsaw",
                    "evidence": [{"segment": "text", "quote": "Warsaw", "occurrence": 1}],
                },
            }
        ]
    }
)


def make_run(source: SourceUnit, response: str) -> GroundedExtractionRun:
    return run_grounded_extraction(source, generate_response=lambda _: response)


def test_serializes_and_uploads_each_source() -> None:
    first_run = make_run(FIRST_SOURCE, FIRST_RESPONSE)
    second_run = make_run(SECOND_SOURCE, SECOND_RESPONSE)
    uploader = RecordingUploader()

    summary = materialize_grounded_extractions((first_run, second_run), graphdb=uploader)

    assert uploader.contents == [
        serialize_extraction_trig_star(first_run.source, first_run.extraction),
        serialize_extraction_trig_star(second_run.source, second_run.extraction),
    ]

    assert summary == GraphMaterializationSummary(
        source_count=2,
        statement_count=2,
        graph_iris=(
            str(unit_graph_iri(FIRST_SOURCE.unit_id)),
            str(unit_graph_iri(SECOND_SOURCE.unit_id)),
        ),
    )


def test_deduplicates_identical_runs() -> None:
    run = make_run(FIRST_SOURCE, FIRST_RESPONSE)
    uploader = RecordingUploader()

    summary = materialize_grounded_extractions((run, run, run), graphdb=uploader)

    assert len(uploader.contents) == 1
    assert summary.source_count == 1
    assert summary.statement_count == 1


def test_rejects_conflicting_extractions() -> None:
    first_run = make_run(FIRST_SOURCE, FIRST_RESPONSE)
    empty_run = make_run(FIRST_SOURCE, '{"statements": []}')

    with pytest.raises(ValueError, match="conflicting grounded extractions"):
        materialize_grounded_extractions((first_run, empty_run), graphdb=RecordingUploader())


def test_rejects_same_id_with_different_source_content() -> None:
    first_run = make_run(FIRST_SOURCE, FIRST_RESPONSE)

    inconsistent_source = SourceUnit(
        unit_id=FIRST_SOURCE.unit_id, title=FIRST_SOURCE.title, text="Different source text."
    )

    inconsistent_run = GroundedExtractionRun(
        source=inconsistent_source,
        prompt=first_run.prompt,
        response=first_run.response,
        extraction=first_run.extraction,
    )

    with pytest.raises(ValueError, match="different source content"):
        materialize_grounded_extractions((first_run, inconsistent_run), graphdb=RecordingUploader())


def test_accepts_empty_materialization() -> None:
    uploader = RecordingUploader()

    summary = materialize_grounded_extractions((), graphdb=uploader)

    assert uploader.contents == []
    assert summary == GraphMaterializationSummary(source_count=0, statement_count=0, graph_iris=())


def test_summary_is_json_serializable() -> None:
    run = make_run(FIRST_SOURCE, FIRST_RESPONSE)

    summary = materialize_grounded_extractions((run,), graphdb=RecordingUploader())

    serialized = json.dumps(summary.to_dict(), sort_keys=True)

    assert json.loads(serialized) == {
        "source_count": 1,
        "statement_count": 1,
        "graph_iris": [str(unit_graph_iri(FIRST_SOURCE.unit_id))],
    }
