from graphragprov.benchmarks.twowiki.case import TwoWikiCase, TwoWikiSupportingFact
from graphragprov.benchmarks.twowiki.evidence import TwoWikiEvidence
from graphragprov.benchmarks.twowiki.paragraph import TwoWikiParagraph
from graphragprov.benchmarks.twowiki.selection import supporting_paragraphs


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


def test_returns_only_supporting_paragraphs_in_evidence_order() -> None:
    paragraphs = supporting_paragraphs(_case())

    assert tuple(paragraph.title for paragraph in paragraphs) == ("The Fascist", "Luciano Salce")


def test_does_not_return_distractor_paragraphs() -> None:
    paragraphs = supporting_paragraphs(_case())

    assert all(paragraph.title != "Peter Levin" for paragraph in paragraphs)
