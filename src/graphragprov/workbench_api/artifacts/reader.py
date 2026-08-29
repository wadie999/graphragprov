"""Read one persisted experiment result through a versioned adapter."""

import json
from pathlib import Path
from typing import cast

from graphragprov.workbench_api.artifacts.current import parse_current
from graphragprov.workbench_api.artifacts.legacy import parse_legacy
from graphragprov.workbench_api.artifacts.types import ArtifactCase


def read_artifact(path: Path) -> ArtifactCase:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"result artifact must contain an object: {path}")
    data = cast(dict[str, object], raw)
    if "outcome" in data:
        return parse_current(path, data)
    if "graph" in data:
        return parse_legacy(path, data)
    raise ValueError(f"unsupported result artifact format: {path}")
