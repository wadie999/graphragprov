from hashlib import sha256


def source_unit_id(text: str) -> str:
    """Return a deterministic identifier for exact UTF-8 text."""

    digest = sha256(text.encode("utf-8")).hexdigest()
    return f"u_{digest}"
