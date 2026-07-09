"""Minimal HTTP client for a GraphDB repository."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

GRAPHDB_URL_ENV = "GRAPHRAGPROV_GRAPHDB_URL"
GRAPHDB_REPOSITORY_ENV = "GRAPHRAGPROV_GRAPHDB_REPOSITORY"
GRAPHDB_USERNAME_ENV = "GRAPHRAGPROV_GRAPHDB_USERNAME"
GRAPHDB_PASSWORD_ENV = "GRAPHRAGPROV_GRAPHDB_PASSWORD"

TRIG_STAR_MEDIA_TYPE = "application/x-trigstar"
SPARQL_RESULTS_MEDIA_TYPE = "application/sparql-results+json"


class GraphDBError(RuntimeError):
    """Raised when GraphDB rejects a request or cannot be reached."""


@dataclass(frozen=True)
class GraphDBClient:
    """Upload RDF and execute SPARQL against one GraphDB repository."""

    base_url: str
    repository: str
    username: str | None = None
    password: str | None = None
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("GraphDB base URL must not be empty")

        if not self.repository.strip():
            raise ValueError("GraphDB repository must not be empty")

        if self.timeout_seconds <= 0:
            raise ValueError("GraphDB timeout must be positive")

        credentials = (self.username, self.password)

        if credentials.count(None) == 1:
            raise ValueError("GraphDB username and password must be provided together")

    @classmethod
    def from_environment(cls) -> GraphDBClient:
        """Build a client from the GraphRAGProv environment variables."""

        base_url = os.getenv(GRAPHDB_URL_ENV)
        repository = os.getenv(GRAPHDB_REPOSITORY_ENV)

        if not base_url:
            raise ValueError(f"missing required environment variable {GRAPHDB_URL_ENV}")

        if not repository:
            raise ValueError(f"missing required environment variable {GRAPHDB_REPOSITORY_ENV}")

        return cls(
            base_url=base_url,
            repository=repository,
            username=os.getenv(GRAPHDB_USERNAME_ENV),
            password=os.getenv(GRAPHDB_PASSWORD_ENV),
        )

    @property
    def repository_endpoint(self) -> str:
        """Return the RDF4J endpoint of the configured repository."""

        repository = quote(self.repository, safe="")

        return f"{self.base_url.rstrip('/')}/repositories/{repository}"

    @property
    def statements_endpoint(self) -> str:
        """Return the RDF4J statements endpoint."""

        return f"{self.repository_endpoint}/statements"

    def upload_trig_star(self, content: str | bytes) -> None:
        """Add one TriG-star document to the repository."""

        payload = content.encode("utf-8") if isinstance(content, str) else content

        request = Request(
            self.statements_endpoint,
            data=payload,
            headers=self._headers(
                content_type=TRIG_STAR_MEDIA_TYPE,
            ),
            method="POST",
        )

        self._execute(request)

    def query(self, sparql: str) -> dict[str, object]:
        """Execute a SPARQL query and return its JSON result."""

        if not sparql.strip():
            raise ValueError("SPARQL query must not be empty")

        payload = urlencode({"query": sparql}).encode("utf-8")

        request = Request(
            self.repository_endpoint,
            data=payload,
            headers=self._headers(
                content_type="application/x-www-form-urlencoded",
                accept=SPARQL_RESULTS_MEDIA_TYPE,
            ),
            method="POST",
        )

        _, response_body = self._execute(request)

        try:
            decoded = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GraphDBError("GraphDB returned invalid SPARQL JSON") from error

        if not isinstance(decoded, dict):
            raise GraphDBError("GraphDB returned a non-object SPARQL result")

        if not all(isinstance(key, str) for key in decoded):
            raise GraphDBError("GraphDB returned invalid SPARQL result keys")

        return cast(dict[str, object], decoded)

    def _headers(
        self,
        *,
        content_type: str,
        accept: str | None = None,
    ) -> dict[str, str]:
        headers = {
            "Content-Type": content_type,
        }

        if accept is not None:
            headers["Accept"] = accept

        if self.username is not None and self.password is not None:
            credentials = f"{self.username}:{self.password}".encode()
            encoded = base64.b64encode(credentials).decode("ascii")
            headers["Authorization"] = f"Basic {encoded}"

        return headers

    def _execute(self, request: Request) -> tuple[int, bytes]:
        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                status = response.getcode()
                body = response.read()
        except HTTPError as error:
            response_body = error.read().decode(
                "utf-8",
                errors="replace",
            )

            raise GraphDBError(
                f"GraphDB returned HTTP {error.code}: {response_body or error.reason}"
            ) from error
        except URLError as error:
            raise GraphDBError(f"could not reach GraphDB: {error.reason}") from error

        if not 200 <= status < 300:
            raise GraphDBError(f"GraphDB returned unexpected HTTP status {status}")

        return status, body
