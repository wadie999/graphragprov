import json

from graphragprov.domain import SourceUnit
from graphragprov.extraction.run import run_grounded_extraction

SOURCE = SourceUnit(
    unit_id="u_system_owned",
    title="Albert Einstein",
    text="He was born in Ulm.",
)


MODEL_RESPONSE = json.dumps(
    {
        "statements": [
            {
                "subject": {
                    "value": "Albert Einstein",
                    "evidence": [
                        {
                            "segment": "title",
                            "quote": "Albert Einstein",
                            "occurrence": 1,
                        },
                        {
                            "segment": "text",
                            "quote": "He",
                            "occurrence": 1,
                        },
                    ],
                },
                "predicate": {
                    "value": "bornIn",
                    "evidence": [
                        {
                            "segment": "text",
                            "quote": "born in",
                            "occurrence": 1,
                        }
                    ],
                },
                "object": {
                    "value": "Ulm",
                    "evidence": [
                        {
                            "segment": "text",
                            "quote": "Ulm",
                            "occurrence": 1,
                        }
                    ],
                },
            }
        ]
    }
)


def test_runs_one_grounded_extraction() -> None:
    received_prompts: list[str] = []

    def fake_model(prompt: str) -> str:
        received_prompts.append(prompt)
        return MODEL_RESPONSE

    run = run_grounded_extraction(
        SOURCE,
        generate_response=fake_model,
    )

    assert received_prompts == [run.prompt]
    assert SOURCE.title in run.prompt
    assert SOURCE.text in run.prompt
    assert SOURCE.unit_id not in run.prompt

    assert run.source == SOURCE
    assert run.response == MODEL_RESPONSE
    assert run.extraction.unit_id == SOURCE.unit_id

    statement = run.extraction.statements[0]

    assert statement.subject.value == "Albert Einstein"
    assert statement.predicate.value == "bornIn"
    assert statement.object.value == "Ulm"
    assert statement.object.evidence[0].start == 15
    assert statement.object.evidence[0].end == 18
