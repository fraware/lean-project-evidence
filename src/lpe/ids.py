from __future__ import annotations

import uuid


def stable_id(prefix: str, material: str) -> str:
    """Return a deterministic identifier for the same prefix and material."""
    from lpe.hashing import sha256_text

    digest = sha256_text(material)
    return f"{prefix}_{digest[:32]}"


def new_id(prefix: str) -> str:
    if not prefix or not prefix.replace("_", "").isalnum():
        raise ValueError(f"prefix must be a non-empty alphanumeric identifier, got {prefix!r}")
    return f"{prefix}_{uuid.uuid4().hex}"


def validate_id_format(identifier: str, prefix: str) -> bool:
    expected_prefix = f"{prefix}_"
    if not identifier.startswith(expected_prefix):
        return False
    suffix = identifier[len(expected_prefix) :]
    return len(suffix) == 32 and all(char in "0123456789abcdef" for char in suffix)
