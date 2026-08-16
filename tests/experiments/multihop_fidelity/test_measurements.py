"""Tests for multi-hop fidelity extraction and graph measurements."""

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
from graphragprov.experiments.multihop_fidelity.measurements import (
    measure_frozen_graph,
    measure_reference_extractions,
)


def _case() -> MusiqueCase:
    return MusiqueCase(
        case_id="2hop__measurement_test",
        question="Where was the performer of Album Alpha born?",
        answer="City Gamma",
        answer_aliases=(),
        answerable=True,
        paragraphs=(
            MusiqueParagraph(
                index=2, title="Artist Beta", text="Artist Beta was born in City Gamma."
            ),
            MusiqueParagraph(
                index=7,
                title="Album Alpha",
                text="Album Alpha was performed by Artist Beta in 1993.",
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


def _grounded_value(
    value: str, *, segment: str, quote: str, datatype: str | None = None
) -> dict[str, object]:
    result: dict[str, object] = {
        "value": value,
        "evidence": [{"segment": segment, "quote": quote, "occurrence": 1}],
    }

    if datatype is not None:
        result["datatype"] = datatype

    return result


def _album_initial_response() -> str:
    """One valid statement plus one with deliberately invalid evidence."""

    return json.dumps(
        {
            "statements": [
                {
                    "subject": _grounded_value("Album Alpha", segment="title", quote="Album Alpha"),
                    "predicate": _grounded_value("performer", segment="text", quote="performed by"),
                    "object": _grounded_value("Artist Beta", segment="text", quote="Artist Beta"),
                },
                {
                    "subject": _grounded_value("Album Alpha", segment="title", quote="Album Alpha"),
                    "predicate": _grounded_value("releaseYear", segment="text", quote="1993"),
                    "object": _grounded_value(
                        "1993", segment="text", quote="1992", datatype="year"
                    ),
                },
            ]
        }
    )


def _album_correction_response() -> str:
    return json.dumps(
        {
            "statements": [
                {
                    "subject": _grounded_value("Album Alpha", segment="title", quote="Album Alpha"),
                    "predicate": _grounded_value("releaseYear", segment="text", quote="1993"),
                    "object": _grounded_value(
                        "1993", segment="text", quote="1993", datatype="year"
                    ),
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


def test_reference_measurements_reuse_real_coverage_and_correction_results() -> None:
    """Measure a realistic extraction including targeted correction."""

    case = _case()
    sources = collect_musique_source_units((case,))

    calls: list[str] = []

    def generate(prompt: str) -> str:
        calls.append(prompt)

        if "Return only corrected replacements" in prompt:
            return _album_correction_response()

        if "Album Alpha was performed by Artist Beta in 1993." in prompt:
            return _album_initial_response()

        if "Artist Beta was born in City Gamma." in prompt:
            return _artist_response()

        raise AssertionError(f"unexpected provider prompt:\n{prompt}")

    outcome = construct_reference_extractions(
        case=case, sources=sources, generate_response=generate, max_attempts=2
    )

    assert isinstance(outcome, ReferenceGraphExtractionResult)

    measurements = measure_reference_extractions(outcome)

    assert measurements.source_count == 2
    assert measurements.statement_occurrence_count == 3

    # Both source extractions succeeded on their first whole-source attempt.
    # The bad evidence quote was handled by targeted correction instead.
    assert measurements.whole_source_attempt_count == 2
    assert measurements.whole_source_retry_count == 0

    assert measurements.targeted_correction_count == 1
    assert measurements.initial_rejection_count == 1
    assert measurements.corrected_valid_statement_count == 1
    assert measurements.remaining_rejection_count == 0

    assert measurements.title_character_count == (len("Album Alpha") + len("Artist Beta"))

    assert measurements.text_character_count == (
        len("Album Alpha was performed by Artist Beta in 1993.")
        + len("Artist Beta was born in City Gamma.")
    )

    assert len(measurements.sources) == 2

    album = measurements.sources[0]
    artist = measurements.sources[1]

    assert album.paragraph_index == 7
    assert artist.paragraph_index == 2

    assert album.statement_occurrence_count == 2
    assert artist.statement_occurrence_count == 1

    assert album.correction_attempted is True
    assert album.initial_rejection_count == 1
    assert album.corrected_valid_statement_count == 1
    assert album.remaining_rejection_count == 0

    assert artist.correction_attempted is False
    assert artist.initial_rejection_count == 0

    # Do not reimplement the existing metrics package here. Verify that its
    # complete measurement families survive into the experiment artifact.
    expected_coverage_sections = {
        "character_coverage",
        "sentence_coverage",
        "longest_uncovered_text_region",
        "statement_density",
        "title_reliance",
    }

    assert expected_coverage_sections <= set(album.coverage)
    assert expected_coverage_sections <= set(artist.coverage)

    # Two initial extraction calls + one targeted correction call.
    assert len(calls) == 3


def test_frozen_graph_measurements_use_rdf_set_semantics() -> None:
    """Duplicates are occurrences upstream but only one semantic RDF triple."""

    graph_ntriples = "\n".join(
        (
            (
                "<urn:graphragprov:entity:Album%20Alpha> "
                "<urn:graphragprov:predicate:performer> "
                "<urn:graphragprov:entity:Artist%20Beta> ."
            ),
            (
                "<urn:graphragprov:entity:Album%20Alpha> "
                "<urn:graphragprov:predicate:performer> "
                "<urn:graphragprov:entity:Artist%20Beta> ."
            ),
            (
                "<urn:graphragprov:entity:Album%20Alpha> "
                "<urn:graphragprov:predicate:releaseYear> "
                '"1993"^^<http://www.w3.org/2001/XMLSchema#gYear> .'
            ),
            (
                "<urn:graphragprov:entity:Artist%20Beta> "
                "<urn:graphragprov:predicate:placeOfBirth> "
                "<urn:graphragprov:entity:City%20Gamma> ."
            ),
        )
    )

    measurements = measure_frozen_graph(graph_ntriples, named_graph_count=2)

    assert measurements.named_graph_count == 2

    # Four serialized lines, but only three distinct RDF triples.
    assert measurements.semantic_triple_count == 3

    assert measurements.resource_node_count == 3
    assert measurements.entity_node_count == 3
    assert measurements.literal_value_count == 1
    assert measurements.predicate_count == 3


def test_frozen_graph_measurements_distinguish_resources_from_literals() -> None:
    graph_ntriples = "\n".join(
        (
            (
                "<urn:graphragprov:entity:Album%20Alpha> "
                "<urn:graphragprov:predicate:releaseYear> "
                '"1993"^^<http://www.w3.org/2001/XMLSchema#gYear> .'
            ),
            ('<urn:graphragprov:entity:Album%20Alpha> <urn:graphragprov:predicate:length> "42" .'),
        )
    )

    measurements = measure_frozen_graph(graph_ntriples, named_graph_count=1)

    assert measurements.semantic_triple_count == 2

    # Literals are not silently counted as graph resource/entity nodes.
    assert measurements.resource_node_count == 1
    assert measurements.entity_node_count == 1
    assert measurements.literal_value_count == 2
    assert measurements.predicate_count == 2


def test_empty_frozen_graph_has_zero_structure_counts() -> None:
    measurements = measure_frozen_graph("", named_graph_count=0)

    assert measurements.to_dict() == {
        "named_graph_count": 0,
        "semantic_triple_count": 0,
        "resource_node_count": 0,
        "entity_node_count": 0,
        "literal_value_count": 0,
        "predicate_count": 0,
    }


def test_negative_named_graph_count_is_rejected() -> None:
    try:
        measure_frozen_graph("", named_graph_count=-1)
    except ValueError as error:
        assert str(error) == ("named graph count must not be negative")
    else:
        raise AssertionError("negative named graph count must fail")
