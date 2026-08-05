"""Mutable state identifying the experiment currently loaded in GraphDB."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from graphragprov.experiments.manifest import MusiqueMaterializationManifest
from graphragprov.experiments.repository import validate_experiment_id

ACTIVE_EXPERIMENT_FILENAME = "active_experiment.json"
ACTIVE_EXPERIMENT_FORMAT = "musique-active-experiment-v1"


@dataclass(frozen=True, slots=True)
class MusiqueExperimentActivation:
    """Exact materialization currently represented by GraphDB."""

    experiment_id: str
    manifest_created_at: datetime
    activated_at: datetime
    graphdb_base_url: str
    graphdb_repository: str

    def __post_init__(self) -> None:
        validate_experiment_id(self.experiment_id)
        _validate_aware_datetime(self.manifest_created_at, "manifest creation time")
        _validate_aware_datetime(self.activated_at, "activation time")

        if not self.graphdb_base_url.strip():
            raise ValueError("active experiment GraphDB base URL must not be empty")

        if not self.graphdb_repository.strip():
            raise ValueError("active experiment GraphDB repository must not be empty")

    @classmethod
    def from_manifest(
        cls,
        *,
        experiment_id: str,
        manifest: MusiqueMaterializationManifest,
        activated_at: datetime | None = None,
    ) -> MusiqueExperimentActivation:
        """Create activation state for one materialization manifest."""

        return cls(
            experiment_id=experiment_id,
            manifest_created_at=manifest.created_at,
            activated_at=activated_at or datetime.now(UTC),
            graphdb_base_url=manifest.graphdb.base_url,
            graphdb_repository=manifest.graphdb.repository,
        )

    def matches(self, *, experiment_id: str, manifest: MusiqueMaterializationManifest) -> bool:
        """Return whether this marker identifies the exact manifest."""

        return (
            self.experiment_id == experiment_id
            and self.manifest_created_at == manifest.created_at
            and self.graphdb_base_url == manifest.graphdb.base_url
            and self.graphdb_repository == manifest.graphdb.repository
        )

    def to_dict(self) -> dict[str, object]:
        """Return the persistent JSON representation."""

        return {
            "format": ACTIVE_EXPERIMENT_FORMAT,
            "experiment_id": self.experiment_id,
            "manifest_created_at": self.manifest_created_at.isoformat(),
            "activated_at": self.activated_at.isoformat(),
            "graphdb": {"base_url": self.graphdb_base_url, "repository": self.graphdb_repository},
        }

    def to_json(self) -> str:
        """Serialize activation state deterministically."""

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MusiqueExperimentActivation:
        """Parse and validate persisted activation state."""

        required = {"format", "experiment_id", "manifest_created_at", "activated_at", "graphdb"}
        _validate_fields(data, required=required, location="active experiment")

        activation_format = _require_string(data["format"], "active experiment format")

        if activation_format != ACTIVE_EXPERIMENT_FORMAT:
            raise ValueError(f"unsupported active experiment format: {activation_format}")

        graphdb = _require_object(data["graphdb"], "active experiment graphdb")
        _validate_fields(
            graphdb, required={"base_url", "repository"}, location="active experiment graphdb"
        )

        return cls(
            experiment_id=_require_string(data["experiment_id"], "active experiment ID"),
            manifest_created_at=_require_datetime(
                data["manifest_created_at"], "active experiment manifest creation time"
            ),
            activated_at=_require_datetime(
                data["activated_at"], "active experiment activation time"
            ),
            graphdb_base_url=_require_string(
                graphdb["base_url"], "active experiment GraphDB base URL"
            ),
            graphdb_repository=_require_string(
                graphdb["repository"], "active experiment GraphDB repository"
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> MusiqueExperimentActivation:
        """Parse activation state from JSON."""

        try:
            raw_data = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("active experiment contains invalid JSON") from error

        return cls.from_dict(_require_object(raw_data, "active experiment"))


def load_musique_experiment_activation(root: Path) -> MusiqueExperimentActivation | None:
    """Load the active marker, or return None when no experiment is active."""

    path = root / ACTIVE_EXPERIMENT_FILENAME

    if not path.is_file():
        return None

    return MusiqueExperimentActivation.from_json(path.read_text(encoding="utf-8"))


def write_musique_experiment_activation(
    root: Path, activation: MusiqueExperimentActivation
) -> Path:
    """Persist the active marker atomically."""

    root.mkdir(parents=True, exist_ok=True)

    path = root / ACTIVE_EXPERIMENT_FILENAME
    temporary_path = root / f".{ACTIVE_EXPERIMENT_FILENAME}.tmp"

    temporary_path.write_text(activation.to_json() + "\n", encoding="utf-8")
    temporary_path.replace(path)

    return path


def clear_musique_experiment_activation(root: Path) -> bool:
    """Remove the active marker and report whether one existed."""

    path = root / ACTIVE_EXPERIMENT_FILENAME

    if not path.exists():
        return False

    path.unlink()
    return True


def _validate_aware_datetime(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"active experiment {name} must be timezone-aware")


def _validate_fields(data: dict[str, Any], *, required: set[str], location: str) -> None:
    fields = set(data)
    missing = required - fields
    unexpected = fields - required

    if missing:
        raise ValueError(f"{location} is missing field(s): " + ", ".join(sorted(missing)))

    if unexpected:
        raise ValueError(
            f"{location} contains unexpected field(s): " + ", ".join(sorted(unexpected))
        )


def _require_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")

    return cast(dict[str, Any], value)


def _require_string(value: Any, location: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{location} must be a string")

    return value


def _require_datetime(value: Any, location: str) -> datetime:
    text = _require_string(value, location)

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"{location} must be an ISO 8601 date-time") from error

    return parsed
