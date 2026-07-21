"""AUDIT-007: secret redaction corpus for build logs embedded in evidence."""

from __future__ import annotations

import pytest

from lpe.execution.env import is_denied_env_key, scrub_environment
from lpe.execution.redact import REDACTION_MARKER, redact_secrets

# Realistic Lean/Lake lines that must survive redaction unchanged.
_LEAN_LOG_LINES = (
    "info: [1/3] Building Mathlib.Data.Nat.Basic",
    "error: unknown identifier 'Nat.add_comm'",
    "theorem Foo.bar : True := by exact trivial",
    "#check List.map",
    "warning: declaration uses 'sorry'",
    "lake build ok",
    "Compiling LpeFixture.Core (12 decls)",
)


def _t(*parts: str) -> str:
    """Join fixture parts so scanners do not see contiguous secret-shaped literals."""
    return "".join(parts)


@pytest.mark.parametrize(
    ("raw", "must_not_appear"),
    [
        (
            "clone failed token=" + _t("ghp_", "abcdefghijklmnopqrstuvwxyz0123456789ABCD"),
            _t("ghp_", "abcdefghijklmnopqrstuvwxyz0123456789ABCD"),
        ),
        (
            "auth " + _t("gho_", "abcdefghijklmnopqrstuvwxyz0123456789"),
            _t("gho_", "abcdefghijklmnopqrstuvwxyz0123456789"),
        ),
        (
            "fine-grained " + _t("github_pat_", "11AAAAAAA0abcdefghijklmnopqrstuv"),
            _t("github_pat_", "11AAAAAAA0abcdefghijklmnopqrstuv"),
        ),
        (
            "AWS_ACCESS_KEY_ID=" + _t("AKIA", "IOSFODNN7EXAMPLE") + " leftover",
            _t("AKIA", "IOSFODNN7EXAMPLE"),
        ),
        (
            "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature",
            "eyJhbGciOiJIUzI1NiJ9.payload.signature",
        ),
        (
            "export API_KEY=supersecretvalue12345",
            "supersecretvalue12345",
        ),
        (
            "password=hunter2hunter2hunter2",
            "hunter2hunter2hunter2",
        ),
        (
            "client_secret=abcdefghijklmnopqrstuvwxyz012345",
            "abcdefghijklmnopqrstuvwxyz012345",
        ),
        (
            "aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        ),
        # Expanded provider-specific corpus
        (
            "slack bot " + _t("xoxb-", "123456789012-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx"),
            _t("xoxb-", "123456789012-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx"),
        ),
        (
            "user token "
            + _t(
                "xoxp-",
                "123456789012-123456789012-123456789012-abcdef0123456789abcdef0123456789",
            ),
            _t(
                "xoxp-",
                "123456789012-123456789012-123456789012-abcdef0123456789abcdef0123456789",
            ),
        ),
        (
            "app token "
            + _t(
                "xapp-",
                "1-A0123456789-1234567890123-abcdef0123456789abcdef0123456789abcd",
            ),
            _t(
                "xapp-",
                "1-A0123456789-1234567890123-abcdef0123456789abcdef0123456789abcd",
            ),
        ),
        (
            "gitlab " + _t("glpat-", "abcdefghijklmnopqrstuvwx"),
            _t("glpat-", "abcdefghijklmnopqrstuvwx"),
        ),
        (
            "npm " + _t("npm_", "abcdefghijklmnopqrstuvwxyz012345"),
            _t("npm_", "abcdefghijklmnopqrstuvwxyz012345"),
        ),
        (
            "stripe " + _t("sk_live_", "abcdefghijklmnopqrstuvwxyz0123"),
            _t("sk_live_", "abcdefghijklmnopqrstuvwxyz0123"),
        ),
        (
            "openai " + _t("sk-", "abcdefghijklmnopqrstuvwxyz0123456789ABCD"),
            _t("sk-", "abcdefghijklmnopqrstuvwxyz0123456789ABCD"),
        ),
        (
            "anthropic " + _t("sk-ant-", "api03-abcdefghijklmnopqrstuvwxyz012345"),
            _t("sk-ant-", "api03-abcdefghijklmnopqrstuvwxyz012345"),
        ),
        (
            "hf " + _t("hf_", "abcdefghijklmnopqrstuvwxyz012345"),
            _t("hf_", "abcdefghijklmnopqrstuvwxyz012345"),
        ),
        (
            "jwt eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        ),
    ],
)
def test_redact_secrets_corpus_replaces_known_shapes(raw: str, must_not_appear: str) -> None:
    """Invariant: known secret shapes never survive redaction into evidence logs."""
    out = redact_secrets(raw)
    assert must_not_appear not in out
    assert REDACTION_MARKER in out


def test_redact_pem_private_key_multiline_dump() -> None:
    """Invariant: PEM private-key dumps are fully redacted (multiline)."""
    pem = (
        "dump follows\n"
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF6PZGBw7\n"
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n"
        "-----END RSA PRIVATE KEY-----\n"
        "done"
    )
    out = redact_secrets(pem)
    assert "BEGIN RSA PRIVATE KEY" not in out
    assert "MIIEowIBAAKCAQEA" not in out
    assert "END RSA PRIVATE KEY" not in out
    assert REDACTION_MARKER in out
    assert out.startswith("dump follows\n")
    assert out.endswith("\ndone")


def test_redact_openssh_private_key_block() -> None:
    block = (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\n"
        "-----END OPENSSH PRIVATE KEY-----"
    )
    out = redact_secrets(block)
    assert "OPENSSH PRIVATE KEY" not in out
    assert "b3BlbnNzaC1rZXktdjE" not in out
    assert out == REDACTION_MARKER


def test_redact_secrets_preserves_non_secret_text() -> None:
    log = "lake build ok\ntheorem Nat.add_comm proved"
    assert redact_secrets(log) == log


def test_redact_secrets_empty_is_noop() -> None:
    assert redact_secrets("") == ""


@pytest.mark.parametrize("line", _LEAN_LOG_LINES)
def test_redact_does_not_over_redact_lean_log_lines(line: str) -> None:
    """Invariant: ordinary Lean/Lake diagnostics are left intact."""
    assert redact_secrets(line) == line


def test_redact_mixed_secret_in_lean_log_keeps_lean_context() -> None:
    """Fail closed on the secret; preserve surrounding Lean diagnostics."""
    raw = (
        "info: [2/4] Building LpeFixture.Core\n"
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature\n"
        "error: unknown identifier 'Nat.add_comm'\n"
    )
    out = redact_secrets(raw)
    assert "eyJhbGciOiJIUzI1NiJ9.payload.signature" not in out
    assert "Building LpeFixture.Core" in out
    assert "unknown identifier 'Nat.add_comm'" in out
    assert REDACTION_MARKER in out


def test_redact_does_not_mangle_short_sk_prefix_or_public_pem() -> None:
    """Avoid over-redacting short identifiers and public certificates."""
    benign = (
        "module Sk.Helper compiled\n"
        "-----BEGIN CERTIFICATE-----\n"
        "MIIBkTCB+wIJAKHBfL7example\n"
        "-----END CERTIFICATE-----\n"
    )
    assert redact_secrets(benign) == benign


# --- AUDIT-008 (paired with redaction: secrets must not enter the build env) ---


@pytest.mark.parametrize(
    "key",
    [
        "MY_API_TOKEN",
        "DB_SECRET",
        "LOGIN_PASSWORD",
        "GITHUB_TOKEN",
        "GITHUB_ACTIONS",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "CI",
        "GH_TOKEN",
    ],
)
def test_env_denylist_blocks_token_secret_github_ci(key: str) -> None:
    """Invariant: TOKEN/SECRET/PASSWORD/GITHUB_/AWS_/CI never forward to builds."""
    assert is_denied_env_key(key) is True


@pytest.mark.parametrize("key", ["PATH", "HOME", "LANG", "TERM", "USER"])
def test_env_denylist_allows_benign_keys(key: str) -> None:
    assert is_denied_env_key(key) is False


def test_scrub_environment_drops_denied_even_when_allowlisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invariant: denylist wins over environment_allowlist."""
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_should_not_leak")
    monkeypatch.setenv("MY_TOKEN", "secret")
    monkeypatch.setenv("HOME", "/home/ci")
    env = scrub_environment(["PATH", "CI", "GITHUB_TOKEN", "MY_TOKEN", "HOME"])
    assert env == {"PATH": "/usr/bin", "HOME": "/home/ci"}
    assert "CI" not in env
    assert "TOKEN" not in " ".join(env)
