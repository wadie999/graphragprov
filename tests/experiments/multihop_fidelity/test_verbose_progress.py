"""Tests for live multi-hop fidelity progress reporting."""

from __future__ import annotations

import json

from graphragprov.benchmarks.musique import (
    MusiqueCase,
    MusiqueHop,
    MusiqueParagraph,
    collect_musique_source_units,
)
from graphragprov.experiments.multihop_fidelity.graph import (
    ReferenceGraphExtractionResult,
    construct_reference_extractions,
)


def _case() -> MusiqueCase:
    return MusiqueCase(
        case_id="1hop__progress_test",
        question=("Who performed Album Alpha?"),
        answer="Artist Beta",
        answer_aliases=(),
        answerable=True,
        paragraphs=(
            MusiqueParagraph(
                index=4, title="Album Alpha", text=("Album Alpha was performed by Artist Beta.")
            ),
        ),
        decomposition=(
            MusiqueHop(
                hop_id=0,
                question=("Album Alpha >> performer"),
                answer="Artist Beta",
                paragraph_support_index=4,
            ),
        ),
        gold_support_indices=(4,),
    )


def _response() -> str:
    return json.dumps(
        {
            "statements": [
                {
                    "subject": {
                        "value": "Album Alpha",
                        "evidence": [{"segment": "title", "quote": "Album Alpha", "occurrence": 1}],
                    },
                    "predicate": {
                        "value": "performer",
                        "evidence": [{"segment": "text", "quote": "performed by", "occurrence": 1}],
                    },
                    "object": {
                        "value": "Artist Beta",
                        "evidence": [{"segment": "text", "quote": "Artist Beta", "occurrence": 1}],
                    },
                }
            ]
        }
    )


def test_reference_graph_progress_reports_source_before_provider_call() -> None:
    case = _case()

    sources = collect_musique_source_units((case,))

    events: list[tuple[str, dict[str, object]]] = []

    provider_calls = 0

    def progress(event: str, payload: dict[str, object]) -> None:
        events.append((event, payload))

        if event == ("graph.source.attempt.started"):
            assert provider_calls == 0

    def generate(prompt: str) -> str:
        nonlocal provider_calls

        provider_calls += 1

        assert "Album Alpha was performed by Artist Beta." in prompt

        return _response()

    outcome = construct_reference_extractions(
        case=case,
        sources=sources,
        generate_response=generate,
        max_attempts=2,
        progress_sink=progress,
    )

    assert isinstance(outcome, ReferenceGraphExtractionResult)

    assert provider_calls == 1

    names = [event for event, _ in events]

    assert names == [
        "graph.source.started",
        "graph.source.attempt.started",
        "graph.source.completed",
    ]

    started = events[0][1]

    assert started["source_position"] == 1

    assert started["source_count"] == 1

    assert started["paragraph_index"] == 4

    completed = events[-1][1]

    assert completed["attempt_index"] == 1
