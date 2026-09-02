"""Persistence and graph construction for user-authored workbench experiments."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

from graphragprov.domain import SourceUnit
from graphragprov.extraction.artifacts import (
    load_grounded_extraction_run,
    save_grounded_extraction_run,
)
from graphragprov.extraction.prompt import SYSTEM_PROMPT, build_extraction_prompt
from graphragprov.extraction.run import (
    GroundedExtractionFailure,
    GroundedExtractionRun,
    run_grounded_extraction_outcome_with_prompt,
)
from graphragprov.hashing import source_unit_id
from graphragprov.providers.deepseek import deepseek_generator
from graphragprov.qaagent import observe_semantic_triples
from graphragprov.workbench_api.artifacts import ArtifactCase
from graphragprov.workbench_api.config import PlannerConfig
from graphragprov.workbench_api.models.authoring import WorkspaceSourceInput
from graphragprov.workbench_api.models.catalog import CaseSummary, ExperimentSummary
from graphragprov.workbench_api.models.metrics import MetricCollection
from graphragprov.workbench_api.models.snapshot import CaseSnapshot
from graphragprov.workbench_api.models.source import SourceUnitView
from graphragprov.workbench_api.services.graph_projection import project_graph
from graphragprov.workbench_api.services.source_projection import project_sources
from graphragprov.workbench_api.services.workspace import GraphWorkspaceManager

BuildMode = Literal["source_only", "question_conditioned"]

_EXPERIMENT_FORMAT = "graphragprov-workspace-experiment-v1"
_CASE_FORMAT = "graphragprov-workspace-case-v1"
_BUILD_FORMAT = "graphragprov-workspace-build-v1"


class UserWorkspaceService:
    """Own user-created experiments under the workbench state directory."""

    def __init__(
        self, root: Path, planner_config: PlannerConfig, graph_workspace: GraphWorkspaceManager
    ) -> None:
        self._root = root / "experiments"
        self._root.mkdir(parents=True, exist_ok=True)
        self._planner_config = planner_config
        self._graph_workspace = graph_workspace

    def experiments(self) -> tuple[ExperimentSummary, ...]:
        items: list[ExperimentSummary] = []
        for directory in sorted(self._root.iterdir()) if self._root.exists() else ():
            manifest = directory / "experiment.json"
            if not directory.is_dir() or not manifest.exists():
                continue
            experiment = self._read_object(manifest)
            experiment_id = self._string(experiment.get("experiment_id"), "experiment_id")
            cases = self.cases(experiment_id)
            items.append(
                ExperimentSummary(
                    experiment_id=experiment_id,
                    label=self._string(experiment.get("name"), "name"),
                    benchmark="custom",
                    origin="workspace",
                    case_count=len(cases),
                    available_case_count=sum(item.graph_available for item in cases),
                )
            )
        return tuple(items)

    def create_experiment(self, name: str) -> ExperimentSummary:
        clean_name = self._clean_name(name)
        experiment_id = f"user-{uuid4().hex[:10]}"
        directory = self._experiment_dir(experiment_id)
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "cases").mkdir()

        self._write_json(
            directory / "experiment.json",
            {
                "format": _EXPERIMENT_FORMAT,
                "experiment_id": experiment_id,
                "name": clean_name,
                "created_at": self._now(),
            },
        )

        return ExperimentSummary(
            experiment_id=experiment_id,
            label=clean_name,
            benchmark="custom",
            origin="workspace",
            case_count=0,
            available_case_count=0,
        )

    def owns_experiment(self, experiment_id: str) -> bool:
        return (self._experiment_dir(experiment_id) / "experiment.json").exists()

    def cases(self, experiment_id: str) -> tuple[CaseSummary, ...]:
        self._experiment(experiment_id)

        case_root = self._experiment_dir(experiment_id) / "cases"
        items: list[CaseSummary] = []

        for directory in sorted(case_root.iterdir()) if case_root.exists() else ():
            manifest = directory / "case.json"
            if directory.is_dir() and manifest.exists():
                items.append(self._case_summary(self._read_object(manifest)))

        return tuple(items)

    def create_case(self, experiment_id: str, name: str) -> CaseSummary:
        self._experiment(experiment_id)

        clean_name = self._clean_name(name)
        case_id = f"case-{uuid4().hex[:10]}"

        directory = self._case_dir(experiment_id, case_id)
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "builds").mkdir()

        case = {
            "format": _CASE_FORMAT,
            "experiment_id": experiment_id,
            "case_id": case_id,
            "name": clean_name,
            "created_at": self._now(),
            "updated_at": self._now(),
            "dirty": True,
            "latest_build_id": None,
            "sources": [],
        }

        self._write_json(directory / "case.json", case)

        return self._case_summary(case)

    def update_sources(
        self, experiment_id: str, case_id: str, sources: tuple[WorkspaceSourceInput, ...]
    ) -> CaseSnapshot:
        case = self._case(experiment_id, case_id)

        serialized = [
            {"title": source.title.strip(), "text": source.text.strip()} for source in sources
        ]

        if not serialized:
            raise ValueError("a workspace case requires at least one paragraph")

        case["sources"] = serialized
        case["dirty"] = True
        case["updated_at"] = self._now()

        self._write_case(experiment_id, case_id, case)

        return self._draft_snapshot(case)

    def build_case(
        self, experiment_id: str, case_id: str, *, mode: BuildMode, question: str | None
    ) -> CaseSnapshot:
        case = self._case(experiment_id, case_id)

        source_payloads = self._source_payloads(case)

        if not source_payloads:
            raise ValueError("add at least one paragraph before building the graph")

        clean_question = question.strip() if question is not None else None

        if mode == "question_conditioned" and not clean_question:
            raise ValueError("question-conditioned construction requires a question")

        api_key = os.getenv(self._planner_config.api_key_env, "")

        if not api_key.strip():
            raise RuntimeError(
                "missing extraction API key environment variable "
                f"{self._planner_config.api_key_env}"
            )

        generate = deepseek_generator(
            api_key=api_key,
            model=self._planner_config.model,
            max_tokens=max(self._planner_config.max_tokens, 16_384),
            timeout_seconds=self._planner_config.timeout_seconds,
        )

        build_id = f"build-{uuid4().hex[:12]}"

        build_dir = self._build_dir(experiment_id, case_id, build_id)

        extraction_root = build_dir / "extractions"
        extraction_root.mkdir(parents=True, exist_ok=False)

        runs: list[GroundedExtractionRun] = []
        immutable_sources: list[dict[str, object]] = []

        for ordinal, payload in enumerate(source_payloads, start=1):
            source = self._source_unit(payload)

            prompt = self._build_prompt(source, mode=mode, question=clean_question)

            outcome = run_grounded_extraction_outcome_with_prompt(
                source, prompt=prompt, generate_response=generate
            )

            if isinstance(outcome, GroundedExtractionFailure):
                raise RuntimeError(
                    f"paragraph {ordinal} extraction failed at "
                    f"{outcome.stage}: "
                    f"{outcome.error_type}: "
                    f"{outcome.error_message}"
                )

            save_grounded_extraction_run(
                outcome, extraction_root / source.unit_id, expected_prompt=prompt
            )

            runs.append(outcome)

            immutable_sources.append(
                {
                    "ordinal": ordinal,
                    "unit_id": source.unit_id,
                    "title": source.title,
                    "text": source.text,
                }
            )

        source_ids = tuple(run.source.unit_id for run in runs)

        temporary_artifact = self._artifact(
            result_path=build_dir / "build.json",
            case_id=case_id,
            question=clean_question or "",
            source_ids=source_ids,
            runs=tuple(runs),
            observation=None,
            sources=immutable_sources,
        )

        with self._graph_workspace.materialized(temporary_artifact) as graphdb:
            observation = observe_semantic_triples(graphdb=graphdb, source_unit_ids=source_ids)

        if not observation.triples:
            raise ValueError("graph construction produced no semantic RDF triples")

        build: dict[str, object] = {
            "format": _BUILD_FORMAT,
            "experiment_id": experiment_id,
            "case_id": case_id,
            "build_id": build_id,
            "mode": mode,
            "question": clean_question,
            "model": self._planner_config.model,
            "created_at": self._now(),
            "sources": immutable_sources,
            "observation": observation.to_dict(),
        }

        self._write_json(build_dir / "build.json", build)

        case["latest_build_id"] = build_id
        case["dirty"] = False
        case["updated_at"] = self._now()

        self._write_case(experiment_id, case_id, case)

        return self._build_snapshot(case, build, tuple(runs))

    def snapshot_for(self, experiment_id: str, case_id: str) -> CaseSnapshot:
        case = self._case(experiment_id, case_id)

        latest = case.get("latest_build_id")

        if case.get("dirty") is True or not isinstance(latest, str) or not latest:
            return self._draft_snapshot(case)

        return self._snapshot_from_build(experiment_id, case_id, latest)

    def snapshot(self, snapshot_id: str) -> CaseSnapshot:
        located = self._find_snapshot(snapshot_id)

        if located is None:
            raise KeyError(f"unknown workspace snapshot: {snapshot_id}")

        experiment_id, case_id, build_id = located

        if build_id is None:
            return self._draft_snapshot(self._case(experiment_id, case_id))

        return self._snapshot_from_build(experiment_id, case_id, build_id)

    def artifact(self, snapshot_id: str) -> ArtifactCase:
        located = self._find_snapshot(snapshot_id)

        if located is None:
            raise KeyError(f"unknown workspace snapshot: {snapshot_id}")

        experiment_id, case_id, build_id = located

        if build_id is None:
            raise ValueError("draft workspace case has no frozen graph artifact")

        build = self._build(experiment_id, case_id, build_id)

        runs = self._load_runs(experiment_id, case_id, build_id, build)

        return self._artifact_from_build(experiment_id, case_id, build_id, build, runs)

    def _case_summary(self, case: dict[str, object]) -> CaseSummary:
        experiment_id = self._string(case.get("experiment_id"), "experiment_id")

        case_id = self._string(case.get("case_id"), "case_id")

        dirty = case.get("dirty") is True
        latest = case.get("latest_build_id")

        graph_available = isinstance(latest, str) and bool(latest) and not dirty

        snapshot_id = (
            self._build_snapshot_id(experiment_id, case_id, latest)
            if graph_available and isinstance(latest, str)
            else self._draft_snapshot_id(experiment_id, case_id)
        )

        question = ""

        if graph_available and isinstance(latest, str):
            build = self._build(experiment_id, case_id, latest)

            raw_question = build.get("question")

            question = raw_question if isinstance(raw_question, str) else ""

        return CaseSummary(
            experiment_id=experiment_id,
            case_id=case_id,
            label=self._string(case.get("name"), "name"),
            snapshot_id=snapshot_id,
            origin="workspace",
            question=question,
            expected_answer="",
            hop_count=None,
            artifact_status=("complete" if graph_available else "draft"),
            graph_available=graph_available,
            provenance_available=False,
        )

    def _draft_snapshot(self, case: dict[str, object]) -> CaseSnapshot:
        experiment_id = self._string(case.get("experiment_id"), "experiment_id")

        case_id = self._string(case.get("case_id"), "case_id")

        sources = tuple(
            SourceUnitView(
                source_id=source_unit_id(title=payload["title"], text=payload["text"]),
                ordinal=index,
                paragraph_index=index,
                title=payload["title"],
                text=payload["text"],
                statement_count=0,
            )
            for index, payload in enumerate(self._source_payloads(case), start=1)
        )

        return CaseSnapshot(
            snapshot_id=self._draft_snapshot_id(experiment_id, case_id),
            experiment_id=experiment_id,
            case_id=case_id,
            case_label=self._string(case.get("name"), "name"),
            origin="workspace",
            artifact_status="draft",
            failure_stage=None,
            failure_message=None,
            benchmark=None,
            sources=sources,
            graph=None,
            metrics=MetricCollection(items=()),
            reference_run=None,
        )

    def _snapshot_from_build(self, experiment_id: str, case_id: str, build_id: str) -> CaseSnapshot:
        case = self._case(experiment_id, case_id)

        build = self._build(experiment_id, case_id, build_id)

        runs = self._load_runs(experiment_id, case_id, build_id, build)

        return self._build_snapshot(case, build, runs)

    def _build_snapshot(
        self,
        case: dict[str, object],
        build: dict[str, object],
        runs: tuple[GroundedExtractionRun, ...],
    ) -> CaseSnapshot:
        experiment_id = self._string(case.get("experiment_id"), "experiment_id")

        case_id = self._string(case.get("case_id"), "case_id")

        build_id = self._string(build.get("build_id"), "build_id")

        snapshot_id = self._build_snapshot_id(experiment_id, case_id, build_id)

        artifact = self._artifact_from_build(experiment_id, case_id, build_id, build, runs)

        mode = self._build_mode(build.get("mode"))

        raw_question = build.get("question")

        question = raw_question if isinstance(raw_question, str) and raw_question.strip() else None

        return CaseSnapshot(
            snapshot_id=snapshot_id,
            experiment_id=experiment_id,
            case_id=case_id,
            case_label=self._string(case.get("name"), "name"),
            origin="workspace",
            artifact_status="complete",
            failure_stage=None,
            failure_message=None,
            build_id=build_id,
            build_mode=mode,
            build_question=question,
            benchmark=None,
            sources=project_sources(artifact),
            graph=project_graph(snapshot_id, artifact),
            metrics=MetricCollection(items=()),
            reference_run=None,
        )

    def _artifact_from_build(
        self,
        experiment_id: str,
        case_id: str,
        build_id: str,
        build: dict[str, object],
        runs: tuple[GroundedExtractionRun, ...],
    ) -> ArtifactCase:
        source_ids = tuple(run.source.unit_id for run in runs)

        sources = self._build_sources(build)

        raw_question = build.get("question")

        question = raw_question if isinstance(raw_question, str) else ""

        observation = build.get("observation")

        if not isinstance(observation, dict):
            raise ValueError("workspace build observation must be an object")

        return self._artifact(
            result_path=(self._build_dir(experiment_id, case_id, build_id) / "build.json"),
            case_id=case_id,
            question=question,
            source_ids=source_ids,
            runs=runs,
            observation=cast(dict[str, object], observation),
            sources=sources,
        )

    @staticmethod
    def _artifact(
        *,
        result_path: Path,
        case_id: str,
        question: str,
        source_ids: tuple[str, ...],
        runs: tuple[GroundedExtractionRun, ...],
        observation: dict[str, object] | None,
        sources: list[dict[str, object]],
    ) -> ArtifactCase:
        measurements: dict[str, object] = {
            "sources": [
                {"unit_id": item["unit_id"], "paragraph_index": item["ordinal"]} for item in sources
            ]
        }

        return ArtifactCase(
            result_path=result_path,
            case_id=case_id,
            question=question,
            expected_answer="",
            hop_count=1,
            status=("complete" if observation is not None else "building"),
            failure_stage=None,
            failure_message=None,
            support_source_ids=source_ids,
            extraction_runs=runs,
            observation=observation,
            extraction_measurements=measurements,
            graph_measurements=None,
            query_attempts=(),
            final_provenance=None,
            raw={},
        )

    def _load_runs(
        self, experiment_id: str, case_id: str, build_id: str, build: dict[str, object]
    ) -> tuple[GroundedExtractionRun, ...]:
        extraction_root = self._build_dir(experiment_id, case_id, build_id) / "extractions"

        runs: list[GroundedExtractionRun] = []

        for source_data in self._build_sources(build):
            source = SourceUnit(
                unit_id=self._string(source_data.get("unit_id"), "source.unit_id"),
                title=self._string(source_data.get("title"), "source.title"),
                text=self._string(source_data.get("text"), "source.text"),
            )

            runs.append(load_grounded_extraction_run(source, extraction_root / source.unit_id))

        return tuple(runs)

    @staticmethod
    def _build_prompt(source: SourceUnit, *, mode: BuildMode, question: str | None) -> str:
        if mode == "source_only":
            return build_extraction_prompt(source)

        assert question is not None

        source_json = json.dumps(
            {"title": source.title, "text": source.text}, ensure_ascii=False, indent=2
        )

        context = "\n".join(
            [
                "QUESTION-CONDITIONED GRAPH CONSTRUCTION",
                "",
                ("The graph will later be queried for the following natural-language question:"),
                question,
                "",
                ("Use the question only as semantic coordination context."),
                ("Extract all useful explicit atomic facts from the CURRENT SOURCE."),
                ("Do not use the question as textual evidence and do not invent missing facts."),
                (
                    "Every subject, predicate, and object must still "
                    "cite exact evidence from the CURRENT SOURCE."
                ),
            ]
        )

        return f"{SYSTEM_PROMPT}\n\n{context}\n\nSOURCE UNIT TO EXTRACT\n\n{source_json}\n"

    def _find_snapshot(self, snapshot_id: str) -> tuple[str, str, str | None] | None:
        for experiment in self.experiments():
            for case in self.cases(experiment.experiment_id):
                draft_id = self._draft_snapshot_id(experiment.experiment_id, case.case_id)

                if snapshot_id == draft_id:
                    return (experiment.experiment_id, case.case_id, None)

                case_data = self._case(experiment.experiment_id, case.case_id)

                case_dir = self._case_dir(experiment.experiment_id, case.case_id)

                build_root = case_dir / "builds"

                for directory in build_root.iterdir() if build_root.exists() else ():
                    if not directory.is_dir():
                        continue

                    build_id = directory.name

                    if snapshot_id == self._build_snapshot_id(
                        experiment.experiment_id, case.case_id, build_id
                    ):
                        return (experiment.experiment_id, case.case_id, build_id)

                latest = case_data.get("latest_build_id")

                if isinstance(latest, str) and snapshot_id == self._build_snapshot_id(
                    experiment.experiment_id, case.case_id, latest
                ):
                    return (experiment.experiment_id, case.case_id, latest)

        return None

    def _experiment(self, experiment_id: str) -> dict[str, object]:
        path = self._experiment_dir(experiment_id) / "experiment.json"

        if not path.exists():
            raise KeyError(f"unknown workspace experiment: {experiment_id}")

        value = self._read_object(path)

        if value.get("format") != _EXPERIMENT_FORMAT:
            raise ValueError("unsupported workspace experiment format")

        return value

    def _case(self, experiment_id: str, case_id: str) -> dict[str, object]:
        self._experiment(experiment_id)

        path = self._case_dir(experiment_id, case_id) / "case.json"

        if not path.exists():
            raise KeyError(f"unknown workspace case: {experiment_id}/{case_id}")

        value = self._read_object(path)

        if value.get("format") != _CASE_FORMAT:
            raise ValueError("unsupported workspace case format")

        return value

    def _build(self, experiment_id: str, case_id: str, build_id: str) -> dict[str, object]:
        path = self._build_dir(experiment_id, case_id, build_id) / "build.json"

        if not path.exists():
            raise KeyError(f"unknown workspace build: {build_id}")

        value = self._read_object(path)

        if value.get("format") != _BUILD_FORMAT:
            raise ValueError("unsupported workspace build format")

        return value

    def _write_case(self, experiment_id: str, case_id: str, case: dict[str, object]) -> None:
        self._write_json((self._case_dir(experiment_id, case_id) / "case.json"), case)

    @staticmethod
    def _source_unit(payload: dict[str, str]) -> SourceUnit:
        return SourceUnit(
            unit_id=source_unit_id(title=payload["title"], text=payload["text"]),
            title=payload["title"],
            text=payload["text"],
        )

    @staticmethod
    def _source_payloads(case: dict[str, object]) -> list[dict[str, str]]:
        raw = case.get("sources")

        if not isinstance(raw, list):
            raise ValueError("workspace case sources must be a list")

        result: list[dict[str, str]] = []

        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(f"workspace source {index} must be an object")

            title = item.get("title")
            text = item.get("text")

            if not isinstance(title, str) or not isinstance(text, str):
                raise ValueError(f"workspace source {index} requires title and text strings")

            result.append({"title": title, "text": text})

        return result

    @staticmethod
    def _build_sources(build: dict[str, object]) -> list[dict[str, object]]:
        raw = build.get("sources")

        if not isinstance(raw, list):
            raise ValueError("workspace build sources must be a list")

        result: list[dict[str, object]] = []

        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("workspace build source must be an object")

            result.append(cast(dict[str, object], item))

        return result

    @staticmethod
    def _build_mode(value: object) -> BuildMode:
        if value not in {"source_only", "question_conditioned"}:
            raise ValueError("workspace build has invalid construction mode")

        return cast(BuildMode, value)

    @staticmethod
    def _clean_name(name: str) -> str:
        clean = " ".join(name.split())

        if not clean:
            raise ValueError("name must not be empty")

        return clean

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _experiment_dir(self, experiment_id: str) -> Path:
        return self._root / experiment_id

    def _case_dir(self, experiment_id: str, case_id: str) -> Path:
        return self._experiment_dir(experiment_id) / "cases" / case_id

    def _build_dir(self, experiment_id: str, case_id: str, build_id: str) -> Path:
        return self._case_dir(experiment_id, case_id) / "builds" / build_id

    @staticmethod
    def _draft_snapshot_id(experiment_id: str, case_id: str) -> str:
        return f"workspace-draft--{experiment_id}--{case_id}"

    @staticmethod
    def _build_snapshot_id(experiment_id: str, case_id: str, build_id: str) -> str:
        return f"workspace-build--{experiment_id}--{case_id}--{build_id}"

    @staticmethod
    def _write_json(path: Path, data: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        temporary = path.with_suffix(path.suffix + ".tmp")

        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        temporary.replace(path)

    @staticmethod
    def _read_object(path: Path) -> dict[str, object]:
        try:
            decoded: Any = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid workspace JSON: {path}") from error

        if not isinstance(decoded, dict):
            raise ValueError(f"workspace JSON must contain an object: {path}")

        return cast(dict[str, object], decoded)

    @staticmethod
    def _string(value: object, name: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"workspace field {name} must be a string")

        return value
