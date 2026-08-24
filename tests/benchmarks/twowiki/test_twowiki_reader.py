import pytest

from graphragprov.benchmarks.twowiki.reader import load_case
from graphragprov.config import twowiki_dataset_path

DATASET_PATH = twowiki_dataset_path()
CASE_ID = "586507fa0bd911eba7f7acde48001122"


@pytest.mark.skipif(
    not DATASET_PATH.is_file(), reason="The 2WikiMultiHopQA dataset is not installed."
)
def test_load_running_example() -> None:
    case = load_case(DATASET_PATH, CASE_ID)

    assert case.case_id == CASE_ID
    assert case.question_type == "compositional"
    assert case.question == "Where was the director of film The Fascist born?"
    assert case.answer == "Rome"
    assert case.answer_id == "Q220"

    assert len(case.paragraphs) == 10

    assert case.evidences[0].subject == "The Fascist"
    assert case.evidences[0].relation == "director"
    assert case.evidences[0].object == "Luciano Salce"

    assert case.evidences[1].subject == "Luciano Salce"
    assert case.evidences[1].relation == "place of birth"
    assert case.evidences[1].object == "Rome"

    assert case.supporting_facts[0].title == "The Fascist"
    assert case.supporting_facts[0].sentence_index == 0

    assert case.supporting_facts[1].title == "Luciano Salce"
    assert case.supporting_facts[1].sentence_index == 0

    assert case.entity_ids == ("Q232190", "Q697834")
