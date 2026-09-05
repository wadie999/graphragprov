"""Decode SparqlProv's nested prefix notation without losing multiplicity."""

from graphragprov.rdf.provenance import _TOKEN_PATTERN, decode_occurrence_token

MAX_DERIVATIONS = 10_000
MAX_DEPTH = 64
MAX_FACTORS = 10_000


def parse_sparqlprov_polynomial(value: str) -> list[tuple[str, ...]]:
    if len(value) > 4_000_000:
        raise ValueError("provenance expression exceeds the 4 MB display limit")
    parser = _Parser(value)
    result = parser.expression(0)
    parser.whitespace()
    if parser.index != len(value):
        raise ValueError("unexpected trailing provenance content")
    if not result or any(not term for term in result):
        raise ValueError("this workbench requires provenance with grounded occurrences")
    return result


class _Parser:
    def __init__(self, value: str) -> None:
        self.value = value
        self.index = 0

    def whitespace(self) -> None:
        while self.index < len(self.value) and self.value[self.index].isspace():
            self.index += 1

    def expression(self, depth: int) -> list[tuple[str, ...]]:
        if depth > MAX_DEPTH:
            raise ValueError("provenance nesting exceeds the display limit")
        self.whitespace()
        match = _TOKEN_PATTERN.match(self.value, self.index)
        if match:
            token = match.group()
            decode_occurrence_token(token)
            self.index = match.end()
            return [(token,)]
        if self.index >= len(self.value):
            raise ValueError("incomplete provenance expression")
        if self.value[self.index] in "01":
            identity = self.value[self.index]
            self.index += 1
            return [] if identity == "0" else [()]
        if self.value[self.index] != "(" or self.index + 1 >= len(self.value):
            raise ValueError(f"invalid provenance expression at {self.index}")
        operator = self.value[self.index + 1]
        if operator == "⊖":
            raise ValueError(
                "difference/OPTIONAL provenance is not supported by the workbench viewer"
            )
        if operator not in {"⊕", "⊗"}:
            raise ValueError(f"unknown provenance operator {operator!r}")
        self.index += 2
        result: list[tuple[str, ...]] = [] if operator == "⊕" else [()]
        while True:
            self.whitespace()
            if self.index >= len(self.value):
                raise ValueError("provenance expression is missing its closing ')'")
            if self.value[self.index] == ")":
                self.index += 1
                return result
            child = self.expression(depth + 1)
            size = len(result) + len(child) if operator == "⊕" else len(result) * len(child)
            if size > MAX_DERIVATIONS:
                raise ValueError("provenance expansion exceeds 10000 derivations; narrow the query")
            if operator == "⊕":
                result.extend(child)
            else:
                if result and child and max(map(len, result)) + max(map(len, child)) > MAX_FACTORS:
                    raise ValueError("provenance derivation exceeds the factor display limit")
                result = [left + right for left in result for right in child]
