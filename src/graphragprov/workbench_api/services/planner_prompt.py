"""Prompt construction for natural-language graph querying."""


def build_planner_prompt(question: str, ntriples: str) -> str:
    return f"""GRAPH QUERY PLANNER

You receive one natural-language question and one frozen RDF graph.
The graph below is the only knowledge source. Do not use outside knowledge.

Return exactly one JSON object with these fields:
{{
  "status": "query" | "ambiguous" | "unanswerable",
  "purpose": "final" | null,
  "sparql": "SELECT ..." | null,
  "rationale": "short explanation",
  "assumptions": []
}}

Rules for status=query:
- produce a read-only SPARQL SELECT query;
- include an explicit WHERE clause;
- project the natural-language answer as ?answer when the question asks for one value;
- use only RDF terms present in the frozen graph;
- use variables for intermediate joins;
- do not include FROM, GRAPH, SERVICE, or SPARQL update operations;
- do not copy an answer from outside the graph.

Use unanswerable when the frozen graph lacks the required facts.
Use ambiguous only when multiple graph-supported interpretations prevent one query.

Question:
{question}

Frozen RDF graph (N-Triples):
{ntriples}
"""
