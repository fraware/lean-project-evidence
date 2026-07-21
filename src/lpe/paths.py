"""Repository-relative path safety helpers (AUDIT-025 path traversal)."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath


class PathTraversalError(ValueError):
    """Raised when a candidate path escapes the project repository root."""


# Fullwidth / compatibility lookalikes that must not be treated as safe dots.
_DOT_LOOKALIKES = (
    "\u2024",  # one-dot leader
    "\u2025",  # two-dot leader
    "\u2026",  # horizontal ellipsis (three dots)
    "\uff0e",  # fullwidth full stop
    "\u3002",  # ideographic full stop
)


def _reject_encoded_or_control(text: str, *, label: str) -> None:
    """Fail closed on null bytes, percent-encoded separators, and NTFS streams."""
    if "\x00" in text:
        raise PathTraversalError(f"{label} must not contain NUL bytes: {text!r}")
    lowered = text.lower()
    # Percent-encoding of ../ or separators — refuse before any downstream decode.
    for needle in ("%2e", "%2f", "%5c", "%00"):
        if needle in lowered:
            raise PathTraversalError(
                f"{label} must not contain percent-encoded path segments: {text!r}"
            )
    # NTFS alternate data streams / ADS: colon in any non-drive segment.
    for part in PurePosixPath(text).parts:
        if ":" in part:
            raise PathTraversalError(
                f"{label} must not contain ':' (NTFS streams / drive escapes): {text!r}"
            )
    for ch in _DOT_LOOKALIKES:
        if ch in text:
            raise PathTraversalError(f"{label} must not contain Unicode lookalike dots: {text!r}")


def assert_safe_repo_relative(repository: Path, relative: str, *, label: str = "path") -> Path:
    """Resolve ``relative`` under ``repository`` or raise ``PathTraversalError``.

    Rejects absolute paths, home shortcuts, ``..`` segments, NUL / percent-encoded
    escapes, NTFS alternate-stream colons, and Unicode lookalike dots. The resolved
    path must remain inside the repository root (symlink-aware via ``resolve``).
    """
    if not relative or not str(relative).strip():
        raise PathTraversalError(f"{label} must be a non-empty repository-relative path")

    text = str(relative).strip().replace("\\", "/")
    _reject_encoded_or_control(text, label=label)

    posix = PurePosixPath(text)
    windows = PureWindowsPath(text.replace("/", "\\"))

    if posix.is_absolute() or windows.is_absolute() or text.startswith("/"):
        raise PathTraversalError(f"{label} must be repository-relative, got absolute {relative!r}")
    if text.startswith("~"):
        raise PathTraversalError(f"{label} must be repository-relative, got {relative!r}")
    if ".." in posix.parts or ".." in windows.parts:
        raise PathTraversalError(f"{label} must not contain '..' segments: {relative!r}")

    repo = repository.resolve()
    resolved = (repo / text).resolve()
    if resolved != repo and not resolved.is_relative_to(repo):
        raise PathTraversalError(f"{label} escapes repository root: {relative!r} → {resolved}")
    return resolved
