"""Deterministic dataset scoping for QA-agent SPARQL queries."""

from __future__ import annotations

import re
from collections.abc import Iterable

from graphragprov.rdf.terms import unit_graph_iri

_SELECT_PATTERN = re.compile(
    r"""
    \A
    \s*
    (?:
        (?:
            PREFIX
            \s+
            (?:[A-Za-z_][A-Za-z0-9_.-]*)?
            :
            \s*
            <[^>]+>
            |
            BASE
            \s+
            <[^>]+>
        )
        \s*
    )*
    SELECT
    \b
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)

_WHERE_PATTERN = re.compile(r"\bWHERE\b", flags=re.IGNORECASE)

_FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("FROM", re.compile(r"\bFROM\b", flags=re.IGNORECASE)),
    ("GRAPH", re.compile(r"\bGRAPH\b", flags=re.IGNORECASE)),
    ("SERVICE", re.compile(r"\bSERVICE\b", flags=re.IGNORECASE)),
    (
        "update operation",
        re.compile(
            r"\b(?:"
            r"INSERT|DELETE|LOAD|CLEAR|CREATE|DROP|"
            r"COPY|MOVE|ADD|WITH|USING"
            r")\b",
            flags=re.IGNORECASE,
        ),
    ),
)


def compile_scoped_select_query(
    semantic_sparql: str, *, source_unit_ids: Iterable[str] | None
) -> str:
    """Compile semantic SPARQL with a backend-controlled dataset.

    ``source_unit_ids`` identifies the named graphs that form the query's
    default dataset. Passing ``None`` preserves repository-level execution
    without adding explicit FROM clauses.
    """

    query = semantic_sparql.strip()

    _validate_semantic_select(query)

    if source_unit_ids is None:
        return query

    graph_iris = tuple(sorted({str(unit_graph_iri(unit_id)) for unit_id in source_unit_ids}))

    if not graph_iris:
        raise ValueError("scoped SPARQL requires at least one source unit")

    where_match = _WHERE_PATTERN.search(query)

    if where_match is None:
        raise ValueError("semantic SPARQL must contain an explicit WHERE clause")

    query_head = query[: where_match.start()].rstrip()
    query_body = query[where_match.start() :].lstrip()

    dataset = "\n".join(f"FROM <{graph_iri}>" for graph_iri in graph_iris)

    return f"{query_head}\n{dataset}\n{query_body}"


def _validate_semantic_select(query: str) -> None:
    if not query:
        raise ValueError("semantic SPARQL must not be empty")

    if _SELECT_PATTERN.match(query) is None:
        raise ValueError("semantic SPARQL must be a SELECT query")

    for name, pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(query) is not None:
            raise ValueError(f"semantic SPARQL must not contain {name}")

    if _WHERE_PATTERN.search(query) is None:
        raise ValueError("semantic SPARQL must contain an explicit WHERE clause")
