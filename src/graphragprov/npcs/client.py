"""Minimal HTTP client for the NPCS rewriting service."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

NPCS_URL_ENV = "GRAPHRAGPROV_NPCS_URL"
NPCS_REWRITE_PATH = "/api/content/rewrite"


class NPCSError(RuntimeError):
    """Raised when NPCS rewriting fails."""


@dataclass(frozen=True)
class NPCSClient:
    """Rewrite SPARQL queries through the NPCS HTTP service."""

    base_url: str
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("NPCS base URL must not be empty")

        if self.timeout_seconds <= 0:
            raise ValueError("NPCS timeout must be positive")

    @classmethod
    def from_environment(cls) -> NPCSClient:
        """Build an NPCS client from environment variables."""

        base_url = os.getenv(NPCS_URL_ENV)

        if not base_url:
            raise ValueError(f"missing required environment variable {NPCS_URL_ENV}")

        return cls(base_url=base_url)

    @property
    def rewrite_endpoint(self) -> str:
        """Return the NPCS rewriting endpoint."""

        return f"{self.base_url.rstrip('/')}{NPCS_REWRITE_PATH}"

    def rewrite(self, sparql: str) -> str:
        """Return the NPCS-rewritten SPARQL query."""

        if not sparql.strip():
            raise ValueError("SPARQL query must not be empty")

        payload = json.dumps(
            {"input1": "SPARQL_Star", "input2": "query", "input3": sparql}
        ).encode()

        request = Request(
            self.rewrite_endpoint,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "text/plain"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = cast(bytes, response.read())
                rewritten = response_body.decode().strip()
        except HTTPError as error:
            body = error.read().decode(errors="replace")

            raise NPCSError(f"NPCS returned HTTP {error.code}: {body or error.reason}") from error
        except URLError as error:
            raise NPCSError(f"could not reach NPCS: {error.reason}") from error

        if not rewritten:
            raise NPCSError("NPCS returned an empty rewritten query")

        return rewritten
