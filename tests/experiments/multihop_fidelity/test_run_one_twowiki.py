from pathlib import Path

from graphragprov.experiments.multihop_fidelity.config import QueryScope
from graphragprov.experiments.multihop_fidelity.run_one_twowiki import (
    DEFAULT_ARTIFACT_ROOT,
    _run_configuration_payload,
    parse_arguments,
)


def test_parse_arguments_matches_run_one_operational_contract() -> None:
    arguments = parse_arguments(
        (
            "--case-id",
            "twowiki-case",
            "--query-scope",
            "repository",
            "--model",
            "deepseek-test",
            "--max-tokens",
            "4096",
            "--max-source-attempts",
            "4",
            "--max-query-attempts",
            "6",
            "--reuse-llm-checkpoints",
            "--verbose",
        )
    )

    assert arguments.case_id == "twowiki-case"
    assert arguments.query_scope is QueryScope.REPOSITORY
    assert arguments.model == "deepseek-test"
    assert arguments.max_tokens == 4096
    assert arguments.max_source_attempts == 4
    assert arguments.max_query_attempts == 6
    assert arguments.artifacts == DEFAULT_ARTIFACT_ROOT
    assert arguments.reuse_llm_checkpoints is True
    assert arguments.verbose is True


def test_run_configuration_identifies_twowiki_and_reproducibility_inputs(tmp_path: Path) -> None:
    dataset = tmp_path / "twowiki.json"

    arguments = parse_arguments(
        (
            "--case-id",
            "twowiki-case",
            "--dataset-path",
            str(dataset),
            "--artifacts",
            str(tmp_path / "runs"),
        )
    )

    payload = _run_configuration_payload(
        case_id=arguments.case_id, dataset_path=dataset, arguments=arguments
    )

    assert payload["format"] == "multihop-fidelity-h0-collection-v1"
    assert payload["benchmark"] == "2wiki"
    assert payload["case_id"] == "twowiki-case"
    assert payload["dataset_path"] == str(dataset.resolve())
    assert payload["query_scope"] == "support"
    assert payload["graph_origin"] == "reference"
    assert payload["query_origin"] == "reference"
