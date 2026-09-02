"""Construction of immutable case snapshots from curated and workspace artifacts."""

from graphragprov.workbench_api.artifacts import ArtifactCase
from graphragprov.workbench_api.models.catalog import CaseSummary, ExperimentSummary
from graphragprov.workbench_api.models.snapshot import CaseSnapshot
from graphragprov.workbench_api.services.benchmark import BenchmarkService
from graphragprov.workbench_api.services.catalog import CaseLocator, ExperimentCatalog
from graphragprov.workbench_api.services.graph_projection import project_graph
from graphragprov.workbench_api.services.metrics import project_metrics
from graphragprov.workbench_api.services.reference_run import project_reference_run
from graphragprov.workbench_api.services.source_projection import project_sources
from graphragprov.workbench_api.services.user_workspace import UserWorkspaceService


class SnapshotService:
    def __init__(
        self,
        catalog: ExperimentCatalog,
        benchmarks: BenchmarkService,
        user_workspace: UserWorkspaceService,
    ) -> None:
        self._catalog = catalog
        self._benchmarks = benchmarks
        self._user_workspace = user_workspace

    def experiments(self) -> tuple[ExperimentSummary, ...]:
        items: list[ExperimentSummary] = []

        for experiment in self._catalog.experiments():
            locators = self._catalog.cases(
                experiment.experiment_id
            )

            available = sum(
                locator.result_path.exists()
                for locator in locators
            )

            items.append(
                ExperimentSummary(
                    experiment_id=experiment.experiment_id,
                    label=experiment.label,
                    benchmark=experiment.benchmark,
                    origin="curated",
                    case_count=len(locators),
                    available_case_count=available,
                )
            )

        items.extend(
            self._user_workspace.experiments()
        )

        return tuple(items)

    def cases(
        self,
        experiment_id: str,
    ) -> tuple[CaseSummary, ...]:
        if self._user_workspace.owns_experiment(
            experiment_id
        ):
            return self._user_workspace.cases(
                experiment_id
            )

        return tuple(
            self._case_summary(locator)
            for locator in self._catalog.cases(
                experiment_id
            )
        )

    def case(
        self,
        experiment_id: str,
        case_id: str,
    ) -> CaseSummary:
        for item in self.cases(
            experiment_id
        ):
            if item.case_id == case_id:
                return item

        raise KeyError(
            f"unknown case: {experiment_id}/{case_id}"
        )

    def snapshot(
        self,
        snapshot_id: str,
    ) -> CaseSnapshot:
        if snapshot_id.startswith(
            "workspace-"
        ):
            return self._user_workspace.snapshot(
                snapshot_id
            )

        return self._snapshot(
            self._catalog.locate_snapshot(
                snapshot_id
            )
        )

    def snapshot_for(
        self,
        experiment_id: str,
        case_id: str,
    ) -> CaseSnapshot:
        if self._user_workspace.owns_experiment(
            experiment_id
        ):
            return self._user_workspace.snapshot_for(
                experiment_id,
                case_id,
            )

        return self._snapshot(
            self._catalog.locate(
                experiment_id,
                case_id,
            )
        )

    def artifact(
        self,
        snapshot_id: str,
    ) -> ArtifactCase:
        if snapshot_id.startswith(
            "workspace-"
        ):
            return self._user_workspace.artifact(
                snapshot_id
            )

        locator = self._catalog.locate_snapshot(
            snapshot_id
        )

        return self._catalog.read(
            locator
        )

    def _case_summary(
        self,
        locator: CaseLocator,
    ) -> CaseSummary:
        if not locator.result_path.exists():
            return CaseSummary(
                experiment_id=locator.experiment.experiment_id,
                case_id=locator.case_id,
                label=locator.case_id,
                snapshot_id=locator.snapshot_id,
                origin="curated",
                question="Artifact unavailable",
                expected_answer="",
                hop_count=0,
                artifact_status="missing",
                graph_available=False,
                provenance_available=False,
            )

        artifact = self._catalog.read(
            locator
        )

        return CaseSummary(
            experiment_id=locator.experiment.experiment_id,
            case_id=artifact.case_id,
            label=artifact.case_id,
            snapshot_id=locator.snapshot_id,
            origin="curated",
            question=artifact.question,
            expected_answer=artifact.expected_answer,
            hop_count=artifact.hop_count,
            artifact_status=artifact.status,
            graph_available=artifact.observation is not None,
            provenance_available=(
                artifact.final_provenance is not None
            ),
        )

    def _snapshot(
        self,
        locator: CaseLocator,
    ) -> CaseSnapshot:
        artifact = self._catalog.read(
            locator
        )

        graph = project_graph(
            locator.snapshot_id,
            artifact,
        )

        return CaseSnapshot(
            snapshot_id=locator.snapshot_id,
            experiment_id=locator.experiment.experiment_id,
            case_id=artifact.case_id,
            case_label=artifact.case_id,
            origin="curated",
            artifact_status=artifact.status,
            failure_stage=artifact.failure_stage,
            failure_message=artifact.failure_message,
            benchmark=self._benchmarks.record(
                locator.experiment,
                artifact,
            ),
            sources=project_sources(
                artifact
            ),
            graph=graph,
            metrics=project_metrics(
                artifact
            ),
            reference_run=project_reference_run(
                locator.snapshot_id,
                artifact,
                graph,
            ),
        )