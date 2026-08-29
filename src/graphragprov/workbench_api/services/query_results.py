"""Helpers for generic SPARQL JSON result objects."""

from typing import cast


def bindings(result: dict[str, object]) -> list[dict[str, object]]:
    results = result.get("results")
    if not isinstance(results, dict):
        return []
    raw = results.get("bindings")
    if not isinstance(raw, list):
        return []
    return [cast(dict[str, object], item) for item in raw if isinstance(item, dict)]
