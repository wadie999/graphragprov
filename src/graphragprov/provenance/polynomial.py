"""Strict parsing of NPCS provenance polynomials."""

from __future__ import annotations

from dataclasses import dataclass

from graphragprov.rdf.provenance import decode_occurrence_token


@dataclass(frozen=True, slots=True)
class ProvenancePolynomial:
    """Canonical sum of grounded-statement derivations."""

    derivations: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.derivations:
            raise ValueError("provenance polynomial must contain at least one derivation")

        for derivation in self.derivations:
            if not derivation:
                raise ValueError("provenance derivation must contain at least one token")

            for token in derivation:
                decode_occurrence_token(token)

            if derivation != tuple(sorted(derivation)):
                raise ValueError("tokens in each provenance derivation must be canonically ordered")

        if self.derivations != tuple(sorted(self.derivations)):
            raise ValueError("provenance derivations must be canonically ordered")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serializable representation."""

        return {"derivations": [{"tokens": list(derivation)} for derivation in self.derivations]}


def parse_provenance_polynomial(value: str) -> ProvenancePolynomial:
    """Parse one NPCS sum-of-products provenance value.

    NPCS currently emits values following this grammar:

        sum     := "⊕(" product (whitespace product)* ")"
        product := "(⊗" token ("," token)* ",)"

    Products and tokens are canonicalized because semiring addition and
    multiplication are commutative. Duplicate products and duplicate tokens
    are preserved because provenance multiplicity may be meaningful.
    """

    if value.startswith(("(⊕", "(⊗", "(⊖")):
        from graphragprov.provenance.sparqlprov_polynomial import parse_sparqlprov_polynomial

        derivations = parse_sparqlprov_polynomial(value)
        return ProvenancePolynomial(tuple(sorted(tuple(sorted(d)) for d in derivations)))

    parser = _PolynomialParser(value)
    derivations = parser.parse()

    canonical_derivations = tuple(sorted(tuple(sorted(derivation)) for derivation in derivations))

    return ProvenancePolynomial(derivations=canonical_derivations)


class _PolynomialParser:
    """Cursor-based parser for the exact NPCS polynomial syntax."""

    def __init__(self, value: str) -> None:
        self._value = value
        self._index = 0

    def parse(self) -> list[tuple[str, ...]]:
        """Parse the complete input and reject trailing content."""

        if not self._value:
            self._fail("provenance polynomial must not be empty")

        self._expect("⊕(")

        if self._at_end():
            self._fail("provenance polynomial is missing its body")

        if self._peek() == ")":
            self._fail("provenance polynomial must contain at least one product")

        derivations = [self._parse_product()]

        while True:
            if self._at_end():
                self._fail("provenance polynomial is missing its closing ')'")

            if self._peek() == ")":
                self._index += 1
                break

            if not self._peek().isspace():
                self._fail("expected whitespace or ')' after provenance product")

            self._consume_whitespace()

            if self._at_end() or self._peek() == ")":
                self._fail("expected provenance product after whitespace separator")

            derivations.append(self._parse_product())

        if not self._at_end():
            self._fail("unexpected trailing content after provenance polynomial")

        return derivations

    def _parse_product(self) -> tuple[str, ...]:
        self._expect("(⊗")

        tokens: list[str] = []

        while True:
            token_start = self._index

            while not self._at_end() and self._peek() != ",":
                self._index += 1

            if self._at_end():
                self._fail("provenance product is missing a token separator")

            token = self._value[token_start : self._index]

            if not token:
                self._fail("provenance product contains an empty token", index=token_start)

            try:
                decode_occurrence_token(token)
            except ValueError as error:
                raise ValueError(
                    f"invalid provenance token at index {token_start}: {error}"
                ) from error

            tokens.append(token)
            self._index += 1

            if self._at_end():
                self._fail("provenance product is missing its closing ')'")

            if self._peek() == ")":
                self._index += 1
                break

        return tuple(tokens)

    def _consume_whitespace(self) -> None:
        while not self._at_end() and self._peek().isspace():
            self._index += 1

    def _expect(self, expected: str) -> None:
        if not self._value.startswith(expected, self._index):
            self._fail(f"expected {expected!r}")

        self._index += len(expected)

    def _peek(self) -> str:
        return self._value[self._index]

    def _at_end(self) -> bool:
        return self._index == len(self._value)

    def _fail(self, message: str, *, index: int | None = None) -> None:
        position = self._index if index is None else index

        raise ValueError(f"{message} at index {position}")
