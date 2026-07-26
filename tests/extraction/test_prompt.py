import json

from graphragprov.domain.source_unit import SourceUnit
from graphragprov.extraction.prompt import PROMPT_VERSION, build_extraction_prompt

SOURCE = SourceUnit(
    unit_id="u_test_should_not_reach_the_model",
    title="Albert Einstein",
    text="He was born in Ulm on 14 March 1879.",
)


def test_prompt_version_is_stable() -> None:
    assert PROMPT_VERSION == "grounded-rdf-v2"


def test_prompt_rendering_is_deterministic() -> None:
    assert build_extraction_prompt(SOURCE) == build_extraction_prompt(SOURCE)


def test_prompt_contains_exact_title_and_text() -> None:
    prompt = build_extraction_prompt(SOURCE)

    expected_source = json.dumps(
        {"title": SOURCE.title, "text": SOURCE.text}, ensure_ascii=False, indent=2
    )

    assert expected_source in prompt


def test_prompt_does_not_expose_source_unit_id() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert SOURCE.unit_id not in prompt
    assert '"unit_id"' not in prompt


def test_prompt_requests_grounded_json_statements() -> None:
    prompt = build_extraction_prompt(SOURCE)

    for field in (
        '"statements"',
        '"subject"',
        '"predicate"',
        '"object"',
        '"value"',
        '"evidence"',
        '"segment"',
        '"quote"',
        '"occurrence"',
    ):
        assert field in prompt


def test_prompt_does_not_request_reasoning() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert '"reasoning"' not in prompt
    assert "Do not return Markdown" in prompt
    assert "reasoning" in prompt
    assert "code fences" in prompt


def test_prompt_requires_atomic_graph_nodes() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert "A triple is NOT a compressed sentence." in prompt
    assert "Subjects and entity objects must be atomic semantic nodes." in prompt
    assert "Do not use a complete sentence, clause, definition" in prompt


def test_prompt_requires_dimensional_splitting() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert "DIMENSIONAL SPLITTING" in prompt
    assert "Grant Green -> nationality -> American" in prompt
    assert "Grant Green -> occupation -> guitarist" in prompt
    assert "Grant Green -> genre -> jazz" in prompt


def test_prompt_requires_list_distribution() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert "LIST DISTRIBUTION" in prompt
    assert "emit one statement" in prompt
    assert "per object" in prompt
    assert "Full-time employment -> oftenIncludesBenefit -> annual leave" in prompt
    assert "Full-time employment -> oftenIncludesBenefit -> health insurance" in prompt


def test_prompt_separates_entities_from_literals() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert "An object without `datatype` is an entity." in prompt
    assert "Use a literal only for a scalar value." in prompt
    assert "A semantic description, definition, sentence, clause, list" in prompt
    assert '"kind"' not in prompt


def test_prompt_requires_minimal_predicate_triggers() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert "Predicate evidence must be the shortest exact phrase" in prompt
    assert '"does not define"' in prompt
    assert '"commonly require"' in prompt


def test_prompt_requires_local_factual_support() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert "inside the same sentence or local clause" in prompt
    assert "Do not borrow an object mention from an earlier sentence" in prompt
    assert 'The subject is "Companies", not "Full-time employment".' in prompt


def test_prompt_requires_exact_verbatim_grounding() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert "STRICT VERBATIM GROUNDING" in prompt
    assert "exact, non-empty substring" in prompt
    assert "Do not silently normalize evidence quotes." in prompt
    assert "select the occurrence participating" in prompt
    assert "sentence or clause" in prompt


def test_prompt_forbids_automatic_derived_statements() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert "Do not automatically add:" in prompt
    assert "- inverse statements;" in prompt
    assert "- symmetric statements;" in prompt
    assert "- transitive statements;" in prompt
    assert "- ontology-derived statements;" in prompt
    assert "- cross-source statements." in prompt


def test_prompt_contains_few_shot_examples() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert "FEW-SHOT EXAMPLE 1" in prompt
    assert "FEW-SHOT EXAMPLE 2" in prompt
    assert "FEW-SHOT EXAMPLE 3" in prompt

    assert '"value": "Maria Torres"' in prompt
    assert '"value": "supermarket chain"' in prompt
    assert '"value": "annual leave"' in prompt
    assert '"value": "35 to 40 hours per week"' in prompt


def test_prompt_allows_empty_extraction() -> None:
    prompt = build_extraction_prompt(SOURCE)

    assert '"statements": []' in prompt
