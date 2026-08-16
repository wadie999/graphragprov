import json

from graphragprov.domain import SourceUnit
from graphragprov.extraction.prompt import build_extraction_prompt
from graphragprov.extraction.run import (
    GroundedExtractionFailure,
    GroundedExtractionRun,
    run_grounded_extraction,
    run_grounded_extraction_outcome_with_prompt,
    run_grounded_extraction_with_prompt,
)


def evidence(*, segment: str, quote: str, occurrence: int = 1) -> dict[str, object]:
    return {"segment": segment, "quote": quote, "occurrence": occurrence}


def value(text: str, *, segment: str, quote: str, datatype: str | None = None) -> dict[str, object]:
    result: dict[str, object] = {
        "value": text,
        "evidence": [evidence(segment=segment, quote=quote)],
    }

    if datatype is not None:
        result["datatype"] = datatype

    return result


def test_custom_prompt_uses_shared_partial_correction_lifecycle() -> None:
    source = SourceUnit(
        unit_id="u_reference",
        title="When I Was a Boy",
        text="When I Was a Boy is a 1993 album by Jane Siberry.",
    )

    initial_response = json.dumps(
        {
            "statements": [
                {
                    "subject": value("When I Was a Boy", segment="title", quote="When I Was a Boy"),
                    "predicate": value("performer", segment="text", quote="by"),
                    "object": value("Jane Siberry", segment="text", quote="Jane Siberry"),
                },
                {
                    "subject": value("When I Was a Boy", segment="title", quote="When I Was a Boy"),
                    "predicate": value("releaseYear", segment="text", quote="1993"),
                    "object": value("1993", segment="text", quote="1992", datatype="year"),
                },
            ]
        }
    )

    correction_response = json.dumps(
        {
            "statements": [
                {
                    "subject": value("When I Was a Boy", segment="title", quote="When I Was a Boy"),
                    "predicate": value("releaseYear", segment="text", quote="1993"),
                    "object": value("1993", segment="text", quote="1993", datatype="year"),
                }
            ]
        }
    )

    responses = iter((initial_response, correction_response))

    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    reference_prompt = (
        "REFERENCE GRAPH CONSTRUCTION\n\n"
        "Question: What year was When I Was a Boy released?\n"
        "Use JSON grounded extraction."
    )

    run = run_grounded_extraction_with_prompt(
        source, prompt=reference_prompt, generate_response=generate
    )

    assert isinstance(run, GroundedExtractionRun)
    assert run.prompt == reference_prompt

    # The initial valid statement survives; only the invalid one is corrected.
    assert len(run.extraction.statements) == 2

    assert run.correction is not None
    assert run.correction.initial_valid_statement_count == 1
    assert run.correction.corrected_valid_statement_count == 1
    assert run.correction.remaining_rejections == ()

    assert len(run.correction.requested_rejections) == 1
    assert "1992" in run.correction.requested_rejections[0].error_message

    # One privileged extraction call, followed by one targeted correction call.
    assert len(prompts) == 2
    assert prompts[0] == reference_prompt

    assert "Rejected statements and validator errors:" in prompts[1]
    assert '"1992"' in prompts[1]
    assert "Return only corrected replacements" in prompts[1]


def test_custom_prompt_outcome_preserves_provider_failure() -> None:
    source = SourceUnit(unit_id="u_failure", title="Casa Loma", text="Casa Loma is in Toronto.")

    reference_prompt = "REFERENCE GRAPH CONSTRUCTION\nReturn JSON."

    def generate(prompt: str) -> str:
        assert prompt == reference_prompt
        raise RuntimeError("provider unavailable")

    outcome = run_grounded_extraction_outcome_with_prompt(
        source, prompt=reference_prompt, generate_response=generate
    )

    assert isinstance(outcome, GroundedExtractionFailure)

    assert outcome.prompt == reference_prompt
    assert outcome.response is None
    assert outcome.stage == "provider"
    assert outcome.error_type == "RuntimeError"
    assert outcome.error_message == "provider unavailable"


def test_custom_prompt_outcome_preserves_response_validation_failure() -> None:
    source = SourceUnit(
        unit_id="u_invalid_response", title="Casa Loma", text="Casa Loma is in Toronto."
    )

    reference_prompt = "REFERENCE GRAPH CONSTRUCTION\nReturn JSON."

    def generate(prompt: str) -> str:
        assert prompt == reference_prompt
        return "not valid JSON"

    outcome = run_grounded_extraction_outcome_with_prompt(
        source, prompt=reference_prompt, generate_response=generate
    )

    assert isinstance(outcome, GroundedExtractionFailure)

    assert outcome.prompt == reference_prompt
    assert outcome.response == "not valid JSON"
    assert outcome.stage == "response_validation"
    assert outcome.error_type == "ValueError"
    assert "invalid extraction JSON" in outcome.error_message


def test_standard_extraction_still_uses_standard_prompt() -> None:
    source = SourceUnit(unit_id="u_standard", title="Casa Loma", text="Casa Loma is in Toronto.")

    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return '{"statements": []}'

    run = run_grounded_extraction(source, generate)

    assert prompts == [build_extraction_prompt(source)]

    assert run.prompt == build_extraction_prompt(source)
    assert run.extraction.statements == ()
    assert run.correction is None
