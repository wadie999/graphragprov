"""Benchmark-specific enrichment behind one stable workbench model."""

from __future__ import annotations

from collections.abc import Mapping

from graphragprov.benchmarks.musique import iter_cases as iter_musique
from graphragprov.benchmarks.twowiki import iter_cases as iter_twowiki
from graphragprov.workbench_api.artifacts import ArtifactCase
from graphragprov.workbench_api.config import ExperimentConfig
from graphragprov.workbench_api.models.benchmark import BenchmarkRecord, ReasoningStep


class BenchmarkService:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], Mapping[str, object]] = {}

    def record(self, experiment: ExperimentConfig, artifact: ArtifactCase) -> BenchmarkRecord:
        case = self._cases(experiment).get(artifact.case_id)

        if experiment.benchmark == "musique" and case is not None:
            return _musique_record(artifact, case)

        if experiment.benchmark == "twowiki" and case is not None:
            return _twowiki_record(artifact, case)

        return _fallback_record(experiment, artifact)

    def _cases(self, experiment: ExperimentConfig) -> Mapping[str, object]:
        path = experiment.dataset_path

        if path is None or not path.exists():
            return {}

        key = (experiment.benchmark, str(path.resolve()))

        cached = self._cache.get(key)
        if cached is not None:
            return cached

        iterator = iter_musique(path) if experiment.benchmark == "musique" else iter_twowiki(path)

        cases = {case.case_id: case for case in iterator}

        self._cache[key] = cases
        return cases


def _musique_record(artifact: ArtifactCase, case: object) -> BenchmarkRecord:
    from graphragprov.benchmarks.musique import MusiqueCase

    assert isinstance(case, MusiqueCase)

    steps = tuple(
        ReasoningStep(
            step_id=str(hop.hop_id),
            question=hop.question,
            answer=hop.answer,
            source_index=hop.paragraph_support_index,
        )
        for hop in case.decomposition
    )

    return BenchmarkRecord(
        case_id=case.case_id,
        benchmark="musique",
        question=case.question,
        expected_answers=(case.answer, *case.answer_aliases),
        hop_count=case.hop_count,
        answerable=case.answerable,
        reasoning_steps=steps,
        support_source_ids=artifact.support_source_ids,
        metadata={"gold_support_indices": list(case.gold_support_indices)},
    )


def _twowiki_record(artifact: ArtifactCase, case: object) -> BenchmarkRecord:
    from graphragprov.benchmarks.twowiki import TwoWikiCase

    assert isinstance(case, TwoWikiCase)

    steps = tuple(
        ReasoningStep(
            step_id=str(index + 1), subject=item.subject, relation=item.relation, object=item.object
        )
        for index, item in enumerate(case.evidences)
    )

    return BenchmarkRecord(
        case_id=case.case_id,
        benchmark="twowiki",
        question=case.question,
        expected_answers=((case.answer,) if case.answer is not None else ()),
        hop_count=artifact.hop_count,
        answerable=case.answer is not None,
        reasoning_steps=steps,
        support_source_ids=artifact.support_source_ids,
        metadata={"question_type": case.question_type},
    )


def _fallback_record(experiment: ExperimentConfig, artifact: ArtifactCase) -> BenchmarkRecord:
    return BenchmarkRecord(
        case_id=artifact.case_id,
        benchmark=experiment.benchmark,
        question=artifact.question,
        expected_answers=(artifact.expected_answer,),
        hop_count=artifact.hop_count,
        answerable=None,
        reasoning_steps=(),
        support_source_ids=artifact.support_source_ids,
        metadata={"enrichment": "artifact_only"},
    )
