import json
from pathlib import Path

from graphragprov.experiments.multihop_fidelity.run_many_twowiki import _load_jobs
from graphragprov.hashing import source_unit_id


def _row(case_id: str, *, support_title: str, support_text: str) -> dict[str, object]:
    return {
        "_id": case_id,
        "type": "compositional",
        "question": f"Question for {case_id}?",
        "context": [
            [support_title, [support_text]],
            [f"Distractor {case_id}", ["Irrelevant text."]],
        ],
        "supporting_facts": [[support_title, 0]],
        "evidences": [[support_title, "relation", f"Answer {case_id}"]],
        "evidences_id": None,
        "answer": f"Answer {case_id}",
        "answer_id": None,
        "entity_ids": "",
    }


def test_load_jobs_preserves_requested_order_and_source_conflicts(tmp_path: Path) -> None:
    dataset = tmp_path / "twowiki.json"

    shared_title = "Shared source"
    shared_text = "The same supporting paragraph is reused."

    dataset.write_text(
        json.dumps(
            [
                _row("case-a", support_title=shared_title, support_text=shared_text),
                _row("case-b", support_title="Other source", support_text="Other evidence."),
                _row("case-c", support_title=shared_title, support_text=shared_text),
            ]
        ),
        encoding="utf-8",
    )

    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("case-c\ncase-b\ncase-a\n", encoding="utf-8")

    jobs = _load_jobs(dataset, ids_file)

    assert tuple(job.case_id for job in jobs) == ("case-c", "case-b", "case-a")

    assert jobs[0].ordinal == 1
    assert jobs[2].ordinal == 3

    shared_id = source_unit_id(title=shared_title, text=shared_text)

    assert shared_id in jobs[0].support_ids
    assert shared_id in jobs[2].support_ids

    assert jobs[0].support_ids.isdisjoint(jobs[1].support_ids)
