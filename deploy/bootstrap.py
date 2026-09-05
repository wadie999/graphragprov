"""Wait for dependencies, then create the configured GraphDB repository once."""

import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from graphragprov.workbench_api.config import load_config


def request(
    url: str, *, data: bytes | None = None, content_type: str = "application/json"
) -> bytes:
    req = Request(
        url, data=data, headers={"Content-Type": content_type, "Accept": "application/json"}
    )
    with urlopen(req, timeout=5) as response:
        return response.read()


def wait_for(label: str, check, *, timeout: float = 180) -> None:
    deadline = time.monotonic() + timeout
    last = "not ready"
    while time.monotonic() < deadline:
        try:
            check()
            print(f"{label}: ready", flush=True)
            return
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            last = str(error)
            time.sleep(2)
    raise RuntimeError(
        f"{label} did not become ready: {last}. Check docker compose logs graphdb sparqlprov."
    )


def ensure_repository(base: str, repository: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", repository):
        raise ValueError("repository name must contain only letters, digits, '_' or '-'")
    metadata_url = f"{base}/rest/repositories/{quote(repository, safe='')}"
    try:
        request(metadata_url)
        print(f"Repository {repository}: already exists (data preserved)", flush=True)
        return
    except HTTPError as error:
        if error.code != 404:
            raise
    # GraphDB's REST API accepts an RDF4J configuration as multipart form data.
    ttl = f'''@prefix rep: <http://www.openrdf.org/config/repository#> .
@prefix sr: <http://www.openrdf.org/config/repository/sail#> .
@prefix sail: <http://www.openrdf.org/config/sail#> .
@prefix owlim: <http://www.ontotext.com/trree/owlim#> .
[] a rep:Repository ;
   rep:repositoryID "{repository}" ;
   rep:repositoryImpl [
     rep:repositoryType "graphdb:SailRepository" ;
     sr:sailImpl [ sail:sailType "graphdb:Sail" ;
       owlim:ruleset "empty" ; owlim:storage-folder "storage" ;
       owlim:repository-type "file-repository" ;
       owlim:enable-context-index "true" ] ] .
'''
    boundary = "graphragprov-repository-config"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; "
        'name="config"; filename="repository.ttl"\r\n'
        f"Content-Type: text/turtle\r\n\r\n{ttl}\r\n--{boundary}--\r\n"
    ).encode()
    request(
        f"{base}/rest/repositories",
        data=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    print(f"Repository {repository}: created with inference disabled", flush=True)


def main() -> None:
    config = load_config()
    base = config.graphdb.base_url.rstrip("/")
    wait_for("SparqlProv", lambda: request(f"{config.sparqlprov.base_url.rstrip('/')}/health"))
    wait_for("GraphDB HTTP", lambda: request(f"{base}/rest/repositories"))
    try:
        ensure_repository(base, config.graphdb.repository or "")
    except HTTPError as error:
        raise RuntimeError(
            f"GraphDB repository setup failed (HTTP {error.code}). "
            "Check the GraphDB license file and its version in docs/setup.md."
        ) from error
    endpoint = f"{base}/repositories/{quote(config.graphdb.repository or '', safe='')}"

    def query_ready() -> None:
        result = json.loads(
            request(
                endpoint,
                data=urlencode(
                    {"query": "SELECT (1 AS ?ready) WHERE {}", "infer": "false"}
                ).encode(),
                content_type="application/x-www-form-urlencoded",
            )
        )
        if not result.get("results", {}).get("bindings"):
            raise ValueError("repository query returned no binding")

    wait_for("GraphDB query engine", query_ready)


if __name__ == "__main__":
    main()
