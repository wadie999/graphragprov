"""Randomly select two MuSiQue cases for each hop count."""

from pathlib import Path
import random

from graphragprov.benchmarks.musique import select_cases


DATASET = Path(
    "external/benchmarks/musique/data/"
    "musique_full_v1.0_train.jsonl"
)
OUTPUT = Path("docs/musique-few-shot-candidates/README.md")
SEED = 42


def main() -> None:
    rng = random.Random(SEED)
    selected = []

    for hop_count in (2, 3, 4):
        cases = select_cases(
            DATASET,
            hop_count=hop_count,
            limit=100_000,
        )
        selected.extend(rng.sample(list(cases), 2))

    lines = [
        "# MuSiQue few-shot candidates",
        "",
        f"- Dataset: `{DATASET}`",
        f"- Random seed: `{SEED}`",
        "- Selected: 2 cases for each of 2, 3 and 4 hops",
        "",
    ]

    for number, case in enumerate(selected, start=1):
        lines.extend(
            [
                "---",
                "",
                f"## {number}. {case.hop_count}-hop — `{case.case_id}`",
                "",
                f"**Question:** {case.question}",
                "",
                f"**Answer:** {case.answer}",
                "",
                "### Decomposition",
                "",
            ]
        )

        for hop_number, hop in enumerate(case.decomposition, start=1):
            lines.extend(
                [
                    f"**Hop {hop_number}**",
                    "",
                    f"- Question: {hop.question}",
                    f"- Answer: {hop.answer}",
                    (
                        "- Supporting paragraph: "
                        f"`{hop.paragraph_support_index}`"
                    ),
                    "",
                ]
            )

        lines.extend(
            [
                "### Gold supporting paragraphs",
                "",
            ]
        )

        supporting_paragraphs = [
            paragraph
            for paragraph in case.paragraphs
            if case.is_supporting(paragraph.index)
        ]

        for paragraph in supporting_paragraphs:
            lines.extend(
                [
                    f"#### Paragraph {paragraph.index}: {paragraph.title}",
                    "",
                    paragraph.text,
                    "",
                ]
            )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {len(selected)} cases to {OUTPUT}")

    for case in selected:
        print(
            f"{case.hop_count}-hop | "
            f"{case.case_id} | "
            f"{case.question}"
        )


if __name__ == "__main__":
    main()
