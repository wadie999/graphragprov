import pytest

from graphragprov.benchmarks.musique.reader import read_first_case
from graphragprov.config import musique_dataset_path

DATASET_PATH = musique_dataset_path()


@pytest.mark.skipif(
    not DATASET_PATH.is_file(),
    reason="The MuSiQue dataset is not installed.",
)
def test_read_first_real_case() -> None:
    case = read_first_case(DATASET_PATH)

    assert case.case_id == "2hop__153573_109006"
    assert case.question == (
        "Who developed the eponymous character from the series "
        "that contains Mickey's Safari in Letterland?"
    )
    assert case.answer == "Walt Disney"
    assert case.answerable is False

    assert len(case.paragraphs) == 20
    assert case.paragraphs[0].index == 0
    assert case.paragraphs[0].title == "History of the Internet"
    assert case.paragraphs[0].text.startswith("Precursors to the web browser")
