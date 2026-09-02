"""Composition root for workbench services."""

from dataclasses import dataclass

from graphragprov.graphdb import GraphDBClient
from graphragprov.npcs import NPCSClient
from graphragprov.workbench_api.config import WorkbenchConfig
from graphragprov.workbench_api.services.benchmark import BenchmarkService
from graphragprov.workbench_api.services.catalog import ExperimentCatalog
from graphragprov.workbench_api.services.execution import QueryExecutor
from graphragprov.workbench_api.services.planner import QueryPlanner
from graphragprov.workbench_api.services.snapshots import SnapshotService
from graphragprov.workbench_api.services.store import WorkbenchStore
from graphragprov.workbench_api.services.user_workspace import UserWorkspaceService
from graphragprov.workbench_api.services.workspace import GraphWorkspaceManager


@dataclass(frozen=True, slots=True)
class Services:
    config: WorkbenchConfig
    catalog: ExperimentCatalog
    snapshots: SnapshotService
    planner: QueryPlanner
    executor: QueryExecutor
    store: WorkbenchStore
    user_workspace: UserWorkspaceService


def build_services(config: WorkbenchConfig) -> Services:
    catalog = ExperimentCatalog(config)

    store = WorkbenchStore(config.state_dir)

    graphdb = GraphDBClient(
        base_url=config.graphdb.base_url,
        repository=(config.graphdb.repository or ""),
        timeout_seconds=(config.graphdb.timeout_seconds),
    )

    npcs = NPCSClient(base_url=config.npcs.base_url, timeout_seconds=(config.npcs.timeout_seconds))

    workspace = GraphWorkspaceManager(graphdb)

    user_workspace = UserWorkspaceService(config.state_dir, config.planner, workspace)

    snapshots = SnapshotService(catalog, BenchmarkService(), user_workspace)

    return Services(
        config=config,
        catalog=catalog,
        snapshots=snapshots,
        planner=QueryPlanner(config.planner, store),
        executor=QueryExecutor(workspace, npcs, store, config.planner),
        store=store,
        user_workspace=user_workspace,
    )
