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


def _keyword_pattern(*keywords: str) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(keyword) for keyword in keywords)

    return re.compile(rf"(?<![\w?$:@.-])(?:{alternatives})(?![\w.-])", flags=re.IGNORECASE)


_WHERE_PATTERN = _keyword_pattern("WHERE")

_FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("FROM", _keyword_pattern("FROM")),
    ("GRAPH", _keyword_pattern("GRAPH")),
    ("SERVICE", _keyword_pattern("SERVICE")),
    (
        "update operation",
        _keyword_pattern(
            "INSERT",
            "DELETE",
            "LOAD",
            "CLEAR",
            "CREATE",
            "DROP",
            "COPY",
            "MOVE",
            "ADD",
            "WITH",
            "USING",
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
    lexical_query = _mask_non_code_regions(query)

    _validate_semantic_select(query=query, lexical_query=lexical_query)

    if source_unit_ids is None:
        return query

    graph_iris = tuple(sorted({str(unit_graph_iri(unit_id)) for unit_id in source_unit_ids}))

    if not graph_iris:
        raise ValueError("scoped SPARQL requires at least one source unit")

    where_match = _WHERE_PATTERN.search(lexical_query)

    if where_match is None:
        raise ValueError("semantic SPARQL must contain an explicit WHERE clause")

    query_head = query[: where_match.start()].rstrip()
    query_body = query[where_match.start() :].lstrip()

    dataset = "\n".join(f"FROM <{graph_iri}>" for graph_iri in graph_iris)

    return f"{query_head}\n{dataset}\n{query_body}"


def _validate_semantic_select(*, query: str, lexical_query: str) -> None:
    if not query:
        raise ValueError("semantic SPARQL must not be empty")

    if _SELECT_PATTERN.match(query) is None:
        raise ValueError("semantic SPARQL must be a SELECT query")

    for name, pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(lexical_query) is not None:
            raise ValueError(f"semantic SPARQL must not contain {name}")

    if _WHERE_PATTERN.search(lexical_query) is None:
        raise ValueError("semantic SPARQL must contain an explicit WHERE clause")


def _mask_non_code_regions(query: str) -> str:
    """Mask lexical regions where SPARQL keywords have no control meaning.

    The returned string has exactly the same length as ``query`` so match
    offsets can safely be used to slice the original query.

    IRI references, string literals, and comments are replaced by spaces,
    while line breaks are preserved.
    """

    masked = list(query)
    index = 0

    while index < len(query):
        if query[index] == "#":
            index = _mask_comment(query=query, masked=masked, start=index)
            continue

        if query.startswith('"""', index):
            index = _mask_string(query=query, masked=masked, start=index, delimiter='"""')
            continue

        if query.startswith("'''", index):
            index = _mask_string(query=query, masked=masked, start=index, delimiter="'''")
            continue

        if query[index] in {'"', "'"}:
            index = _mask_string(query=query, masked=masked, start=index, delimiter=query[index])
            continue

        if query[index] == "<":
            iri_end = _iri_reference_end(query, start=index)

            if iri_end is not None:
                _mask_range(masked, start=index, end=iri_end + 1)
                index = iri_end + 1
                continue

        index += 1

    return "".join(masked)


def _mask_comment(*, query: str, masked: list[str], start: int) -> int:
    index = start

    while index < len(query) and query[index] not in "\r\n":
        masked[index] = " "
        index += 1

    return index


def _mask_string(*, query: str, masked: list[str], start: int, delimiter: str) -> int:
    index = start
    delimiter_length = len(delimiter)

    _mask_range(masked, start=start, end=min(start + delimiter_length, len(query)))
    index += delimiter_length

    while index < len(query):
        if query.startswith(delimiter, index):
            _mask_range(masked, start=index, end=index + delimiter_length)
            return index + delimiter_length

        if query[index] == "\\" and index + 1 < len(query):
            masked[index] = " "
            if query[index + 1] not in "\r\n":
                masked[index + 1] = " "
            index += 2
            continue

        if query[index] not in "\r\n":
            masked[index] = " "

        index += 1

    return index


def _iri_reference_end(query: str, *, start: int) -> int | None:
    """Return the closing ``>`` for an IRIREF beginning at ``start``.

    A SPARQL IRIREF cannot contain whitespace or the forbidden characters
    checked below. This distinction prevents comparison operators such as
    ``?x < 5`` from being mistaken for IRI references.
    """

    index = start + 1

    while index < len(query):
        character = query[index]

        if character == ">":
            return index

        if ord(character) <= 0x20 or character in '<"{}|^`\\':
            return None

        index += 1

    return None


def _mask_range(masked: list[str], *, start: int, end: int) -> None:
    for index in range(start, min(end, len(masked))):
        if masked[index] not in "\r\n":
            masked[index] = " "
