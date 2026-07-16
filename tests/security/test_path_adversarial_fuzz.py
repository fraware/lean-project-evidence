"""AUDIT-025 expansion: Unicode, NTFS streams, percent-encoding, symlink escapes."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lpe.paths import PathTraversalError, assert_safe_repo_relative


@pytest.mark.parametrize(
    "relative",
    [
        # Classic + mixed (regression)
        "../etc/passwd",
        "..\\Windows\\System32",
        "/etc/passwd",
        "src/../../secret",
        "C:/Windows/System32",
        "~/secret",
        "foo/../../../etc/shadow",
        "..",
        "../",
        "a/b/../../c/../../../x",
        # NUL / control
        "foo\x00/bar",
        "src/\x00../etc/passwd",
        # Percent-encoded traversal / separators
        "..%2fetc/passwd",
        "%2e%2e/etc/passwd",
        "foo%2f..%2fbar",
        "src%5c..%5csecret",
        "file%00.lean",
        # NTFS alternate data streams
        "README.md:Zone.Identifier",
        "src/Foo.lean:$DATA",
        "nested/x.lean:stream",
        # Unicode lookalike dots
        "\uff0e\uff0e/etc/passwd",
        "\u2025/etc/passwd",
        "src/\u3002\u3002/secret",
        # UNC / device-ish
        "//server/share",
        "\\\\server\\share",
    ],
)
def test_assert_safe_repo_relative_rejects_adversarial(
    tmp_path: Path, relative: str
) -> None:
    with pytest.raises(PathTraversalError):
        assert_safe_repo_relative(tmp_path, relative)


def test_symlink_escape_rejected(tmp_path: Path) -> None:
    """Symlink inside repo pointing outside must fail closed on resolve."""
    outside = tmp_path / "outside_secret"
    outside.mkdir()
    (outside / "leak.txt").write_text("secret", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    link = repo / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation not permitted: {exc}")

    with pytest.raises(PathTraversalError, match="escapes"):
        assert_safe_repo_relative(repo, "escape/leak.txt")


def test_symlink_within_repo_allowed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    target_dir = repo / "real"
    target_dir.mkdir(parents=True)
    target = target_dir / "Foo.lean"
    target.write_text("-- lean\n", encoding="utf-8")
    link = repo / "alias"
    try:
        link.symlink_to(target_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation not permitted: {exc}")

    resolved = assert_safe_repo_relative(repo, "alias/Foo.lean")
    assert resolved == target.resolve()
    assert resolved.is_relative_to(repo.resolve())


@pytest.mark.parametrize(
    "relative",
    [
        "src/Foo.lean",
        "Example/Public/Api.lean",
        "nested/dir/file.lean",
        "unicode/名前.lean",
    ],
)
def test_safe_nested_paths_still_accepted(tmp_path: Path, relative: str) -> None:
    (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / relative).write_text("-- lean\n", encoding="utf-8")
    resolved = assert_safe_repo_relative(tmp_path, relative)
    assert resolved == (tmp_path / relative).resolve()


@pytest.mark.skipif(os.name != "nt", reason="Windows drive-letter absolute form")
def test_windows_drive_absolute_rejected(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError):
        assert_safe_repo_relative(tmp_path, "D:\\secrets\\x.lean")
