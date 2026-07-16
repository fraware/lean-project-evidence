"""Structured secret redaction for build logs embedded in evidence (AUDIT-007).

Fail closed on known secret shapes. Patterns are intentionally specific so
ordinary Lean/Lake build logs (theorem names, module paths, sorry warnings)
are not mangled.
"""

from __future__ import annotations

import re

REDACTION_MARKER = "[REDACTED]"

_BEARER = re.compile(r"(?i)(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)")

# Multiline PEM / OpenSSH private key blocks (BEGIN … PRIVATE KEY … END).
_PEM_PRIVATE_KEY = re.compile(
    r"-----BEGIN[^\n]*PRIVATE KEY-----.*?-----END[^\n]*PRIVATE KEY-----",
    re.DOTALL,
)

_FULL_REPLACE: tuple[re.Pattern[str], ...] = (
    # GitHub PATs / fine-grained tokens
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"ghu_[A-Za-z0-9]{20,}"),
    re.compile(r"ghs_[A-Za-z0-9]{20,}"),
    re.compile(r"ghr_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    # Slack bot / user / app tokens
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    re.compile(r"xapp-[0-9A-Za-z-]{10,}"),
    # GitLab personal access tokens
    re.compile(r"glpat-[A-Za-z0-9\-_]{20,}"),
    # npm access tokens
    re.compile(r"npm_[A-Za-z0-9]{20,}"),
    # Stripe secret / restricted keys
    re.compile(r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}"),
    # OpenAI / project-style sk- keys (require long body; avoid short Lean idents)
    re.compile(r"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"),
    # Hugging Face tokens
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
    # AWS access key IDs
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # AWS secret access key assignment shapes
    re.compile(
        r"(?i)(aws_secret_access_key|secret_access_key)\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{30,}['\"]?"
    ),
    # Common assignment / export shapes
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|secret[_-]?key|password|"
        r"client_secret)\b\s*[=:]\s*['\"]?[^\s'\"]{8,}['\"]?"
    ),
    # Generic JWT-like triples (header.payload.signature)
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
)


def redact_secrets(text: str) -> str:
    """Redact known secret shapes from stdout/stderr before evidence embedding."""
    if not text:
        return text
    redacted = _PEM_PRIVATE_KEY.sub(REDACTION_MARKER, text)
    redacted = _BEARER.sub(rf"\1{REDACTION_MARKER}", redacted)
    for pattern in _FULL_REPLACE:
        redacted = pattern.sub(REDACTION_MARKER, redacted)
    return redacted
