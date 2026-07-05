import pytest

from graphragprov.benchmarks.musique import select_cases
from graphragprov.config import musique_dataset_path
from graphragprov.extraction.musique import (
    build_musique_extraction_prompt,
)

DATASET_PATH = musique_dataset_path()

pytestmark = pytest.mark.skipif(
    not DATASET_PATH.exists(),
    reason="local MuSiQue dataset is unavailable",
)


def test_build_prompt_from_musique_paragraph() -> None:
    case = select_cases(
        DATASET_PATH,
        hop_count=3,
        limit=1,
    )[0]

    paragraph = case.paragraphs[0]

    prompt = build_musique_extraction_prompt(
        case_id=case.case_id,
        paragraph_index=paragraph.index,
        expected_hops=3,
        path=DATASET_PATH,
    )

    assert paragraph.title in prompt
    assert paragraph.text in prompt
    assert paragraph.unit_id not in prompt


def test_reject_case_with_unexpected_hop_count() -> None:
    case = select_cases(
        DATASET_PATH,
        hop_count=3,
        limit=1,
    )[0]

    with pytest.raises(ValueError, match="has 3 hops, not 2"):
        build_musique_extraction_prompt(
            case_id=case.case_id,
            paragraph_index=case.paragraphs[0].index,
            expected_hops=2,
            path=DATASET_PATH,
        )


def test_reject_unknown_paragraph_index() -> None:
    case = select_cases(
        DATASET_PATH,
        hop_count=3,
        limit=1,
    )[0]

    with pytest.raises(ValueError, match="has no paragraph"):
        build_musique_extraction_prompt(
            case_id=case.case_id,
            paragraph_index=999_999,
            expected_hops=3,
            path=DATASET_PATH,
        )
