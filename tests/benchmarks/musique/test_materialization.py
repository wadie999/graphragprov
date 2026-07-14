from graphragprov.benchmarks.musique.case import (
    MusiqueCase,
)
from graphragprov.benchmarks.musique.materialization import (
    collect_musique_source_units,
)
from graphragprov.benchmarks.musique.paragraph import (
    MusiqueParagraph,
)


def make_case(
    *,
    case_id: str,
    paragraphs: tuple[MusiqueParagraph, ...],
    supporting_indices: tuple[int, ...] = (),
) -> MusiqueCase:
    return MusiqueCase(
        case_id=case_id,
        question="Example question?",
        answer="Example answer",
        answer_aliases=(),
        answerable=True,
        paragraphs=paragraphs,
        decomposition=(),
        gold_support_indices=supporting_indices,
    )


def test_collects_all_case_paragraphs() -> None:
    case = make_case(
        case_id="case-1",
        paragraphs=(
            MusiqueParagraph(
                index=0,
                title="Supporting",
                text="Supporting text.",
            ),
            MusiqueParagraph(
                index=1,
                title="Distractor",
                text="Distractor text.",
            ),
        ),
        supporting_indices=(0,),
    )

    units = collect_musique_source_units((case,))

    assert len(units) == 2
    assert [unit.title for unit in units] == [
        "Supporting",
        "Distractor",
    ]

    assert units[0].occurrences[0].is_supporting
    assert not units[1].occurrences[0].is_supporting


def test_deduplicates_identical_content_across_cases() -> None:
    first_case = make_case(
        case_id="case-1",
        paragraphs=(
            MusiqueParagraph(
                index=0,
                title="Shared paragraph",
                text="The same exact text.",
            ),
        ),
        supporting_indices=(0,),
    )

    second_case = make_case(
        case_id="case-2",
        paragraphs=(
            MusiqueParagraph(
                index=7,
                title="Shared paragraph",
                text="The same exact text.",
            ),
        ),
    )

    units = collect_musique_source_units(
        (
            first_case,
            second_case,
        )
    )

    assert len(units) == 1
    assert len(units[0].occurrences) == 2

    assert units[0].occurrences[0].case_id == ("case-1")
    assert units[0].occurrences[0].paragraph_index == 0
    assert units[0].occurrences[0].is_supporting

    assert units[0].occurrences[1].case_id == ("case-2")
    assert units[0].occurrences[1].paragraph_index == 7
    assert not units[0].occurrences[1].is_supporting


def test_preserves_first_seen_source_order() -> None:
    first_case = make_case(
        case_id="case-1",
        paragraphs=(
            MusiqueParagraph(
                index=3,
                title="First",
                text="First text.",
            ),
            MusiqueParagraph(
                index=1,
                title="Second",
                text="Second text.",
            ),
        ),
    )

    second_case = make_case(
        case_id="case-2",
        paragraphs=(
            MusiqueParagraph(
                index=0,
                title="Third",
                text="Third text.",
            ),
        ),
    )

    units = collect_musique_source_units(
        (
            first_case,
            second_case,
        )
    )

    assert [unit.title for unit in units] == [
        "First",
        "Second",
        "Third",
    ]


def test_repeated_case_input_is_idempotent() -> None:
    case = make_case(
        case_id="case-1",
        paragraphs=(
            MusiqueParagraph(
                index=0,
                title="Shared paragraph",
                text="The same exact text.",
            ),
        ),
        supporting_indices=(0,),
    )

    units = collect_musique_source_units(
        (
            case,
            case,
        )
    )

    assert len(units) == 1
    assert len(units[0].occurrences) == 1
