"""Environment scrubbing for sandboxed and host builds (AUDIT-008)."""

from __future__ import annotations

import os
import re

# Keys matching these patterns are never forwarded, even if allowlisted.
_DENIED_NAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r".*_TOKEN$", re.IGNORECASE),
    re.compile(r".*_SECRET$", re.IGNORECASE),
    re.compile(r".*_PASSWORD$", re.IGNORECASE),
    re.compile(r"^GITHUB_.*", re.IGNORECASE),
    re.compile(r"^AWS_.*", re.IGNORECASE),
)

# Exact names that must never pass through.
_DENIED_EXACT: frozenset[str] = frozenset(
    {
        "CI",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SESSION_TOKEN",
    }
)


def is_denied_env_key(key: str) -> bool:
    """Return True if the environment key must never be forwarded to builds."""
    if key in _DENIED_EXACT:
        return True
    return any(pattern.fullmatch(key) for pattern in _DENIED_NAME_PATTERNS)


def scrub_environment(allowlist: list[str]) -> dict[str, str]:
    """Select host env vars that are allowlisted and not on the secret denylist."""
    allowed = set(allowlist)
    return {
        key: value
        for key, value in os.environ.items()
        if key in allowed and not is_denied_env_key(key)
    }
