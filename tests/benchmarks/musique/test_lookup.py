import pytest

from graphragprov.benchmarks.musique import find_unit, read_first_case
from graphragprov.config import musique_dataset_path

DATASET_PATH = musique_dataset_path()


@pytest.mark.skipif(
    not DATASET_PATH.is_file(),
    reason="The MuSiQue dataset is not installed.",
)
def test_find_source_unit() -> None:
    case = read_first_case(DATASET_PATH)
    paragraph = case.paragraphs[0]

    unit = find_unit(DATASET_PATH, paragraph.unit_id)

    assert unit.unit_id == paragraph.unit_id
    assert unit.text == paragraph.text
    assert unit.occurrences

    occurrence = unit.occurrences[0]

    assert occurrence.case_id == case.case_id
    assert occurrence.paragraph_index == paragraph.index
    assert occurrence.title == paragraph.title


@pytest.mark.skipif(
    not DATASET_PATH.is_file(),
    reason="The MuSiQue dataset is not installed.",
)
def test_missing_source_unit_raises_key_error() -> None:
    missing_id = f"u_{'0' * 64}"

    with pytest.raises(KeyError, match=missing_id):
        find_unit(DATASET_PATH, missing_id)
