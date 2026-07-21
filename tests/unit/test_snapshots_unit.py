"""Unit coverage for workspace/snapshots.py (no Lean/Docker)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from lpe.hashing import sha256_text
from lpe.workspace.snapshots import (
    PatchRejectError,
    SnapshotError,
    SnapshotPair,
    _copy_tree,
    _reject_patch_content,
    _reject_patch_path,
    apply_patch_to_worktree,
    cleanup_snapshot_pair,
    create_snapshot_pair,
    lake_manifest_hash,
    resolve_patch_bytes,
    toolchain_file_hash,
    tree_hash_filesystem,
    tree_hash_git,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_git_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir()
    (root / "src" / "Main.lean").write_bytes(b"-- main\n")
    (root / "lean-toolchain").write_bytes(b"leanprover/lean4:v4.14.0\n")
    (root / "lakefile.toml").write_bytes(b'name = "demo"\n')
    _git(root, "init")
    _git(root, "config", "user.email", "lpe@localhost")
    _git(root, "config", "user.name", "LPE")
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    return root


def test_tree_hash_filesystem_stable_and_skips_git(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    (root / "a.txt").write_text("hello", encoding="utf-8")
    nested = root / "sub"
    nested.mkdir()
    (nested / "b.txt").write_text("world", encoding="utf-8")
    git_dir = root / ".git"
    git_dir.mkdir()
    (git_dir / "objects").mkdir()
    (git_dir / "objects" / "x").write_text("ignored", encoding="utf-8")

    h1 = tree_hash_filesystem(root)
    h2 = tree_hash_filesystem(root)
    assert h1 == h2
    assert len(h1) == 64

    (root / "a.txt").write_text("hello!", encoding="utf-8")
    assert tree_hash_filesystem(root) != h1


def test_tree_hash_git_success_and_failure(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path / "repo")
    digest = tree_hash_git(repo)
    assert len(digest) == 40

    with patch(
        "lpe.workspace.snapshots._run_git",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="cannot resolve tree hash"
        ),
    ):
        with pytest.raises(SnapshotError, match=r"tree hash|cannot resolve"):
            tree_hash_git(tmp_path / "empty")


def test_reject_patch_path_variants() -> None:
    _reject_patch_path("/dev/null", context="ok")
    _reject_patch_path("", context="ok")
    with pytest.raises(PatchRejectError, match="NUL"):
        _reject_patch_path("foo\x00bar", context="x")
    with pytest.raises(PatchRejectError, match="absolute"):
        _reject_patch_path("~/.ssh/id_rsa", context="x")
    with pytest.raises(PatchRejectError, match="absolute"):
        _reject_patch_path("\\\\server\\share", context="x")
    with pytest.raises(PatchRejectError, match="traversal"):
        _reject_patch_path("a/../../etc/passwd", context="x")


def test_reject_patch_content_rename_copy_and_type() -> None:
    with pytest.raises(PatchRejectError, match="absolute"):
        _reject_patch_content("rename from /etc/passwd\n")
    with pytest.raises(PatchRejectError, match="absolute"):
        _reject_patch_content("copy to C:/Windows/x\n")
    with pytest.raises(PatchRejectError, match=r"symlink|submodule"):
        _reject_patch_content("type symlink\n")
    with pytest.raises(PatchRejectError, match=r"symlink|submodule"):
        _reject_patch_content("old mode 160000\n")
    with pytest.raises(PatchRejectError, match="binary"):
        _reject_patch_content("GIT binary patch\n")
    # allow_binary permits binary markers
    _reject_patch_content("Binary files a/x and b/x differ\n", allow_binary=True)


def test_apply_patch_requires_input(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    with pytest.raises(PatchRejectError, match="required"):
        apply_patch_to_worktree(wt)


def test_apply_patch_to_worktree_success(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path / "repo")
    patch = (
        "diff --git a/src/Main.lean b/src/Main.lean\n"
        "--- a/src/Main.lean\n"
        "+++ b/src/Main.lean\n"
        "@@ -1 +1,2 @@\n"
        " -- main\n"
        "+-- patched\n"
    )
    digest = apply_patch_to_worktree(repo, patch_text=patch)
    assert len(digest) == 64
    assert "-- patched" in (repo / "src" / "Main.lean").read_text(encoding="utf-8")


def test_apply_patch_from_path_inside_worktree(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path / "repo")
    # Keep the on-disk patch input gitignored so porcelain checks stay clean.
    (repo / ".gitignore").write_bytes(b"candidate.patch\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "ignore-patch")
    patch_body = (
        "diff --git a/src/Main.lean b/src/Main.lean\n"
        "--- a/src/Main.lean\n"
        "+++ b/src/Main.lean\n"
        "@@ -1 +1,2 @@\n"
        " -- main\n"
        "+-- via path\n"
    )
    patch_file = repo / "candidate.patch"
    patch_file.write_bytes(patch_body.encode("utf-8"))
    digest = apply_patch_to_worktree(repo, patch_path=patch_file)
    assert len(digest) == 64


def test_apply_patch_rejects_failed_hunk(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path / "repo")
    bad = (
        "diff --git a/src/Main.lean b/src/Main.lean\n"
        "--- a/src/Main.lean\n"
        "+++ b/src/Main.lean\n"
        "@@ -1 +1 @@\n"
        "-not the actual content\n"
        "+replacement\n"
    )
    with pytest.raises(PatchRejectError, match=r"apply|failed|hunk|corrupt"):
        apply_patch_to_worktree(repo, patch_text=bad)


def test_resolve_patch_bytes_text_path_and_missing(tmp_path: Path) -> None:
    raw, digest = resolve_patch_bytes(tmp_path, patch_text="hello", patch_path=None)
    assert raw == b"hello"
    assert digest == sha256_text("hello")

    patch = tmp_path / "p.patch"
    patch.write_bytes(b"abc")
    raw2, dig2 = resolve_patch_bytes(tmp_path, patch_text=None, patch_path="p.patch")
    assert raw2 == b"abc"
    assert dig2 is not None and len(dig2) == 64

    with pytest.raises(PatchRejectError, match="does not exist"):
        resolve_patch_bytes(tmp_path, patch_text=None, patch_path="missing.patch")

    none_raw, none_dig = resolve_patch_bytes(tmp_path, patch_text=None, patch_path=None)
    assert none_raw is None and none_dig is None


def test_copy_tree_keeps_extraction_json_skips_cas_and_caches(tmp_path: Path) -> None:
    """Snapshot copy must not re-ingest ``.lpe/artifacts`` or tooling caches."""
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    (src / ".lpe" / "artifacts" / "sha256" / "ab").mkdir(parents=True)
    (src / ".lpe" / "artifacts" / "sha256" / "ab" / "abcd").write_bytes(b"cas")
    (src / ".lpe" / "lean-extraction.json").write_text('{"ok":true}\n', encoding="utf-8")
    (src / ".mypy_cache" / "3.12").mkdir(parents=True)
    (src / ".mypy_cache" / "3.12" / "x.meta.json").write_text("{}", encoding="utf-8")
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "mod.cpython-312.pyc").write_bytes(b"\0")
    (src / "Main.lean").write_text("def x := 1\n", encoding="utf-8")

    _copy_tree(src, dest)

    assert (dest / "Main.lean").is_file()
    assert (dest / ".lpe" / "lean-extraction.json").is_file()
    assert not (dest / ".lpe" / "artifacts").exists()
    assert not (dest / ".mypy_cache").exists()
    assert not (dest / "__pycache__").exists()


def test_create_snapshot_pair_copy_fallback(tmp_path: Path) -> None:
    # Non-git directory → copy-based snapshots.
    project = tmp_path / "fixture"
    project.mkdir()
    (project / "Main.lean").write_text("def x := 1\n", encoding="utf-8")
    (project / "lean-toolchain").write_text("leanprover/lean4:v4.14.0\n", encoding="utf-8")
    session = tmp_path / "session"
    pair = create_snapshot_pair(
        project,
        base_commit="0" * 40,
        head_commit=None,
        patch_text=(
            "diff --git a/Main.lean b/Main.lean\n"
            "--- a/Main.lean\n"
            "+++ b/Main.lean\n"
            "@@ -1 +1,2 @@\n"
            " def x := 1\n"
            "+-- note\n"
        ),
        session_root=session,
    )
    assert pair.git_backed is False
    assert pair.base_path.is_dir()
    assert pair.candidate_path.is_dir()
    assert pair.base_tree_hash
    assert pair.candidate_tree_hash
    assert pair.patch_sha256 is not None
    cleanup_snapshot_pair(pair)
    assert not session.exists()


def test_create_snapshot_pair_git_with_patch(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path / "repo")
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    session = tmp_path / "sess"
    pair = create_snapshot_pair(
        repo,
        base_commit=head,
        head_commit=None,
        patch_text=(
            "diff --git a/src/Main.lean b/src/Main.lean\n"
            "--- a/src/Main.lean\n"
            "+++ b/src/Main.lean\n"
            "@@ -1 +1,2 @@\n"
            " -- main\n"
            "+-- cand\n"
        ),
        session_root=session,
    )
    assert pair.git_backed is True
    assert pair.base_commit == head
    assert pair.candidate_commit != head
    assert "-- cand" in (pair.candidate_path / "src" / "Main.lean").read_text(encoding="utf-8")
    cleanup_snapshot_pair(pair, repository=repo)
    assert not session.exists()


def test_create_snapshot_pair_git_with_head_commit(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path / "repo")
    base = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (repo / "src" / "Main.lean").write_text("-- main\n-- second\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "second")
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    session = tmp_path / "sess2"
    pair = create_snapshot_pair(
        repo,
        base_commit=base,
        head_commit=head,
        session_root=session,
    )
    assert pair.git_backed is True
    assert pair.base_commit == base
    assert pair.candidate_commit == head
    cleanup_snapshot_pair(pair, repository=repo)


def test_create_snapshot_pair_requires_patch_when_no_head(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path / "repo")
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    with pytest.raises(PatchRejectError, match="patch"):
        create_snapshot_pair(
            repo,
            base_commit=head,
            head_commit=None,
            session_root=tmp_path / "sess3",
        )


def test_create_snapshot_pair_bad_head_commit(tmp_path: Path) -> None:
    repo = _init_git_repo(tmp_path / "repo")
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    with pytest.raises(SnapshotError, match="head_commit"):
        create_snapshot_pair(
            repo,
            base_commit=head,
            head_commit="deadbeef" * 5,
            session_root=tmp_path / "sess4",
        )


def test_toolchain_and_lake_manifest_hashes(tmp_path: Path) -> None:
    project = tmp_path / "p"
    project.mkdir()
    empty_hash = toolchain_file_hash(project)
    assert empty_hash == sha256_text("")
    (project / "lean-toolchain").write_text("leanprover/lean4:v4.14.0\n", encoding="utf-8")
    assert toolchain_file_hash(project) != empty_hash
    assert lake_manifest_hash(project) is None
    (project / "lakefile.toml").write_text('name = "x"\n', encoding="utf-8")
    assert lake_manifest_hash(project) is not None


def test_cleanup_snapshot_pair_non_git(tmp_path: Path) -> None:
    session = tmp_path / "s"
    base = session / "base"
    cand = session / "candidate"
    base.mkdir(parents=True)
    cand.mkdir(parents=True)
    (base / "f").write_text("x", encoding="utf-8")
    pair = SnapshotPair(
        session_root=session,
        base_path=base,
        candidate_path=cand,
        base_commit="b",
        candidate_commit="c",
        base_tree_hash="t1",
        candidate_tree_hash="t2",
        patch_sha256=None,
        git_backed=False,
    )
    cleanup_snapshot_pair(pair)
    assert not session.exists()


def test_apply_patch_dirty_worktree_rejected(tmp_path: Path) -> None:
    """Untracked extras after apply should fail closed."""
    repo = _init_git_repo(tmp_path / "repo")
    patch_body = (
        "diff --git a/src/Main.lean b/src/Main.lean\n"
        "--- a/src/Main.lean\n"
        "+++ b/src/Main.lean\n"
        "@@ -1 +1,2 @@\n"
        " -- main\n"
        "+-- ok\n"
    )

    import lpe.workspace.snapshots as snap_mod

    real_run_git = snap_mod._run_git

    def _flaky(repository: Path, *args: str) -> subprocess.CompletedProcess[str]:
        result = real_run_git(repository, *args)
        if args and args[0] == "status" and "--porcelain" in args:
            return subprocess.CompletedProcess(
                args=["git", *args],
                returncode=0,
                stdout="?? sneaky.txt\n",
                stderr="",
            )
        return result

    with patch("lpe.workspace.snapshots._run_git", side_effect=_flaky):
        with pytest.raises(PatchRejectError, match="untracked"):
            apply_patch_to_worktree(repo, patch_text=patch_body)


def test_commit_detached_tree_failure_mocked(tmp_path: Path) -> None:
    from lpe.workspace.snapshots import commit_detached_tree

    wt = tmp_path / "wt"
    wt.mkdir()

    def _fail(repository: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["git", *args],
            returncode=1,
            stdout="",
            stderr="add failed",
        )

    with patch("lpe.workspace.snapshots._run_git", side_effect=_fail):
        with pytest.raises(SnapshotError, match=r"git add|add failed"):
            commit_detached_tree(wt)
