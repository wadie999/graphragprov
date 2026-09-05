"""HTTP client for the SparqlProv rewriting service."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SPARQLPROV_URL_ENV = "GRAPHRAGPROV_SPARQLPROV_URL"
SPARQLPROV_REWRITE_PATH = "/rewrite"


class SparqlProvError(RuntimeError):
    """Raised when SparqlProv rewriting fails."""


@dataclass(frozen=True, slots=True)
class RewriteResult:
    """Rewritten SPARQL and the provenance result variable."""

    sparql: str
    provenance_variable: str


class QueryRewriter(Protocol):
    def rewrite_detailed(self, sparql: str) -> RewriteResult: ...


def rewrite_query(rewriter: QueryRewriter, sparql: str) -> RewriteResult:
    """Rewrite a query and return its provenance metadata."""

    return rewriter.rewrite_detailed(sparql)


@dataclass(frozen=True, slots=True)
class SparqlProvClient:
    """Rewrite SPARQL queries through SparqlProv."""

    base_url: str
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("SparqlProv base URL must not be empty")

        if self.timeout_seconds <= 0:
            raise ValueError("SparqlProv timeout must be positive")

    @classmethod
    def from_environment(cls) -> SparqlProvClient:
        """Build a SparqlProv client from environment variables."""

        base_url = os.getenv(SPARQLPROV_URL_ENV)

        if not base_url:
            raise ValueError(
                f"missing required environment variable {SPARQLPROV_URL_ENV}"
            )

        return cls(base_url=base_url)

    @property
    def rewrite_endpoint(self) -> str:
        """Return the SparqlProv rewrite endpoint."""

        return f"{self.base_url.rstrip('/')}{SPARQLPROV_REWRITE_PATH}"

    def rewrite(self, sparql: str) -> str:
        """Return only the rewritten SPARQL query."""

        return self.rewrite_detailed(sparql).sparql

    def rewrite_detailed(self, sparql: str) -> RewriteResult:
        """Return rewritten SPARQL and its provenance variable."""

        if not sparql.strip():
            raise ValueError("SPARQL query must not be empty")

        from graphragprov.rdf.vocabulary import PROV

        payload = json.dumps(
            {
                "query": sparql,
                "strategy": "optimized",
                "provenance_predicate": f"{PROV}occurrenceOf",
            }
        ).encode("utf-8")

        request = Request(
            self.rewrite_endpoint,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8").strip()

        except HTTPError as error:
            body = error.read().decode(errors="replace")
            raise SparqlProvError(
                f"SparqlProv returned HTTP {error.code}: "
                f"{body or error.reason}"
            ) from error

        except URLError as error:
            raise SparqlProvError(
                f"could not reach SparqlProv: {error.reason}"
            ) from error

        if not response_body:
            raise SparqlProvError("SparqlProv returned an empty response")

        try:
            result = json.loads(response_body)
        except json.JSONDecodeError as error:
            raise SparqlProvError(
                "SparqlProv returned invalid JSON"
            ) from error

        if not isinstance(result, dict):
            raise SparqlProvError(
                "SparqlProv response must be a JSON object"
            )

        rewritten_query = result.get("sparql")
        provenance_variable = result.get("provenance_variable")

        if not isinstance(rewritten_query, str) or not rewritten_query.strip():
            raise SparqlProvError(
                "SparqlProv returned no rewritten query"
            )

        if (
            not isinstance(provenance_variable, str)
            or re.fullmatch(
                r"\?[A-Za-z_][A-Za-z0-9_]*",
                provenance_variable,
            )
            is None
        ):
            raise SparqlProvError(
                "SparqlProv returned no valid provenance variable"
            )

        return RewriteResult(
            sparql=rewritten_query,
            provenance_variable=provenance_variable[1:],
        )