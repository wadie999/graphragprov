from graphragprov.benchmarks.twowiki.case import TwoWikiCase, TwoWikiSupportingFact
from graphragprov.benchmarks.twowiki.materialization import collect_twowiki_source_units
from graphragprov.benchmarks.twowiki.paragraph import TwoWikiParagraph
from graphragprov.hashing import source_unit_id


def _case(
    *,
    case_id: str,
    paragraphs: tuple[TwoWikiParagraph, ...],
    supporting_facts: tuple[TwoWikiSupportingFact, ...] = (),
) -> TwoWikiCase:
    return TwoWikiCase(
        case_id=case_id,
        question_type="compositional",
        question="Example question?",
        paragraphs=paragraphs,
        supporting_facts=supporting_facts,
        evidences=(),
        evidence_ids=None,
        answer="Example answer",
        answer_id=None,
        entity_ids=(),
    )


def test_collects_all_context_paragraphs() -> None:
    case = _case(
        case_id="case-1",
        paragraphs=(
            TwoWikiParagraph(
                index=0, title="Supporting", sentences=("First sentence.", "Second sentence.")
            ),
            TwoWikiParagraph(index=1, title="Distractor", sentences=("Distractor text.",)),
        ),
        supporting_facts=(TwoWikiSupportingFact(title="Supporting", sentence_index=1),),
    )

    units = collect_twowiki_source_units((case,))

    assert len(units) == 2

    supporting = units[0]
    distractor = units[1]

    assert supporting.title == "Supporting"
    assert supporting.text == "First sentence. Second sentence."
    assert supporting.occurrences[0].case_id == "case-1"
    assert supporting.occurrences[0].paragraph_index == 0
    assert supporting.occurrences[0].supporting_sentence_indices == (1,)

    assert distractor.title == "Distractor"
    assert distractor.text == "Distractor text."
    assert distractor.occurrences[0].supporting_sentence_indices == ()


def test_materializes_canonical_text_and_source_identity() -> None:
    paragraph = TwoWikiParagraph(
        index=0,
        title="The Fascist",
        sentences=(
            "The Fascist  is a 1961 Italian film directed by Luciano Salce.",
            "It was coproduced with France.",
            "It was also the first feature film scored by Ennio Morricone.",
        ),
    )

    case = _case(case_id="case-1", paragraphs=(paragraph,))

    (unit,) = collect_twowiki_source_units((case,))

    expected_text = (
        "The Fascist  is a 1961 Italian film directed by Luciano Salce. "
        "It was coproduced with France. "
        "It was also the first feature film scored by Ennio Morricone."
    )

    assert unit.title == "The Fascist"
    assert unit.text == expected_text
    assert unit.unit_id == source_unit_id(title="The Fascist", text=expected_text)

    # The benchmark paragraph and materialized source unit share one
    # canonical source identity.
    assert paragraph.unit_id == unit.unit_id


def test_deduplicates_identical_sources_and_preserves_occurrences() -> None:
    paragraph_a = TwoWikiParagraph(
        index=2, title="Shared Article", sentences=("The same source text appears in both cases.",)
    )
    paragraph_b = TwoWikiParagraph(
        index=7, title="Shared Article", sentences=("The same source text appears in both cases.",)
    )

    first_case = _case(
        case_id="case-1",
        paragraphs=(paragraph_a,),
        supporting_facts=(TwoWikiSupportingFact(title="Shared Article", sentence_index=0),),
    )
    second_case = _case(case_id="case-2", paragraphs=(paragraph_b,))

    units = collect_twowiki_source_units((first_case, second_case))

    assert len(units) == 1

    (unit,) = units

    assert unit.unit_id == paragraph_a.unit_id
    assert paragraph_a.unit_id == paragraph_b.unit_id

    assert len(unit.occurrences) == 2

    assert unit.occurrences[0].case_id == "case-1"
    assert unit.occurrences[0].paragraph_index == 2
    assert unit.occurrences[0].supporting_sentence_indices == (0,)

    assert unit.occurrences[1].case_id == "case-2"
    assert unit.occurrences[1].paragraph_index == 7
    assert unit.occurrences[1].supporting_sentence_indices == ()


def test_repeated_case_input_does_not_duplicate_occurrence() -> None:
    paragraph = TwoWikiParagraph(index=0, title="Article", sentences=("Stable source text.",))

    case = _case(
        case_id="case-1",
        paragraphs=(paragraph,),
        supporting_facts=(TwoWikiSupportingFact(title="Article", sentence_index=0),),
    )

    units = collect_twowiki_source_units((case, case))

    assert len(units) == 1

    (unit,) = units

    assert len(unit.occurrences) == 1
    assert unit.occurrences[0].case_id == "case-1"
    assert unit.occurrences[0].paragraph_index == 0
    assert unit.occurrences[0].supporting_sentence_indices == (0,)
