import json
from pathlib import Path

import pytest

from graphragprov.experiments.multihop_fidelity.run_one import (
    ensure_result_artifact_target,
    read_result_artifact_status,
)


def _write_result(path: Path, *, status: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(json.dumps({"outcome": {"status": status}}), encoding="utf-8")


def test_complete_result_is_never_overwritten(tmp_path: Path) -> None:
    result = tmp_path / "result.json"

    _write_result(result, status="complete")

    assert read_result_artifact_status(result) == "complete"

    with pytest.raises(FileExistsError, match="completed result artifact"):
        ensure_result_artifact_target(result, reuse_llm_checkpoints=True)


def test_operational_failure_can_resume_only_explicitly(tmp_path: Path) -> None:
    result = tmp_path / "result.json"

    _write_result(result, status="operational_failure")

    assert read_result_artifact_status(result) == "operational_failure"

    with pytest.raises(FileExistsError, match="failed result artifact"):
        ensure_result_artifact_target(result, reuse_llm_checkpoints=False)

    ensure_result_artifact_target(result, reuse_llm_checkpoints=True)


def test_missing_result_is_available(tmp_path: Path) -> None:
    ensure_result_artifact_target(tmp_path / "missing.json", reuse_llm_checkpoints=False)


def test_unknown_result_status_is_rejected(tmp_path: Path) -> None:
    result = tmp_path / "result.json"

    _write_result(result, status="mystery")

    with pytest.raises(ValueError, match="unknown outcome status"):
        read_result_artifact_status(result)
