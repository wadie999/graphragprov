"""Acceptance-policy tests for H0 reference graph construction."""

from __future__ import annotations

import json

from graphragprov.benchmarks.musique import (
    MusiqueCase,
    MusiqueHop,
    MusiqueParagraph,
    collect_musique_source_units,
)
from graphragprov.experiments.multihop_fidelity.graph import (
    ReferenceGraphExtractionFailure,
    ReferenceGraphExtractionResult,
    construct_reference_extractions,
)
from graphragprov.extraction.run import GroundedExtractionFailure


def _case() -> MusiqueCase:
    return MusiqueCase(
        case_id="2hop__empty_acceptance_test",
        question="Where was the performer of Album Alpha born?",
        answer="City Gamma",
        answer_aliases=(),
        answerable=True,
        paragraphs=(
            MusiqueParagraph(
                index=2, title="Artist Beta", text="Artist Beta was born in City Gamma."
            ),
            MusiqueParagraph(
                index=7, title="Album Alpha", text="Album Alpha was performed by Artist Beta."
            ),
        ),
        decomposition=(
            MusiqueHop(
                hop_id=0,
                question="Album Alpha >> performer",
                answer="Artist Beta",
                paragraph_support_index=7,
            ),
            MusiqueHop(
                hop_id=1,
                question="#1 >> place of birth",
                answer="City Gamma",
                paragraph_support_index=2,
            ),
        ),
        gold_support_indices=(7, 2),
    )


def _grounded_value(value: str, *, segment: str, quote: str) -> dict[str, object]:
    return {"value": value, "evidence": [{"segment": segment, "quote": quote, "occurrence": 1}]}


def _album_response() -> str:
    return json.dumps(
        {
            "statements": [
                {
                    "subject": _grounded_value("Album Alpha", segment="title", quote="Album Alpha"),
                    "predicate": _grounded_value("performer", segment="text", quote="performed by"),
                    "object": _grounded_value("Artist Beta", segment="text", quote="Artist Beta"),
                }
            ]
        }
    )


def _artist_response() -> str:
    return json.dumps(
        {
            "statements": [
                {
                    "subject": _grounded_value("Artist Beta", segment="title", quote="Artist Beta"),
                    "predicate": _grounded_value("placeOfBirth", segment="text", quote="born in"),
                    "object": _grounded_value("City Gamma", segment="text", quote="City Gamma"),
                }
            ]
        }
    )


def test_zero_statement_support_extraction_is_retried() -> None:
    case = _case()
    sources = collect_musique_source_units((case,))
    album_calls = 0
    events: list[tuple[str, dict[str, object]]] = []

    def progress(event: str, payload: dict[str, object]) -> None:
        events.append((event, payload))

    def generate(prompt: str) -> str:
        nonlocal album_calls

        if "Album Alpha was performed by Artist Beta." in prompt:
            album_calls += 1

            if album_calls == 1:
                return json.dumps({"statements": []})

            assert "zero validated grounded statements" in prompt
            return _album_response()

        if "Artist Beta was born in City Gamma." in prompt:
            return _artist_response()

        raise AssertionError(f"unexpected provider prompt:\n{prompt}")

    outcome = construct_reference_extractions(
        case=case,
        sources=sources,
        generate_response=generate,
        max_attempts=2,
        progress_sink=progress,
    )

    assert isinstance(outcome, ReferenceGraphExtractionResult)
    assert tuple(item.attempt_count for item in outcome.items) == (2, 1)
    assert outcome.items[0].run.extraction.statements

    failed = [
        payload["failure"] for event, payload in events if event == "graph.source.attempt.failed"
    ]

    assert len(failed) == 1

    failure = failed[0]

    assert isinstance(failure, GroundedExtractionFailure)

    assert failure.error_type == "EmptyReferenceExtraction"


def test_repeated_empty_support_extraction_fails_before_materialization() -> None:
    case = _case()
    sources = collect_musique_source_units((case,))

    def generate(prompt: str) -> str:
        assert "Album Alpha was performed by Artist Beta." in prompt
        return json.dumps({"statements": []})

    outcome = construct_reference_extractions(
        case=case, sources=sources, generate_response=generate, max_attempts=3
    )

    assert isinstance(outcome, ReferenceGraphExtractionFailure)
    assert outcome.paragraph_index == 7
    assert outcome.attempt_count == 3
    assert outcome.completed_items == ()
    assert outcome.failure.stage == "response_validation"
    assert outcome.failure.error_type == "EmptyReferenceExtraction"
    assert "zero validated grounded statements" in outcome.failure.error_message
