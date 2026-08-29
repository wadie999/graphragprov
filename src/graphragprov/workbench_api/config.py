"""Load the single TOML configuration for the research workbench."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import cast

from graphragprov.workbench_api.config_models import (
    BenchmarkName,
    ExperimentConfig,
    PlannerConfig,
    ServiceConfig,
    WorkbenchConfig,
)

CONFIG_ENV = "GRAPHRAGPROV_WORKBENCH_CONFIG"


def load_config(path: Path | None = None) -> WorkbenchConfig:
    config_path = (
        path
        or Path(os.getenv(CONFIG_ENV, "workbench.toml"))
    ).resolve()

    data = tomllib.loads(
        config_path.read_text(encoding="utf-8")
    )
    root = config_path.parent

    experiments = tuple(
        _experiment(root, item)
        for item in data.get("experiments", [])
    )

    if not experiments:
        raise ValueError(
            "workbench configuration requires at least one experiment"
        )

    server = _table(data, "server")
    storage = _table(data, "storage")
    services = _table(data, "services")
    planner = _table(data, "planner")

    return WorkbenchConfig(
        root=root,
        state_dir=_resolve(
            root,
            storage.get("state_dir", ".workbench"),
        ),
        frontend_dist=_resolve(
            root,
            storage.get(
                "frontend_dist",
                "frontend/dist",
            ),
        ),
        host=str(
            server.get("host", "127.0.0.1")
        ),
        port=_int(
            server.get("port", 8080),
            "server.port",
        ),
        frontend_dev_port=_int(
            server.get(
                "frontend_dev_port",
                5173,
            ),
            "server.frontend_dev_port",
        ),
        graphdb=_service(
            _nested(services, "graphdb"),
            require_repository=True,
        ),
        npcs=_service(
            _nested(services, "npcs"),
            require_repository=False,
        ),
        planner=PlannerConfig(
            model=str(
                planner.get(
                    "model",
                    "deepseek-v4-flash",
                )
            ),
            max_tokens=_int(
                planner.get(
                    "max_tokens",
                    4096,
                ),
                "planner.max_tokens",
            ),
            timeout_seconds=_float(
                planner.get(
                    "timeout_seconds",
                    60.0,
                ),
                "planner.timeout_seconds",
            ),
            api_key_env=str(
                planner.get(
                    "api_key_env",
                    "DEEPSEEK_API_KEY",
                )
            ),
        ),
        experiments=experiments,
    )


def _experiment(
    root: Path,
    item: dict[str, object],
) -> ExperimentConfig:
    benchmark = str(item["benchmark"])

    if benchmark not in {
        "musique",
        "twowiki",
    }:
        raise ValueError(
            f"unsupported benchmark: {benchmark}"
        )

    return ExperimentConfig(
        experiment_id=str(item["id"]),
        label=str(
            item.get("label", item["id"])
        ),
        benchmark=cast(
            BenchmarkName,
            benchmark,
        ),
        path=_resolve(
            root,
            item["path"],
        ),
        scope=str(
            item.get("scope", "support")
        ),
        cohort_path=_optional_path(
            root,
            item.get("cohort_path"),
        ),
        dataset_path=_optional_path(
            root,
            item.get("dataset_path"),
        ),
    )


def _service(
    data: dict[str, object],
    *,
    require_repository: bool,
) -> ServiceConfig:
    repository = data.get("repository")

    if require_repository and not repository:
        raise ValueError(
            "GraphDB repository must be configured"
        )

    return ServiceConfig(
        base_url=str(
            data.get("base_url", "")
        ),
        timeout_seconds=_float(
            data.get(
                "timeout_seconds",
                30.0,
            ),
            "service.timeout_seconds",
        ),
        repository=(
            str(repository)
            if repository
            else None
        ),
    )


def _int(
    value: object,
    name: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, str))
    ):
        raise ValueError(
            f"{name} must be an integer"
        )

    try:
        return int(value)
    except ValueError as error:
        raise ValueError(
            f"{name} must be an integer"
        ) from error


def _float(
    value: object,
    name: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (int, float, str),
        )
    ):
        raise ValueError(
            f"{name} must be numeric"
        )

    try:
        return float(value)
    except ValueError as error:
        raise ValueError(
            f"{name} must be numeric"
        ) from error


def _resolve(
    root: Path,
    value: object,
) -> Path:
    path = Path(str(value))

    if path.is_absolute():
        return path

    return (root / path).resolve()


def _optional_path(
    root: Path,
    value: object,
) -> Path | None:
    if value in {None, ""}:
        return None

    return _resolve(root, value)


def _table(
    data: dict[str, object],
    key: str,
) -> dict[str, object]:
    value = data.get(key, {})

    if not isinstance(value, dict):
        return {}

    return cast(
        dict[str, object],
        value,
    )


def _nested(
    data: dict[str, object],
    key: str,
) -> dict[str, object]:
    return _table(data, key)


__all__ = [
    "CONFIG_ENV",
    "ExperimentConfig",
    "PlannerConfig",
    "ServiceConfig",
    "WorkbenchConfig",
    "load_config",
]