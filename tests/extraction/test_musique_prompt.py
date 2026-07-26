import pytest

from graphragprov.benchmarks.musique import MusiqueCase, select_cases
from graphragprov.config import musique_dataset_path
from graphragprov.extraction.musique import (
    build_musique_extraction_prompt,
    load_musique_source_unit,
    run_musique_grounded_extraction,
)

DATASET_PATH = musique_dataset_path()

pytestmark = pytest.mark.skipif(
    not DATASET_PATH.exists(), reason="local MuSiQue dataset is unavailable"
)


def first_three_hop_case() -> MusiqueCase:
    return select_cases(DATASET_PATH, hop_count=3, limit=1)[0]


def test_loads_musique_paragraph_as_source_unit() -> None:
    case = first_three_hop_case()
    paragraph = case.paragraphs[0]

    source = load_musique_source_unit(
        case_id=case.case_id, paragraph_index=paragraph.index, expected_hops=3, path=DATASET_PATH
    )

    assert source.unit_id == paragraph.unit_id
    assert source.title == paragraph.title
    assert source.text == paragraph.text


def test_builds_prompt_from_loaded_source_unit() -> None:
    case = first_three_hop_case()
    paragraph = case.paragraphs[0]

    prompt = build_musique_extraction_prompt(
        case_id=case.case_id, paragraph_index=paragraph.index, expected_hops=3, path=DATASET_PATH
    )

    assert paragraph.title in prompt
    assert paragraph.text in prompt
    assert paragraph.unit_id not in prompt


def test_rejects_case_with_unexpected_hop_count() -> None:
    case = first_three_hop_case()

    with pytest.raises(ValueError, match="has 3 hops, not 2"):
        load_musique_source_unit(
            case_id=case.case_id,
            paragraph_index=case.paragraphs[0].index,
            expected_hops=2,
            path=DATASET_PATH,
        )


def test_rejects_unknown_paragraph_index() -> None:
    case = first_three_hop_case()

    with pytest.raises(ValueError, match="has no paragraph"):
        load_musique_source_unit(
            case_id=case.case_id, paragraph_index=999_999, expected_hops=3, path=DATASET_PATH
        )


def test_runs_grounded_extraction_on_musique_paragraph() -> None:
    case = first_three_hop_case()
    paragraph = case.paragraphs[0]
    received_prompts: list[str] = []

    def fake_model(prompt: str) -> str:
        received_prompts.append(prompt)
        return '{"statements": []}'

    run = run_musique_grounded_extraction(
        case_id=case.case_id,
        paragraph_index=paragraph.index,
        expected_hops=3,
        generate_response=fake_model,
        path=DATASET_PATH,
    )

    assert received_prompts == [run.prompt]
    assert run.source.unit_id == paragraph.unit_id
    assert run.source.title == paragraph.title
    assert run.source.text == paragraph.text
    assert paragraph.unit_id not in run.prompt
    assert run.extraction.unit_id == paragraph.unit_id
    assert run.extraction.statements == ()
