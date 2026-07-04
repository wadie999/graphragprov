import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MUSIQUE_DATASET_PATH = (
    PROJECT_ROOT / "external" / "benchmarks" / "musique" / "data" / "musique_full_v1.0_dev.jsonl"
)


def musique_dataset_path() -> Path:
    """Return the configured MuSiQue development dataset path."""

    value = os.getenv("MUSIQUE_DATASET_PATH")

    if value is None:
        return DEFAULT_MUSIQUE_DATASET_PATH

    return Path(value).expanduser().resolve()
