"""Explicit allowlist for contract build_command executables (AUDIT-005)."""

from __future__ import annotations

from pathlib import Path

# Basename allowlist. Documented wrappers may be added only after security review.
ALLOWED_BUILD_COMMANDS: frozenset[str] = frozenset(
    {
        "lake",
        "lean",
        "elan",
        "lake.exe",
        "lean.exe",
        "elan.exe",
    }
)


class CommandAllowlistError(ValueError):
    """Raised when build_command is not on the explicit allowlist."""


def normalize_command_basename(executable: str) -> str:
    """Return the executable basename used for allowlist checks."""
    name = Path(executable).name
    return name.lower()


def validate_build_command(command: list[str]) -> list[str]:
    """Reject empty or non-allowlisted build commands with an actionable error.

    Only the executable (argv[0]) is checked against the allowlist. Arguments are
    passed through unchanged; shell wrappers and interpreters are not permitted.
    """
    if not command:
        raise CommandAllowlistError(
            "build_command is empty. Configure an allowlisted command such as "
            f"{sorted(ALLOWED_BUILD_COMMANDS)} (see docs/09_SECURITY_AND_PRIVACY.md)."
        )

    executable = command[0]
    if not executable or executable.startswith("-"):
        raise CommandAllowlistError(
            f"build_command executable {executable!r} is invalid. "
            f"Allowed executables: {sorted(ALLOWED_BUILD_COMMANDS)}."
        )

    # Refuse shell/interpreter forms that would bypass the allowlist.
    basename = normalize_command_basename(executable)
    if basename in {
        "sh",
        "bash",
        "zsh",
        "cmd.exe",
        "cmd",
        "powershell",
        "pwsh",
        "python",
        "python3",
    }:
        raise CommandAllowlistError(
            f"build_command executable {executable!r} is a shell/interpreter and is not "
            f"allowed. Use a direct allowlisted tool ({sorted(ALLOWED_BUILD_COMMANDS)})."
        )

    if basename not in ALLOWED_BUILD_COMMANDS:
        raise CommandAllowlistError(
            f"build_command executable {executable!r} (basename {basename!r}) is not "
            f"on the allowlist. Allowed: {sorted(ALLOWED_BUILD_COMMANDS)}. "
            "See docs/09_SECURITY_AND_PRIVACY.md."
        )

    return command
