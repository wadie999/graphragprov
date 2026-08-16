"""Tests for multi-hop reference graph construction."""

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
    reference_supporting_paragraphs,
)


def _case() -> MusiqueCase:
    """Build a realistic two-hop MuSiQue-shaped case with one distractor."""

    return MusiqueCase(
        case_id="2hop__reference_test",
        question="Where was the performer of Album Alpha born?",
        answer="City Gamma",
        answer_aliases=(),
        answerable=True,
        paragraphs=(
            MusiqueParagraph(
                index=0, title="Distractor", text="This paragraph is irrelevant to the question."
            ),
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
    """Build one grounded value in the real extraction response shape."""

    return {"value": value, "evidence": [{"segment": segment, "quote": quote, "occurrence": 1}]}


def _album_response() -> str:
    """Return a valid grounded extraction for the first support source."""

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
    """Return a valid grounded extraction for the second support source."""

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


def _prompt_contains_album_source(prompt: str) -> bool:
    """Recognize the source by immutable source content, not prompt formatting."""

    return "Album Alpha was performed by Artist Beta." in prompt


def _prompt_contains_artist_source(prompt: str) -> bool:
    """Recognize the source by immutable source content, not prompt formatting."""

    return "Artist Beta was born in City Gamma." in prompt


def test_reference_supporting_paragraphs_follow_dependency_order() -> None:
    case = _case()

    paragraphs = reference_supporting_paragraphs(case)

    assert tuple(paragraph.index for paragraph in paragraphs) == (7, 2)

    assert tuple(paragraph.title for paragraph in paragraphs) == ("Album Alpha", "Artist Beta")


def test_reference_graph_constructs_only_gold_support_sources() -> None:
    """Exercise case -> prompt -> extraction lifecycle for both gold sources."""

    case = _case()
    sources = collect_musique_source_units((case,))

    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)

        if _prompt_contains_album_source(prompt):
            return _album_response()

        if _prompt_contains_artist_source(prompt):
            return _artist_response()

        raise AssertionError(f"provider received an unexpected source prompt:\n{prompt}")

    outcome = construct_reference_extractions(
        case=case, sources=sources, generate_response=generate, max_attempts=2
    )

    assert isinstance(outcome, ReferenceGraphExtractionResult)

    assert tuple(item.paragraph_index for item in outcome.items) == (7, 2)

    assert tuple(item.run.source.title for item in outcome.items) == ("Album Alpha", "Artist Beta")

    assert outcome.attempt_count == 2
    assert outcome.retry_count == 0

    assert len(outcome.runs) == 2
    assert len(outcome.runs[0].extraction.statements) == 1
    assert len(outcome.runs[1].extraction.statements) == 1

    # Only the two gold support sources must reach the provider.
    assert len(prompts) == 2

    assert any(_prompt_contains_album_source(prompt) for prompt in prompts)

    assert any(_prompt_contains_artist_source(prompt) for prompt in prompts)

    assert all("This paragraph is irrelevant to the question." not in prompt for prompt in prompts)


def test_reference_graph_retries_whole_source_after_invalid_response() -> None:
    """Simulate a malformed first LLM response followed by successful recovery."""

    case = _case()
    sources = collect_musique_source_units((case,))

    album_calls = 0
    artist_calls = 0
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        nonlocal album_calls
        nonlocal artist_calls

        prompts.append(prompt)

        if _prompt_contains_album_source(prompt):
            album_calls += 1

            if album_calls == 1:
                return "not valid JSON"

            return _album_response()

        if _prompt_contains_artist_source(prompt):
            artist_calls += 1
            return _artist_response()

        raise AssertionError(f"provider received an unexpected source prompt:\n{prompt}")

    outcome = construct_reference_extractions(
        case=case, sources=sources, generate_response=generate, max_attempts=2
    )

    assert isinstance(outcome, ReferenceGraphExtractionResult)

    assert tuple(item.attempt_count for item in outcome.items) == (2, 1)

    assert outcome.attempt_count == 3
    assert outcome.retry_count == 1

    assert album_calls == 2
    assert artist_calls == 1
    assert len(prompts) == 3

    # The retry remains attached to the same source.
    assert _prompt_contains_album_source(prompts[0])
    assert _prompt_contains_album_source(prompts[1])

    # Construction proceeds to hop two only after hop one succeeds.
    assert _prompt_contains_artist_source(prompts[2])

    # The whole-source retry receives deterministic validation feedback.
    assert "invalid extraction JSON" in prompts[1]


def test_reference_graph_preserves_partial_progress_when_source_exhausts_retries() -> None:
    """A later source failure must not erase already successful extraction work."""

    case = _case()
    sources = collect_musique_source_units((case,))

    album_calls = 0
    artist_calls = 0

    def generate(prompt: str) -> str:
        nonlocal album_calls
        nonlocal artist_calls

        if _prompt_contains_album_source(prompt):
            album_calls += 1
            return _album_response()

        if _prompt_contains_artist_source(prompt):
            artist_calls += 1
            return "not valid JSON"

        raise AssertionError(f"provider received an unexpected source prompt:\n{prompt}")

    outcome = construct_reference_extractions(
        case=case, sources=sources, generate_response=generate, max_attempts=2
    )

    assert isinstance(outcome, ReferenceGraphExtractionFailure)

    assert outcome.paragraph_index == 2
    assert outcome.attempt_count == 2

    assert outcome.failure.stage == "response_validation"
    assert outcome.failure.error_type == "ValueError"
    assert "invalid extraction JSON" in outcome.failure.error_message

    assert len(outcome.completed_items) == 1

    completed = outcome.completed_items[0]

    assert completed.paragraph_index == 7
    assert completed.attempt_count == 1
    assert completed.run.source.title == "Album Alpha"
    assert len(completed.run.extraction.statements) == 1

    assert outcome.completed_runs == (completed.run,)

    assert album_calls == 1
    assert artist_calls == 2


def test_reference_graph_rejects_missing_support_source_before_provider_call() -> None:
    """Missing benchmark/source alignment is a deterministic input error."""

    case = _case()
    all_sources = collect_musique_source_units((case,))

    sources_without_artist = tuple(
        source for source in all_sources if source.title != "Artist Beta"
    )

    provider_calls = 0

    def generate(prompt: str) -> str:
        nonlocal provider_calls

        provider_calls += 1

        if _prompt_contains_album_source(prompt):
            return _album_response()

        raise AssertionError(f"provider received an unexpected source prompt:\n{prompt}")

    try:
        construct_reference_extractions(
            case=case, sources=sources_without_artist, generate_response=generate, max_attempts=2
        )
    except ValueError as error:
        assert "is missing from supplied sources" in str(error)
    else:
        raise AssertionError("missing supporting source should raise ValueError")

    # The first support source legitimately completed before the deterministic
    # missing-source problem was reached. No calls are made for the absent one.
    assert provider_calls == 1


def test_reference_graph_rejects_non_positive_attempt_limit() -> None:
    case = _case()
    sources = collect_musique_source_units((case,))

    def generate(prompt: str) -> str:
        raise AssertionError(f"provider must not be called:\n{prompt}")

    try:
        construct_reference_extractions(
            case=case, sources=sources, generate_response=generate, max_attempts=0
        )
    except ValueError as error:
        assert str(error) == "max attempts must be at least 1"
    else:
        raise AssertionError("non-positive max_attempts should raise ValueError")
