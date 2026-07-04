from pathlib import Path

from pytest import MonkeyPatch

from graphragprov.config import PROJECT_ROOT, musique_dataset_path


def test_default_musique_dataset_path(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("MUSIQUE_DATASET_PATH", raising=False)

    expected = (
        PROJECT_ROOT
        / "external"
        / "benchmarks"
        / "musique"
        / "data"
        / "musique_full_v1.0_dev.jsonl"
    )

    assert musique_dataset_path() == expected


def test_musique_dataset_path_can_be_configured(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "musique.jsonl"
    monkeypatch.setenv("MUSIQUE_DATASET_PATH", str(dataset_path))

    assert musique_dataset_path() == dataset_path.resolve()
