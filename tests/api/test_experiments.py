"""Tests for experiment and QA API resources."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from graphragprov.api import create_app
from graphragprov.api.dependencies import MusiqueQueryScope, QARunEventSink
from graphragprov.benchmarks.musique import MusiqueCase
from graphragprov.experiments import (
    ExperimentNotFoundError,
    MusiqueMaterializationManifest,
    StoredMusiqueExperiment,
    validate_experiment_id,
)
from graphragprov.provenance import SourceRegistry
from graphragprov.qaagent import QAAgentConfiguration, QAAgentDecision, QAAgentRunResult
from graphragprov.qaagent.trace import QAQueryAttempt
from graphragprov.query.execution import ProvenanceQueryExecution


@dataclass(frozen=True, slots=True)
class StubExperimentRepository:
    """In-memory repository used by HTTP contract tests."""

    experiments: tuple[StoredMusiqueExperiment, ...]

    def list_experiments(self) -> tuple[StoredMusiqueExperiment, ...]:
        return self.experiments

    def get_experiment(self, experiment_id: str) -> StoredMusiqueExperiment:
        validated_id = validate_experiment_id(experiment_id)

        for experiment in self.experiments:
            if experiment.experiment_id == validated_id:
                return experiment

        raise ExperimentNotFoundError(f"experiment does not exist: {validated_id}")


@dataclass(slots=True)
class StubQARunner:
    """Observable QA runner used by API tests."""

    emit_events: bool = False
    calls: list[dict[str, object]] = field(default_factory=list)

    def __call__(
        self,
        *,
        case: MusiqueCase,
        question: str | None = None,
        max_turns: int,
        query_scope: MusiqueQueryScope = ("case_graphs"),
        include_oracle_tuples: bool = False,
        model: str,
        max_tokens: int,
        provenance_registry: (SourceRegistry | None) = None,
        event_sink: (QARunEventSink | None) = None,
    ) -> QAAgentRunResult:
        self.calls.append(
            {
                "case_id": case.case_id,
                "question": question,
                "max_turns": max_turns,
                "query_scope": query_scope,
                "include_oracle_tuples": (include_oracle_tuples),
                "model": model,
                "max_tokens": max_tokens,
                "provenance_registry": (provenance_registry),
            }
        )

        if self.emit_events and event_sink is not None:
            event_sink(
                {
                    "type": ("turn.query_generated"),
                    "turn_index": 1,
                    "purpose": "inspection",
                    "semantic_sparql": ("SELECT ?entity WHERE { ?entity ?predicate ?object . }"),
                }
            )

            event_sink(
                {
                    "type": ("turn.query.rewritten"),
                    "turn_index": 1,
                    "purpose": "inspection",
                    "rewritten_query": (
                        "SELECT ?entity "
                        "?finalprovennacevariable "
                        "WHERE { "
                        "?entity ?predicate ?object . "
                        "}"
                    ),
                }
            )

            event_sink({"type": "run.completed", "termination_reason": ("budget_exhausted")})

        return _qa_run_result(max_turns=max_turns)


def test_list_experiments_returns_public_metadata() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "experiment_id": ("musique_pilot"),
                "benchmark": "musique",
                "status": "complete",
                "created_at": ("2026-07-18T16:07:40Z"),
                "case_count": 2,
                "hop_counts": [2, 4],
                "prompt_version": ("grounded-rdf-v2"),
                "extraction_model": ("test-model"),
                "requested_source_count": 2,
                "successful_extraction_count": 2,
                "failed_extraction_count": 0,
                "materialized_source_count": 2,
                "statement_count": 17,
            }
        ],
        "total": 1,
    }


def test_get_experiment_returns_one_public_resource() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot")

    assert response.status_code == 200

    payload = response.json()

    assert payload["experiment_id"] == "musique_pilot"
    assert payload["case_count"] == 2
    assert payload["hop_counts"] == [2, 4]


def test_experiment_response_hides_internal_and_gold_fields() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot")

    payload = response.json()

    assert "dataset_path" not in payload
    assert "cache_root" not in payload
    assert "graphdb" not in payload
    assert "cases" not in payload
    assert "answer" not in payload
    assert "gold_support_indices" not in payload


def test_get_experiment_returns_not_found_error() -> None:
    repository = StubExperimentRepository(experiments=())

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/missing")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "experiment_not_found",
            "message": ("experiment does not exist: missing"),
        }
    }


def test_get_experiment_rejects_invalid_identifier() -> None:
    repository = StubExperimentRepository(experiments=())

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/bad!")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_experiment_id"


def test_list_experiment_cases_returns_public_metadata() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases")

    assert response.status_code == 200
    assert response.json() == {
        "experiment_id": "musique_pilot",
        "items": [
            {
                "experiment_id": ("musique_pilot"),
                "case_id": "case-2-hop",
                "question": "First question?",
                "hop_count": 2,
                "answerable": True,
                "paragraph_count": 2,
            },
            {
                "experiment_id": ("musique_pilot"),
                "case_id": "case-4-hop",
                "question": ("Second question?"),
                "hop_count": 4,
                "answerable": True,
                "paragraph_count": 2,
            },
        ],
        "total": 2,
    }


def test_get_experiment_case_returns_one_public_resource() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases/case-4-hop")

    assert response.status_code == 200
    assert response.json() == {
        "experiment_id": "musique_pilot",
        "case_id": "case-4-hop",
        "question": "Second question?",
        "hop_count": 4,
        "answerable": True,
        "paragraph_count": 2,
    }


def test_experiment_case_response_hides_gold_metadata() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases/case-2-hop")

    payload = response.json()

    assert "answer" not in payload
    assert "answer_aliases" not in payload
    assert "gold_support_indices" not in payload
    assert "paragraph_indices" not in payload


def test_get_experiment_case_returns_not_found_error() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases/missing")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": ("experiment_case_not_found"),
            "message": ("case does not exist in experiment musique_pilot: missing"),
        }
    }


def test_list_experiment_cases_reports_missing_experiment() -> None:
    repository = StubExperimentRepository(experiments=())

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/missing/cases")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "experiment_not_found"


def test_get_experiment_case_reference_returns_benchmark_data(tmp_path: Path) -> None:
    dataset_path = tmp_path / "musique.jsonl"

    _write_test_musique_dataset(dataset_path)

    repository = StubExperimentRepository(
        experiments=(_stored_experiment(dataset_path=str(dataset_path)),)
    )

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases/case-2-hop/reference")

    assert response.status_code == 200

    payload = response.json()

    assert payload["experiment_id"] == ("musique_pilot")
    assert payload["case_id"] == ("case-2-hop")
    assert payload["question"] == ("First question?")
    assert payload["gold_answer"] == ("Hidden first answer")
    assert payload["hop_count"] == 2
    assert payload["gold_support_indices"] == [0]
    assert len(payload["decomposition"]) == 2
    assert len(payload["paragraphs"]) == 2
    assert payload["paragraphs"][0]["is_supporting"] is True


def test_get_experiment_case_reference_reports_missing_case() -> None:
    repository = StubExperimentRepository(experiments=(_stored_experiment(),))

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases/missing/reference")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "experiment_case_not_found"


def test_get_experiment_case_reference_reports_unavailable_dataset(tmp_path: Path) -> None:
    missing_dataset = tmp_path / "missing.jsonl"

    repository = StubExperimentRepository(
        experiments=(_stored_experiment(dataset_path=str(missing_dataset)),)
    )

    with TestClient(create_app(experiment_repository=repository)) as client:
        response = client.get("/api/v1/experiments/musique_pilot/cases/case-2-hop/reference")

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "experiment_reference_unavailable"


def test_synchronous_qa_run_exposes_research_configuration_and_queries(tmp_path: Path) -> None:
    dataset_path = tmp_path / "musique.jsonl"

    _write_test_musique_dataset(dataset_path)

    repository = StubExperimentRepository(
        experiments=(_stored_experiment(dataset_path=str(dataset_path)),)
    )

    qa_runner = StubQARunner()

    with TestClient(
        create_app(experiment_repository=repository, musique_qa_runner=qa_runner)
    ) as client:
        response = client.post(
            "/api/v1/experiments/musique_pilot/cases/case-2-hop/qa-runs",
            json={
                "question": ("Edited research question?"),
                "max_turns": 3,
                "query_scope": ("whole_repository"),
                "include_oracle_tuples": True,
                "model": "research-model",
                "max_tokens": 4096,
            },
        )

    assert response.status_code == 200

    payload = response.json()

    assert payload["question"] == ("Edited research question?")
    assert payload["query_scope"] == ("whole_repository")
    assert payload["include_oracle_tuples"] is True
    assert payload["max_turns"] == 3
    assert payload["termination_reason"] == "budget_exhausted"

    turn = payload["turns"][0]

    assert turn["purpose"] == "final"
    assert turn["semantic_sparql"] == ("SELECT ?answer WHERE { ?s ?p ?answer . }")
    assert "FROM <urn:case:graph>" in (turn["scoped_sparql"])
    assert turn["rewritten_sparql"] == (
        "SELECT ?answer ?finalprovennacevariable WHERE { ?s ?p ?answer . }"
    )
    assert turn["provenance_status"] == ("no_answers")

    assert len(qa_runner.calls) == 1

    call = qa_runner.calls[0]

    assert call["question"] == ("Edited research question?")
    assert call["query_scope"] == ("whole_repository")
    assert call["include_oracle_tuples"] is True
    assert isinstance(call["provenance_registry"], SourceRegistry)


def test_qa_stream_returns_ndjson_events(tmp_path: Path) -> None:
    dataset_path = tmp_path / "musique.jsonl"

    _write_test_musique_dataset(dataset_path)

    repository = StubExperimentRepository(
        experiments=(_stored_experiment(dataset_path=str(dataset_path)),)
    )

    qa_runner = StubQARunner(emit_events=True)

    with TestClient(
        create_app(experiment_repository=repository, musique_qa_runner=qa_runner)
    ) as client:
        with client.stream(
            "POST",
            "/api/v1/experiments/musique_pilot/cases/case-2-hop/qa-stream",
            json={"max_turns": 2, "query_scope": ("case_graphs"), "include_oracle_tuples": False},
        ) as response:
            events = [json.loads(line) for line in response.iter_lines() if line]

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")

    assert [event["type"] for event in events] == [
        "run.requested",
        "turn.query_generated",
        "turn.query.rewritten",
        "run.completed",
    ]

    assert events[0]["query_scope"] == ("case_graphs")
    assert events[0]["include_oracle_tuples"] is False

    assert events[1]["experiment_id"] == ("musique_pilot")
    assert events[1]["case_id"] == ("case-2-hop")


def _qa_run_result(*, max_turns: int) -> QAAgentRunResult:
    semantic_sparql = "SELECT ?answer WHERE { ?s ?p ?answer . }"

    scoped_sparql = "SELECT ?answer\nFROM <urn:case:graph>\nWHERE { ?s ?p ?answer . }"

    rewritten_sparql = "SELECT ?answer ?finalprovennacevariable WHERE { ?s ?p ?answer . }"

    execution = ProvenanceQueryExecution(
        original_query=scoped_sparql,
        original_result={"results": {"bindings": []}},
        rewritten_query=rewritten_sparql,
        rewritten_result={"results": {"bindings": []}},
    )

    decision = QAAgentDecision(
        status="query",
        purpose="final",
        sparql=semantic_sparql,
        rationale=("The final relation was selected."),
        assumptions=(),
    )

    attempt = QAQueryAttempt(
        turn_index=1,
        purpose="final",
        semantic_sparql=semantic_sparql,
        scoped_sparql=scoped_sparql,
        execution=execution,
        provenance_status="no_answers",
    )

    return QAAgentRunResult(
        configuration=QAAgentConfiguration(
            context_mode="graph_agent",
            graph_scope="case_all",
            answer_visibility="hidden",
            decomposition_visibility=("hop_count"),
            max_turns=max_turns,
        ),
        observation=None,
        prompt="test prompt",
        raw_response=json.dumps(decision.to_dict()),
        decision=decision,
        query_attempts=(attempt,),
        termination_reason=("budget_exhausted"),
    )


def _stored_experiment(
    *, dataset_path: str = ("/private/datasets/musique.jsonl")
) -> StoredMusiqueExperiment:
    first_source_id = "u_" + ("0" * 63) + "1"

    second_source_id = "u_" + ("0" * 63) + "2"

    manifest = MusiqueMaterializationManifest.from_dict(
        {
            "format": ("musique-pilot-materialization-v2"),
            "status": "complete",
            "created_at": datetime(2026, 7, 18, 16, 7, 40, tzinfo=UTC).isoformat(),
            "dataset_path": dataset_path,
            "prompt_version": ("grounded-rdf-v2"),
            "model": "test-model",
            "max_tokens": 4096,
            "cache_root": ("/private/runs/extractions"),
            "graphdb": {
                "base_url": ("http://localhost:7200"),
                "repository": ("private-repository"),
                "statements_before_run": 0,
            },
            "cases": [
                {
                    "case_id": ("case-2-hop"),
                    "hop_count": 2,
                    "question": ("First question?"),
                    "answer": ("Hidden first answer"),
                    "answer_aliases": [],
                    "answerable": True,
                    "paragraph_indices": [0, 1],
                    "gold_support_indices": [0],
                },
                {
                    "case_id": ("case-4-hop"),
                    "hop_count": 4,
                    "question": ("Second question?"),
                    "answer": ("Hidden second answer"),
                    "answer_aliases": [],
                    "answerable": True,
                    "paragraph_indices": [0, 1],
                    "gold_support_indices": [1],
                },
            ],
            "paragraph_occurrence_count": 4,
            "requested_source_count": 2,
            "successful_extraction_count": 2,
            "failed_extraction_count": 0,
            "new_outcome_count": 2,
            "reused_outcome_count": 0,
            "source_unit_ids": [first_source_id, second_source_id],
            "failures": [],
            "materialization": {
                "source_count": 2,
                "statement_count": 17,
                "graph_iris": [
                    ("urn:graphragprov:unit:u_0000000000000000"),
                    ("urn:graphragprov:unit:u_0000000000000001"),
                ],
            },
        }
    )

    return StoredMusiqueExperiment(experiment_id="musique_pilot", manifest=manifest)


def _write_test_musique_dataset(path: Path) -> None:
    shared_paragraphs = [
        {
            "idx": 0,
            "title": ("Supporting paragraph"),
            "paragraph_text": ("The supporting paragraph text."),
            "is_supporting": True,
        },
        {
            "idx": 1,
            "title": ("Distractor paragraph"),
            "paragraph_text": ("The distractor paragraph text."),
            "is_supporting": False,
        },
    ]

    first_row = {
        "id": "case-2-hop",
        "question": "First question?",
        "answer": "Hidden first answer",
        "answer_aliases": [],
        "answerable": True,
        "paragraphs": shared_paragraphs,
        "question_decomposition": [
            {
                "id": 0,
                "question": ("Intermediate question?"),
                "answer": ("Intermediate answer"),
                "paragraph_support_idx": 0,
            },
            {
                "id": 1,
                "question": ("Final subquestion?"),
                "answer": ("Hidden first answer"),
                "paragraph_support_idx": None,
            },
        ],
    }

    second_row = {
        "id": "case-4-hop",
        "question": "Second question?",
        "answer": "Hidden second answer",
        "answer_aliases": [],
        "answerable": True,
        "paragraphs": [
            {
                "idx": 0,
                "title": ("Supporting paragraph"),
                "paragraph_text": ("The supporting paragraph text."),
                "is_supporting": False,
            },
            {
                "idx": 1,
                "title": ("Distractor paragraph"),
                "paragraph_text": ("The distractor paragraph text."),
                "is_supporting": True,
            },
        ],
        "question_decomposition": [
            {"id": 0, "question": "Hop one?", "answer": "Answer one", "paragraph_support_idx": 1},
            {
                "id": 1,
                "question": "Hop two?",
                "answer": "Answer two",
                "paragraph_support_idx": None,
            },
            {
                "id": 2,
                "question": "Hop three?",
                "answer": "Answer three",
                "paragraph_support_idx": None,
            },
            {
                "id": 3,
                "question": "Hop four?",
                "answer": ("Hidden second answer"),
                "paragraph_support_idx": None,
            },
        ],
    }

    path.write_text(
        "\n".join([json.dumps(first_row), json.dumps(second_row)]) + "\n", encoding="utf-8"
    )
