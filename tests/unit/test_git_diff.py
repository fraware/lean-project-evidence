from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lpe.git.diff import GitError, changed_paths, classify_added_declarations, resolve_commit


def run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def init_repo(tmp_path: Path) -> tuple[str, str]:
    run("git", "init", cwd=tmp_path)
    run("git", "config", "user.email", "test@example.org", cwd=tmp_path)
    run("git", "config", "user.name", "Test", cwd=tmp_path)
    return "", ""


def test_git_diff_classifier(tmp_path: Path) -> None:
    init_repo(tmp_path)
    public_dir = tmp_path / "Example" / "Public"
    public_dir.mkdir(parents=True)
    file = public_dir / "Example.lean"
    file.write_text("theorem old : True := by trivial\n", encoding="utf-8")
    run("git", "add", ".", cwd=tmp_path)
    run("git", "commit", "-m", "base", cwd=tmp_path)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    file.write_text(
        "theorem old : True := by trivial\n"
        "def newDefinition : Nat := 1\n",
        encoding="utf-8",
    )
    run("git", "add", ".", cwd=tmp_path)
    run("git", "commit", "-m", "change", cwd=tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert changed_paths(tmp_path, base, head) == ["Example/Public/Example.lean"]
    declarations = classify_added_declarations(
        tmp_path,
        base,
        head,
        public_api_prefixes=("Example/Public",),
    )
    assert [d.name for d in declarations] == ["newDefinition"]
    assert declarations[0].public is True
    assert declarations[0].signature_changed is False


def test_invalid_revision_raises_actionable_error(tmp_path: Path) -> None:
    init_repo(tmp_path)
    with pytest.raises(GitError, match="cannot resolve revision"):
        resolve_commit(tmp_path, "not-a-real-ref")


def test_signature_change_detected(tmp_path: Path) -> None:
    init_repo(tmp_path)
    internal = tmp_path / "Internal.lean"
    internal.write_text("def foo : Nat := 1\n", encoding="utf-8")
    run("git", "add", ".", cwd=tmp_path)
    run("git", "commit", "-m", "base", cwd=tmp_path)
    base = resolve_commit(tmp_path, "HEAD")
    internal.write_text("def foo : Int := 1\n", encoding="utf-8")
    run("git", "add", ".", cwd=tmp_path)
    run("git", "commit", "-m", "sig", cwd=tmp_path)
    head = resolve_commit(tmp_path, "HEAD")
    declarations = classify_added_declarations(tmp_path, base, head)
    assert len(declarations) == 1
    assert declarations[0].signature_changed is True
    assert declarations[0].public is False
