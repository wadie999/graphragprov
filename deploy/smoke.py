"""Exercise the deployed API, GraphDB, rewriting, and source-span decoding."""

import json
import os
from urllib.request import Request, urlopen


def main() -> None:
    base = os.getenv("GRAPHRAGPROV_SMOKE_URL", "http://127.0.0.1:8080").rstrip("/")

    def call(path: str, payload: dict | None = None) -> dict:
        request = Request(
            base + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=120) as response:
            return json.load(response)

    case = call("/api/v1/experiments/demo/cases/aster-designer")
    snapshot = call(f"/api/v1/snapshots/{case['snapshot_id']}")
    query = snapshot["reference_run"]["semantic_sparql"]
    for attempt in range(2):
        result = call(
            f"/api/v1/snapshots/{case['snapshot_id']}/query-runs",
            {"sparql": query, "origin": "manual"},
        )
        if result.get("error") or result.get("provenance_status") != "decoded":
            raise RuntimeError(f"execution or provenance failed: {result}")
        rows = result["result"]["results"]["bindings"]
        if len(rows) != 1 or rows[0]["answer"]["value"] != "urn:graphragprov:entity:Porto":
            raise RuntimeError(f"unexpected answer: {rows}")
        answers = result["provenance"]
        if len(answers) != 1 or len(answers[0]["derivations"]) != 1:
            raise RuntimeError("expected one complete derivation")
        factors = answers[0]["derivations"][0]["factors"]
        if len(factors) != 2 or any(not factor.get("occurrence_id") for factor in factors):
            raise RuntimeError("expected two resolvable occurrence factors")
        print(f"Run {attempt + 1}: Porto; both source occurrences decoded.")
    print("Deployment smoke check passed.")


if __name__ == "__main__":
    main()
