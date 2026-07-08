"""Stable identifiers derived from immutable source content."""

import json
import re
from hashlib import sha256

_SOURCE_UNIT_ID_PATTERN = re.compile(r"u_[0-9a-f]{64}")


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


def validate_source_unit_id(unit_id: str) -> None:
    """Reject abbreviated or malformed source-unit identifiers."""

    if _SOURCE_UNIT_ID_PATTERN.fullmatch(unit_id) is None:
        raise ValueError(
            "unit ID must contain 'u_' followed by the full 64-character lowercase SHA-256 digest"
        )
