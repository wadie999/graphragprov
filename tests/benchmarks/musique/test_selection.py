import pytest

from graphragprov.benchmarks.musique.reader import iter_cases
from graphragprov.benchmarks.musique.selection import select_cases
from graphragprov.config import musique_dataset_path

DATASET_PATH = musique_dataset_path()


@pytest.mark.skipif(
    not DATASET_PATH.is_file(),
    reason="The MuSiQue dataset is not installed.",
)
def test_select_answerable_three_hop_cases() -> None:
    selected = select_cases(
        DATASET_PATH,
        hop_count=3,
        limit=5,
        answerable_only=True,
    )

    expected_ids = [
        case.case_id for case in iter_cases(DATASET_PATH) if case.hop_count == 3 and case.answerable
    ][:5]

    assert [case.case_id for case in selected] == expected_ids
    assert all(case.hop_count == 3 for case in selected)
    assert all(case.answerable for case in selected)


@pytest.mark.skipif(
    not DATASET_PATH.is_file(),
    reason="The MuSiQue dataset is not installed.",
)
def test_select_four_hop_cases_including_unanswerable() -> None:
    selected = select_cases(
        DATASET_PATH,
        hop_count=4,
        limit=3,
        answerable_only=False,
    )

    assert len(selected) == 3
    assert all(case.hop_count == 4 for case in selected)


def test_zero_limit_returns_no_cases() -> None:
    selected = select_cases(
        DATASET_PATH,
        hop_count=2,
        limit=0,
    )

    assert selected == ()


def test_negative_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="limit"):
        select_cases(
            DATASET_PATH,
            hop_count=2,
            limit=-1,
        )
