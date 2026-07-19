"""Persistence boundary for materialized MuSiQue experiments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from graphragprov.experiments.manifest import (
    MusiqueMaterializationCase,
    MusiqueMaterializationManifest,
    load_musique_materialization_manifest,
)

_MANIFEST_FILENAME = "materialization.json"
_EXPERIMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class InvalidExperimentIdError(ValueError):
    """Raised when an experiment identifier is unsafe or malformed."""


class ExperimentNotFoundError(LookupError):
    """Raised when a requested experiment does not exist."""


class ExperimentCaseNotFoundError(LookupError):
    """Raised when a case does not belong to an experiment."""


@dataclass(frozen=True, slots=True)
class StoredMusiqueExperiment:
    """One validated experiment together with its persistence identity."""

    experiment_id: str
    manifest: MusiqueMaterializationManifest

    def list_cases(self) -> tuple[MusiqueMaterializationCase, ...]:
        """Return the benchmark cases recorded by this experiment."""

        return self.manifest.cases

    def get_case(
        self,
        case_id: str,
    ) -> MusiqueMaterializationCase:
        """Return one benchmark case recorded by this experiment."""

        for case in self.manifest.cases:
            if case.case_id == case_id:
                return case

        raise ExperimentCaseNotFoundError(
            f"case does not exist in experiment "
            f"{self.experiment_id}: {case_id}"
        )


class MusiqueExperimentRepository(Protocol):
    """Read boundary for stored MuSiQue materialization experiments."""

    def list_experiments(self) -> tuple[StoredMusiqueExperiment, ...]:
        """Return every stored and validated experiment."""
        ...

    def get_experiment(
        self,
        experiment_id: str,
    ) -> StoredMusiqueExperiment:
        """Return one stored and validated experiment."""
        ...


@dataclass(frozen=True, slots=True)
class FilesystemMusiqueExperimentRepository:
    """Read experiments stored as direct children of one directory."""

    root: Path

    def list_experiments(self) -> tuple[StoredMusiqueExperiment, ...]:
        """Load every direct child containing a materialization manifest."""

        if not self.root.exists():
            return ()

        if not self.root.is_dir():
            raise NotADirectoryError(
                f"experiment root is not a directory: {self.root}"
            )

        experiments: list[StoredMusiqueExperiment] = []

        for experiment_directory in sorted(
            self.root.iterdir(),
            key=lambda path: path.name,
        ):
            if not experiment_directory.is_dir():
                continue

            manifest_path = experiment_directory / _MANIFEST_FILENAME

            if not manifest_path.is_file():
                continue

            experiment_id = validate_experiment_id(
                experiment_directory.name
            )

            experiments.append(
                StoredMusiqueExperiment(
                    experiment_id=experiment_id,
                    manifest=load_musique_materialization_manifest(
                        manifest_path
                    ),
                )
            )

        return tuple(experiments)

    def get_experiment(
        self,
        experiment_id: str,
    ) -> StoredMusiqueExperiment:
        """Load one experiment by its safe directory identifier."""

        validated_id = validate_experiment_id(experiment_id)
        manifest_path = self.root / validated_id / _MANIFEST_FILENAME

        if not manifest_path.is_file():
            raise ExperimentNotFoundError(
                f"experiment does not exist: {validated_id}"
            )

        return StoredMusiqueExperiment(
            experiment_id=validated_id,
            manifest=load_musique_materialization_manifest(
                manifest_path
            ),
        )


def validate_experiment_id(experiment_id: str) -> str:
    """Validate an identifier suitable for paths and HTTP resources."""

    if not _EXPERIMENT_ID_PATTERN.fullmatch(experiment_id):
        raise InvalidExperimentIdError(
            "experiment ID must start with an alphanumeric character "
            "and contain only letters, digits, dots, underscores, or hyphens"
        )

    return experiment_id