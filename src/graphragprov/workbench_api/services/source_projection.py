"""Project persisted grounded source units for source inspection."""

from graphragprov.workbench_api.artifacts import ArtifactCase
from graphragprov.workbench_api.models.source import SourceUnitView


def project_sources(artifact: ArtifactCase) -> tuple[SourceUnitView, ...]:
    items: list[SourceUnitView] = []

    for ordinal, run in enumerate(artifact.extraction_runs, start=1):
        paragraph_index = _paragraph_index(artifact, run.source.unit_id)

        items.append(
            SourceUnitView(
                source_id=run.source.unit_id,
                ordinal=ordinal,
                paragraph_index=paragraph_index,
                title=run.source.title,
                text=run.source.text,
                statement_count=len(run.extraction.statements),
                extraction_prompt=(run.prompt or None),
                extraction_response=(run.response or None),
            )
        )

    return tuple(items)


def _paragraph_index(artifact: ArtifactCase, source_id: str) -> int | None:
    measurements = artifact.extraction_measurements or {}

    sources = measurements.get("sources")

    if not isinstance(sources, list):
        return None

    for item in sources:
        if isinstance(item, dict) and item.get("unit_id") == source_id:
            value = item.get("paragraph_index")

            return value if isinstance(value, int) else None

    return None
