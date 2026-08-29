"""Aggregate configured case metrics without changing experiment artifacts."""

from statistics import fmean

from graphragprov.workbench_api.models.metrics import MetricCollection, MetricObservation
from graphragprov.workbench_api.services.catalog import ExperimentCatalog
from graphragprov.workbench_api.services.metrics import project_metrics


def experiment_metrics(catalog: ExperimentCatalog, experiment_id: str) -> MetricCollection:
    locators = catalog.cases(experiment_id)
    artifacts = [catalog.read(item) for item in locators if item.result_path.exists()]
    items: list[MetricObservation] = [
        _metric("experiment.case_count", "Cases", len(locators)),
        _metric("experiment.available_count", "Artifacts", len(artifacts)),
        _metric(
            "experiment.complete_count", "Complete", sum(a.status == "complete" for a in artifacts)
        ),
    ]
    grouped: dict[str, list[float]] = {}
    labels: dict[str, tuple[str, str | None]] = {}
    for artifact in artifacts:
        for metric in project_metrics(artifact).items:
            if isinstance(metric.value, (int, float)) and not isinstance(metric.value, bool):
                grouped.setdefault(metric.key, []).append(float(metric.value))
                labels[metric.key] = (metric.label, metric.unit)
    for key, values in grouped.items():
        label, unit = labels[key]
        items.append(
            MetricObservation(
                key=f"{key}.mean",
                label=f"Mean {label.lower()}",
                scope="experiment",
                value=fmean(values),
                unit=unit,
                method="mean-over-available-cases",
            )
        )
    return MetricCollection(items=tuple(items))


def _metric(key: str, label: str, value: int) -> MetricObservation:
    return MetricObservation(key=key, label=label, scope="experiment", value=value)
