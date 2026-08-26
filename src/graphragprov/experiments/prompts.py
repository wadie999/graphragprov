"""Named prompts used by research experiments."""

from __future__ import annotations

import json
from collections.abc import Iterable

from graphragprov.benchmarks.musique import MusiqueCase
from graphragprov.benchmarks.twowiki import TwoWikiCase
from graphragprov.domain import SourceUnit
from graphragprov.extraction.prompt import SYSTEM_PROMPT
from graphragprov.extraction.run import GroundedExtractionRun

H0_QUERY_PROMPT_VERSION = "musique-sparql-evidence-first-v1"

CONSTRUCT_TWOWIKI_QUESTION_GRAPH = """
We are constructing a rich grounded RDF graph for one 2WikiMultiHopQA question.

The CURRENT SOURCE is the extraction target.

The question, expected answer, and benchmark evidence relations are coordination
context. They identify relations that the final graph must not miss, but they
do not define the complete graph and they are not textual evidence.

For the CURRENT SOURCE:

1. MANDATORY BENCHMARK COVERAGE

Represent every benchmark evidence relation that is explicitly supported by
CURRENT SOURCE.

These relations are a required minimum. They must not be omitted.

2. BROAD SOURCE EXTRACTION

After ensuring the mandatory benchmark relations are represented, continue
through the entire CURRENT SOURCE and extract all other useful explicit atomic
facts that can be grounded correctly.

Do not stop after extracting the benchmark relation.

Do not restrict extraction to facts needed for the question or expected answer.

Treat each sentence or local clause independently: when it contains a useful
explicit factual relation, represent that relation unless doing so would violate
the grounding or graph-quality rules.

The benchmark evidence tells you what must not be missed.
It is not the extraction target and is not a reason to stop.

Reuse semantic names already present in the accepted graph when they denote the
same thing.

Every returned subject, predicate, and object must cite exact evidence from the
CURRENT SOURCE.

Do not use the question, expected answer, benchmark evidence relations, accepted
graph, or another source as textual evidence.

Python owns source identity; never return source IDs.
""".strip()

CONSTRUCT_MUSIQUE_QUESTION_GRAPH = """
We are constructing a grounded RDF graph for one MuSiQue benchmark question.

The question, expected answer, and decomposition are coordination context. They
help keep entity and predicate choices compatible across supporting paragraphs.
They are not evidence.

For the CURRENT SOURCE only, return grounded RDF statements using the extraction
schema below. Reuse semantic names already present in the accepted graph when
they denote the same thing.
Extract all useful explicit atomic facts from CURRENT SOURCE.

Do not restrict extraction to facts needed for the question.

However, facts explicitly present in CURRENT SOURCE that are required
to realize its MuSiQue decomposition hop(s) are mandatory and must not
be omitted.

Question/answer/decomposition/accepted graph are coordination context,
not evidence.

Every returned statement must be supported by the CURRENT SOURCE. Python owns
source identity; never return source IDs.
""".strip()


WRITE_SPARQL_FOR_MUSIQUE_QUESTION = """
ROLE

You are constructing the SPARQL computation for a multi-hop question-answering
experiment over a frozen RDF graph.

Your job is not merely to state or force the expected answer.

Your job is to express a query whose ?answer value is obtained by executing
graph patterns against the RDF graph supplied below.

WHY THE QUERY STRUCTURE MATTERS

The query is executed over the frozen graph.

After execution, the computation is traced backwards to determine which RDF
statements contributed to each returned answer, and those RDF statements are
resolved back to their exact source occurrences.

Therefore the answer must genuinely arise from graph matching.

A query that simply injects an already-known answer may return the right value,
but it does not express the computation we need to observe.

THE FROZEN GRAPH IS THE SOURCE OF TRUTH FOR THIS TASK

Every triple pattern you rely on must correspond to relations actually available
in the frozen RDF graph.

Do not invent a relation because it would make the reasoning chain work.

Do not assume a benchmark relation exists unless you can locate the corresponding
RDF triple in the supplied graph.

If the graph does not contain the relation needed for an intended reasoning
step, do not fabricate it.

DECOMPOSITION

The MuSiQue decomposition describes the intended semantic dependency of the
question.

Use it to understand what each reasoning step means and to look for corresponding
relations in the frozen graph.

The decomposition does not create facts in the graph.

An intermediate answer from the decomposition may help you recognize entities,
but the SPARQL computation must still derive its bindings through the graph
relations that actually exist.

CONSTRUCT THE QUERY

Find the RDF triples in the frozen graph that can realize the question.

Use variables to connect dependent graph patterns.

The final ?answer variable must occur in an RDF triple pattern that retrieves
its value from the graph.

Example:

Graph:
    <Organization> <abbreviatedAs> <FIFA> .

To retrieve the organization represented by FIFA:

    ?answer <abbreviatedAs> <FIFA> .

Do not instead write:

    <Organization> <abbreviatedAs> <FIFA> .
    BIND(<Organization> AS ?answer)

The first query derives the answer.
The second query inserts an answer that was already known.

SUPPORTED QUERY FORM

Use a SELECT query with ?answer as the answer variable.

Use basic RDF triple patterns and joins through shared variables.

Do not use:
- BIND
- VALUES
- SELECT DISTINCT
- GRAPH
- SERVICE
- SPARQL updates
- FROM clauses

Python adds dataset scoping after your semantic query is produced.

MATCHED TRIPLES

matched_triples is your record of the exact frozen-graph statements you relied
on while constructing the query.

Copy those N-Triples lines exactly from the supplied frozen graph.

Do not report a triple that is not present in the graph.

matched_triples describes your evidence selection; the SPARQL query describes
the computation you construct from that evidence.

OUTPUT

Return only valid JSON:

{
  "matched_triples": [
    "<subject> <predicate> <object> ."
  ],
  "sparql": "SELECT ?answer WHERE { ... }"
}
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


def build_twowiki_graph_source_prompt(
    *,
    case: TwoWikiCase,
    source: SourceUnit,
    paragraph_index: int,
    accepted_runs: Iterable[GroundedExtractionRun],
    validation_error: str | None = None,
) -> str:
    accepted_graph = _render_accepted_graph(accepted_runs)

    source_json = json.dumps(
        {"title": source.title, "text": source.text}, ensure_ascii=False, indent=2
    )

    evidence_chain = "\n".join(
        f"{i}. {evidence.subject} | {evidence.relation} | {evidence.object}"
        for i, evidence in enumerate(case.evidences, start=1)
    )

    parts = [
        SYSTEM_PROMPT,
        "EXPERIMENT TASK — CONSTRUCT 2WIKI QUESTION GRAPH",
        CONSTRUCT_TWOWIKI_QUESTION_GRAPH,
        f"Question: {case.question}",
        f"Expected answer: {case.answer}",
        "Benchmark evidence relations:\n" + evidence_chain,
        "Accepted semantic graph so far:\n" + (accepted_graph or "(empty)"),
        f"CURRENT SOURCE — 2Wiki paragraph {paragraph_index}",
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
