import json
from hashlib import sha256


def source_unit_id(*, title: str, text: str) -> str:
    """Return an identifier for an exact title-and-text source unit."""

    payload = json.dumps(
        {
            "text": text,
            "title": title,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return f"u_{sha256(payload).hexdigest()}"
