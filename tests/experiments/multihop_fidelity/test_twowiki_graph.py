import json

from graphragprov.benchmarks.twowiki.case import TwoWikiCase, TwoWikiSupportingFact
from graphragprov.benchmarks.twowiki.evidence import TwoWikiEvidence
from graphragprov.benchmarks.twowiki.materialization import collect_twowiki_source_units
from graphragprov.benchmarks.twowiki.paragraph import TwoWikiParagraph
from graphragprov.experiments.multihop_fidelity.graph import ReferenceGraphExtractionResult
from graphragprov.experiments.multihop_fidelity.twowiki_graph import (
    construct_twowiki_reference_extractions,
)


def _case() -> TwoWikiCase:
    return TwoWikiCase(
        case_id="586507fa0bd911eba7f7acde48001122",
        question_type="compositional",
        question="Where was the director of film The Fascist born?",
        paragraphs=(
            TwoWikiParagraph(
                index=0,
                title="Peter Levin",
                sentences=("Peter Levin is an American director of film, television and theatre.",),
            ),
            TwoWikiParagraph(
                index=1,
                title="The Fascist",
                sentences=(
                    "The Fascist  is a 1961 Italian film directed by Luciano Salce.",
                    "It was coproduced with France.",
                    "It was also the first feature film scored by Ennio Morricone.",
                ),
            ),
            TwoWikiParagraph(
                index=2,
                title="Luciano Salce",
                sentences=(
                    (
                        "Luciano Salce (25 September 1922, in Rome – "
                        "17 December 1989, in Rome) was an Italian film "
                        "director, actor and lyricist."
                    ),
                    (
                        'His 1962 film "Le pillole di Ercole" was shown as part '
                        "of a retrospective on Italian comedy at the 67th Venice "
                        "International Film Festival."
                    ),
                ),
            ),
        ),
        supporting_facts=(
            TwoWikiSupportingFact(title="The Fascist", sentence_index=0),
            TwoWikiSupportingFact(title="Luciano Salce", sentence_index=0),
        ),
        evidences=(
            TwoWikiEvidence(subject="The Fascist", relation="director", object="Luciano Salce"),
            TwoWikiEvidence(subject="Luciano Salce", relation="place of birth", object="Rome"),
        ),
        evidence_ids=None,
        answer="Rome",
        answer_id="Q220",
        entity_ids=("Q232190", "Q697834"),
    )


def _grounded_value(
    value: str, *, segment: str, quote: str, occurrence: int = 1
) -> dict[str, object]:
    return {
        "value": value,
        "evidence": [{"segment": segment, "quote": quote, "occurrence": occurrence}],
    }


def _fascist_response() -> str:
    return json.dumps(
        {
            "statements": [
                {
                    "subject": _grounded_value("The Fascist", segment="title", quote="The Fascist"),
                    "predicate": _grounded_value("director", segment="text", quote="directed by"),
                    "object": _grounded_value(
                        "Luciano Salce", segment="text", quote="Luciano Salce"
                    ),
                }
            ]
        }
    )


def _salce_response() -> str:
    return json.dumps(
        {
            "statements": [
                {
                    "subject": _grounded_value(
                        "Luciano Salce", segment="title", quote="Luciano Salce"
                    ),
                    "predicate": _grounded_value(
                        "placeOfBirth", segment="text", quote="in", occurrence=1
                    ),
                    "object": _grounded_value("Rome", segment="text", quote="Rome", occurrence=1),
                }
            ]
        }
    )


def test_constructs_reference_graph_from_only_supporting_sources() -> None:
    case = _case()
    sources = collect_twowiki_source_units((case,))

    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)

        if "The Fascist  is a 1961 Italian film directed by Luciano Salce." in prompt:
            return _fascist_response()

        if "Luciano Salce (25 September 1922, in Rome" in prompt:
            return _salce_response()

        raise AssertionError(f"provider received an unexpected source prompt:\n{prompt}")

    outcome = construct_twowiki_reference_extractions(
        case=case, sources=sources, generate_response=generate, max_attempts=2
    )

    assert isinstance(outcome, ReferenceGraphExtractionResult)

    assert tuple(item.paragraph_index for item in outcome.items) == (1, 2)

    assert tuple(item.run.source.title for item in outcome.items) == (
        "The Fascist",
        "Luciano Salce",
    )

    assert outcome.attempt_count == 2
    assert outcome.retry_count == 0

    assert len(prompts) == 2

    assert all("Peter Levin is an American director of film" not in prompt for prompt in prompts)

    first_statement = outcome.items[0].run.extraction.statements[0]

    assert first_statement.subject.value == "The Fascist"
    assert first_statement.predicate.value == "director"
    assert first_statement.object.value == "Luciano Salce"

    second_statement = outcome.items[1].run.extraction.statements[0]

    assert second_statement.subject.value == "Luciano Salce"
    assert second_statement.predicate.value == "placeOfBirth"
    assert second_statement.object.value == "Rome"


def test_preserves_exact_grounding_for_repeated_rome_occurrences() -> None:
    case = _case()
    sources = collect_twowiki_source_units((case,))

    def generate(prompt: str) -> str:
        if "The Fascist  is a 1961 Italian film directed by Luciano Salce." in prompt:
            return _fascist_response()

        if "Luciano Salce (25 September 1922, in Rome" in prompt:
            return _salce_response()

        raise AssertionError(f"provider received an unexpected source prompt:\n{prompt}")

    outcome = construct_twowiki_reference_extractions(
        case=case, sources=sources, generate_response=generate, max_attempts=1
    )

    assert isinstance(outcome, ReferenceGraphExtractionResult)

    salce_statement = outcome.items[1].run.extraction.statements[0]

    predicate_span = salce_statement.predicate.evidence[0]
    object_span = salce_statement.object.evidence[0]

    assert predicate_span.start == 34
    assert predicate_span.end == 36
    assert object_span.start == 37
    assert object_span.end == 41
