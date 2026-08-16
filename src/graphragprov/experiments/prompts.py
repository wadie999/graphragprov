"""Named prompts used by research experiments."""

from __future__ import annotations

import json
from collections.abc import Iterable

from graphragprov.benchmarks.musique import MusiqueCase
from graphragprov.domain import SourceUnit
from graphragprov.extraction.prompt import SYSTEM_PROMPT
from graphragprov.extraction.run import GroundedExtractionRun

H0_QUERY_PROMPT_VERSION = "musique-sparql-evidence-first-v1"


CONSTRUCT_MUSIQUE_QUESTION_GRAPH = """
We are constructing a grounded RDF graph for one MuSiQue benchmark question.

The question, expected answer, and decomposition are coordination context. They
help keep entity and predicate choices compatible across supporting paragraphs.
They are not evidence.

For the CURRENT SOURCE only, return grounded RDF statements using the extraction
schema below. Reuse semantic names already present in the accepted graph when
they denote the same thing.

Every returned statement must be supported by the CURRENT SOURCE. Python owns
source identity; never return source IDs.
""".strip()


WRITE_SPARQL_FOR_MUSIQUE_QUESTION = """
Construct the SPARQL SELECT query that represents the MuSiQue question over the
frozen RDF graph below.

Use an evidence-first procedure. Do not jump directly from the natural-language
question to a path-shaped SPARQL query.

Step 1 — select graph evidence

For every step of the gold decomposition:

1. Locate the exact RDF triple or triples in the frozen graph that establish
   that step.

2. Copy those triples verbatim into `matched_triples`.

3. Do not change subject, predicate, object, or predicate direction.

4. Do not assume that consecutive decomposition steps form a directed RDF path.

Two decomposition steps may instead be connected by a join.

For example, the graph topology may be:

    <A> <p> <X> .
    <B> <p> <X> .
    <B> <q> <Y> .

The correct composition is then structurally:

    <A> <p> ?shared .
    <B> <p> ?shared .
    <B> <q> ?answer .

It is NOT:

    <A> <p> ?shared .
    ?shared <p> ?something .

unless that second orientation literally exists in the frozen graph.

When a decomposition step refers to the answer of an earlier step, identify
exactly where that earlier answer appears in the selected frozen-graph triples:
as subject, object, or both.

Step 2 — compile selected evidence into SPARQL

Build the WHERE clause only from the evidence selected in `matched_triples`.

Preserve the subject/predicate/object orientation of every selected triple.

Keep entities explicitly named by the benchmark question as constants when they
identify the intended resource.

Replace intermediate decomposition answers with shared variables where they
connect selected triples.

Replace the final answer position with `?answer`.

The same intermediate entity must use the same variable everywhere it joins
selected triples.

Do not create a new triple orientation while converting evidence into SPARQL.

SPARQL requirements:

- project the final answer as ?answer;
- derive ?answer from graph patterns;
- use only RDF terms present in the frozen graph;
- include an explicit WHERE clause;
- do not use FROM, GRAPH, SERVICE, or update operations;
- do not manufacture the expected answer with VALUES, BIND, FILTER, or a
  constant equal to the expected answer.
- Any non-final answer appearing in the gold decomposition must not occur as an RDF constant 
in the generated SPARQL; it must be abstracted into a variable 
wherever it connects decomposition hops.
Return only one valid JSON object with exactly these two fields:

{
  "matched_triples": [
    "<subject> <predicate> <object> ."
  ],
  "sparql": "SELECT ?answer WHERE { ... }"
}

`matched_triples` is an auditable graph-evidence selection, not free-form
reasoning.

Every string in `matched_triples` must be copied exactly from one complete line
of the frozen RDF graph.
""".strip()


def build_musique_graph_source_prompt(
    *,
    case: MusiqueCase,
    source: SourceUnit,
    paragraph_index: int,
    accepted_runs: Iterable[GroundedExtractionRun],
    validation_error: str | None = None,
) -> str:
    accepted_graph = _render_accepted_graph(accepted_runs)

    source_json = json.dumps(
        {"title": source.title, "text": source.text}, ensure_ascii=False, indent=2
    )

    parts = [
        SYSTEM_PROMPT,
        "EXPERIMENT TASK — CONSTRUCT MUSIQUE QUESTION GRAPH",
        CONSTRUCT_MUSIQUE_QUESTION_GRAPH,
        f"Question: {case.question}",
        f"Expected answer: {case.answer}",
        "Gold decomposition:\n" + _render_decomposition(case),
        "Accepted semantic graph so far:\n" + (accepted_graph or "(empty)"),
        f"CURRENT SOURCE — MuSiQue paragraph {paragraph_index}",
        source_json,
    ]

    if validation_error is not None:
        parts.extend(
            [
                "PREVIOUS RESPONSE WAS REJECTED BY THE DETERMINISTIC VALIDATOR",
                validation_error,
                "Return a corrected response for this same CURRENT SOURCE.",
            ]
        )

    return "\n\n".join(parts) + "\n"


def build_musique_sparql_prompt(
    *, case: MusiqueCase, graph_ntriples: str, feedback: str | None = None
) -> str:
    parts = [
        "EXPERIMENT TASK — WRITE SPARQL FOR MUSIQUE QUESTION",
        f"Prompt version: {H0_QUERY_PROMPT_VERSION}",
        WRITE_SPARQL_FOR_MUSIQUE_QUESTION,
        f"Question: {case.question}",
        f"Expected answer: {case.answer}",
        "Gold decomposition:\n" + _render_decomposition(case),
        "Frozen RDF graph:\n" + graph_ntriples,
    ]

    if feedback is not None:
        parts.extend(
            [
                "PREVIOUS QUERY FEEDBACK",
                feedback,
                (
                    "Return a corrected JSON object. "
                    "Re-select matched_triples if necessary, then rebuild the "
                    "SPARQL only from those selected triples."
                ),
            ]
        )

    return "\n\n".join(parts) + "\n"


def _render_decomposition(case: MusiqueCase) -> str:
    return "\n".join(
        (
            f"{i}. question={hop.question!r}; "
            f"answer={hop.answer!r}; "
            f"support_paragraph={hop.paragraph_support_index}"
        )
        for i, hop in enumerate(case.decomposition, start=1)
    )


def _render_accepted_graph(runs: Iterable[GroundedExtractionRun]) -> str:
    triples: set[str] = set()

    for run in runs:
        for statement in run.extraction.statements:
            triples.add(
                f"{statement.subject.value} | "
                f"{statement.predicate.value} | "
                f"{statement.object.value}"
            )

    return "\n".join(sorted(triples))
