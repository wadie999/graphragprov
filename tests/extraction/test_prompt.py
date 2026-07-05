import json

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.prompt import (
    PROMPT_VERSION,
    build_extraction_prompt,
)

SOURCE = SourceUnit(
    unit_id="u_test_should_not_reach_the_model",
    title="Albert Einstein",
    text="He was born in Ulm on 14 March 1879.",
)


def test_prompt_version_is_stable() -> None:
    assert PROMPT_VERSION == "grounded-rdf-v1"


def test_prompt_rendering_is_deterministic() -> None:
    assert build_extraction_prompt(SOURCE) == build_extraction_prompt(SOURCE)


def test_prompt_contains_exact_title_and_text() -> None:
    prompt = build_extraction_prompt(SOURCE)

    expected_source = json.dumps(
        {
            "title": SOURCE.title,
            "text": SOURCE.text,
        },
        ensure_ascii=False,
        indent=2,
    )

    assert expected_source in prompt


def test_prompt_does_not_expose_source_unit_id() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert SOURCE.unit_id not in prompt
    assert '"unit_id"' not in prompt


def test_prompt_requests_grounded_json_statements() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert '"statements"' in prompt
    assert '"subject"' in prompt
    assert '"predicate"' in prompt
    assert '"object"' in prompt
    assert '"value"' in prompt
    assert '"evidence"' in prompt
    assert '"segment"' in prompt
    assert '"quote"' in prompt
    assert '"occurrence"' in prompt


def test_prompt_does_not_request_reasoning() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert '"reasoning"' not in prompt
    assert "Do not return Markdown, explanations, reasoning" in prompt


def test_prompt_forbids_automatic_inverse_statements() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert "Do not automatically generate:" in prompt
    assert "inverse statements" in prompt
    assert "hasInstance" in prompt


def test_prompt_allows_empty_extraction() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert '"statements": []' in prompt


def test_prompt_infers_object_kind_from_datatype() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert '"kind"' not in prompt
    assert "An object without a datatype is an entity." in prompt
    assert "An object with a datatype is a scalar literal." in prompt
