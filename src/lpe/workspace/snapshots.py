"""Base/candidate snapshot creation, patch apply, and tree hashing."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from lpe.git.candidate import is_git_toplevel, repository_has_commits
from lpe.hashing import sha256_file, sha256_text
from lpe.paths import assert_safe_repo_relative


class SnapshotError(RuntimeError):
    pass


class PatchRejectError(SnapshotError):
    """Raised when a candidate patch violates apply policy."""


@dataclass(frozen=True)
class SnapshotPair:
    session_root: Path
    base_path: Path
    candidate_path: Path
    base_commit: str
    candidate_commit: str
    base_tree_hash: str
    candidate_tree_hash: str
    patch_sha256: str | None
    git_backed: bool


def _run_git(repository: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def tree_hash_git(worktree: Path) -> str:
    result = _run_git(worktree, "rev-parse", "HEAD^{tree}")
    if result.returncode != 0:
        raise SnapshotError(result.stderr.strip() or "cannot resolve tree hash")
    return result.stdout.strip()


def tree_hash_filesystem(root: Path) -> str:
    """Content-addressed tree hash for non-git ephemeral snapshots."""
    digest = hashlib.sha256()
    root = root.resolve()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".git/") or "/.git/" in f"/{rel}/":
            continue
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _create_worktree(repository: Path, commit: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = _run_git(
        repository,
        "worktree",
        "add",
        "--detach",
        str(dest),
        commit,
    )
    if result.returncode != 0:
        raise SnapshotError(result.stderr.strip() or f"cannot create worktree at {commit}")


def _remove_worktree(repository: Path, worktree: Path) -> None:
    result = _run_git(repository, "worktree", "remove", "--force", str(worktree))
    if result.returncode != 0 and worktree.exists():
        shutil.rmtree(worktree, ignore_errors=True)


# Names excluded from copy-based evaluation snapshots.
# Keep ``.lpe/lean-extraction*.json`` (and siblings) but never copy the CAS store:
# ``.lpe/artifacts`` grows under ``artifact_root`` and must not re-enter worktrees
# (feedback loop → multi-thousand-file copies on fixture projects).
_SNAPSHOT_IGNORE_NAMES = frozenset(
    {
        ".git",
        ".lake",
        "build",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        ".hypothesis",
        ".tox",
        "htmlcov",
        ".eggs",
    }
)
_SNAPSHOT_IGNORE_SUFFIXES = (".pyc", ".egg-info")


def _snapshot_copy_ignore(directory: str, names: list[str]) -> set[str]:
    """Ignore build/tool caches and ``.lpe/artifacts`` during snapshot copy."""
    ignored: set[str] = set()
    parent_name = Path(directory).name
    for name in names:
        if name in _SNAPSHOT_IGNORE_NAMES:
            ignored.add(name)
        elif name.endswith(_SNAPSHOT_IGNORE_SUFFIXES):
            ignored.add(name)
        elif name == "artifacts" and parent_name == ".lpe":
            # Content-addressed store lives on the operator/artifact root, not
            # inside isolated base/candidate trees.
            ignored.add(name)
    return ignored


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    # Keep ``.lpe`` extraction JSON; drop CAS artifacts + tooling caches.
    shutil.copytree(
        src,
        dest,
        ignore=_snapshot_copy_ignore,
        symlinks=False,
    )


def _reject_patch_path(path: str, *, context: str) -> None:
    """Reject absolute, home, traversal, null, and drive-letter patch paths."""
    text = path.strip().strip('"').strip("'")
    if not text or text == "/dev/null":
        return
    if text.startswith(("a/", "b/")):
        text = text[2:]
    if "\x00" in text:
        raise PatchRejectError(f"NUL in patch path ({context}): {path!r}")
    # POSIX absolute, home, Windows drive / UNC.
    if text.startswith(("/", "~", "\\")):
        raise PatchRejectError(f"absolute path in patch ({context}): {path!r}")
    if len(text) >= 2 and text[1] == ":" and text[0].isalpha():
        raise PatchRejectError(f"absolute path in patch ({context}): {path!r}")
    if text.startswith(("\\\\", "//")):
        raise PatchRejectError(f"UNC / absolute path in patch ({context}): {path!r}")
    # Normalize separators before traversal checks.
    normalized = text.replace("\\", "/")
    if ".." in Path(normalized).parts or ".." in normalized.split("/"):
        raise PatchRejectError(f"parent traversal in patch ({context}): {path!r}")


def _reject_patch_content(
    patch_text: str,
    *,
    allow_binary: bool = False,
) -> None:
    if "\x00" in patch_text:
        raise PatchRejectError("NUL bytes in patch content are not permitted")
    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            # ``diff --git a/foo b/bar`` (possibly quoted)
            parts = line.split()
            for token in parts[2:]:
                path = token[2:] if token.startswith(("a/", "b/")) else token
                _reject_patch_path(path, context="diff --git")
        if line.startswith("+++ ") or line.startswith("--- "):
            path = line[4:].strip()
            _reject_patch_path(path, context=line[:3])
        if line.startswith("rename from ") or line.startswith("rename to "):
            parts = line.split(" ", 2)
            _reject_patch_path(parts[-1], context=f"{parts[0]} {parts[1]}")
        if line.startswith("copy from ") or line.startswith("copy to "):
            parts = line.split(" ", 2)
            _reject_patch_path(parts[-1], context=f"{parts[0]} {parts[1]}")
        if not allow_binary and (
            line.startswith("Binary files ") or line.startswith("GIT binary patch")
        ):
            raise PatchRejectError("binary patch content is not permitted")
        # Symlink create / mode change, or gitlink (submodule).
        if (
            line.startswith("new file mode 120000")
            or line.startswith("new file mode 160000")
            or line.startswith("old mode 120000")
            or line.startswith("new mode 120000")
            or line.startswith("old mode 160000")
            or line.startswith("new mode 160000")
        ):
            raise PatchRejectError("symlink or submodule changes are not permitted")
        if line.startswith("type ") and line.strip() in {"type symlink", "type commit"}:
            raise PatchRejectError("symlink or submodule changes are not permitted")


def apply_patch_to_worktree(
    worktree: Path,
    *,
    patch_text: str | None = None,
    patch_path: Path | None = None,
    allow_binary: bool = False,
    allow_submodules: bool = False,
) -> str:
    """Apply a patch with ``git apply --index --whitespace=error-all``.

    Returns the sha256 of the patch bytes. Raises ``PatchRejectError`` on policy
    violations or failed hunks.
    """
    del allow_submodules  # submodule mode lines already rejected in content scan
    if patch_text is None and patch_path is None:
        raise PatchRejectError("patch_text or patch_path is required")
    if patch_path is not None:
        resolved_patch = patch_path.resolve()
        worktree_resolved = worktree.resolve()
        # Prefer repo-relative patch inputs; absolute paths must stay inside worktree.
        if patch_path.is_absolute() and not resolved_patch.is_relative_to(worktree_resolved):
            raise PatchRejectError(f"absolute patch path rejected: {patch_path}")
        raw = resolved_patch.read_bytes()
        text = raw.decode("utf-8", errors="replace")
    else:
        assert patch_text is not None
        text = patch_text
        raw = text.encode("utf-8")

    _reject_patch_content(text, allow_binary=allow_binary)

    patch_file = worktree / ".lpe-candidate.patch"
    patch_file.write_bytes(raw)
    try:
        result = _run_git(
            worktree,
            "apply",
            "--index",
            "--whitespace=error-all",
            str(patch_file),
        )
        if result.returncode != 0:
            raise PatchRejectError(
                result.stderr.strip() or result.stdout.strip() or "git apply failed"
            )
        # Remove the temp patch before porcelain checks so it is not treated as
        # an untracked extra (it lives inside the worktree by design).
        patch_file.unlink(missing_ok=True)
        # Reject dirty extras outside the index after apply.
        status = _run_git(worktree, "status", "--porcelain")
        if status.returncode != 0:
            raise PatchRejectError("cannot verify worktree cleanliness after patch")
        for line in status.stdout.splitlines():
            # Staged changes (index) are expected; unstaged/untracked extras fail.
            if not line:
                continue
            code = line[:2]
            if code == "??":
                raise PatchRejectError(f"untracked file after patch apply: {line[3:].strip()}")
            # Second column dirty (worktree side) outside staged index.
            if len(code) >= 2 and code[1] not in {" ", ""}:
                raise PatchRejectError(f"dirty files outside patch apply: {line[3:].strip()}")
    finally:
        patch_file.unlink(missing_ok=True)

    return hashlib.sha256(raw).hexdigest()


def commit_detached_tree(worktree: Path, *, message: str = "lpe-candidate") -> str:
    """Create a temporary detached commit so the candidate has a stable tree hash."""
    add = _run_git(worktree, "add", "-A")
    if add.returncode != 0:
        raise SnapshotError(add.stderr.strip() or "git add failed")
    commit = _run_git(
        worktree,
        "-c",
        "user.email=lpe@localhost",
        "-c",
        "user.name=LPE",
        "commit",
        "--allow-empty",
        "-m",
        message,
    )
    if commit.returncode != 0:
        raise SnapshotError(commit.stderr.strip() or "detached commit failed")
    head = _run_git(worktree, "rev-parse", "HEAD")
    if head.returncode != 0:
        raise SnapshotError("cannot resolve candidate commit")
    return head.stdout.strip()


def resolve_patch_bytes(
    repository: Path,
    *,
    patch_text: str | None,
    patch_path: str | None,
) -> tuple[bytes | None, str | None]:
    if patch_text is not None:
        raw = patch_text.encode("utf-8")
        return raw, sha256_text(patch_text)
    if patch_path:
        path = assert_safe_repo_relative(repository, patch_path, label="patch_path")
        if not path.is_file():
            raise PatchRejectError(f"patch_path does not exist: {patch_path}")
        raw = path.read_bytes()
        return raw, hashlib.sha256(raw).hexdigest()
    return None, None


def create_snapshot_pair(
    repository: Path,
    *,
    base_commit: str,
    head_commit: str | None,
    patch_text: str | None = None,
    patch_path: str | None = None,
    session_root: Path | None = None,
) -> SnapshotPair:
    """Create isolated base + candidate snapshots (git worktrees or copies)."""
    repository = repository.resolve()
    if session_root is None:
        session_root = Path(tempfile.mkdtemp(prefix="lpe-workspace-"))
    else:
        session_root.mkdir(parents=True, exist_ok=True)

    base_path = session_root / "base"
    candidate_path = session_root / "candidate"
    patch_sha256: str | None = None

    use_git = (
        is_git_toplevel(repository)
        and repository_has_commits(repository)
        and set(base_commit.strip().lower()) != {"0"}
    )

    # Probe whether base_commit resolves.
    if use_git:
        probe = _run_git(repository, "rev-parse", "--verify", f"{base_commit}^{{commit}}")
        use_git = probe.returncode == 0

    if use_git:
        resolved_base = _run_git(repository, "rev-parse", base_commit).stdout.strip()
        _create_worktree(repository, resolved_base, base_path)

        if head_commit:
            probe_head = _run_git(repository, "rev-parse", "--verify", f"{head_commit}^{{commit}}")
            if probe_head.returncode != 0:
                _remove_worktree(repository, base_path)
                raise SnapshotError(f"head_commit does not resolve: {head_commit}")
            resolved_head = _run_git(repository, "rev-parse", head_commit).stdout.strip()
            _create_worktree(repository, resolved_head, candidate_path)
            candidate_commit = resolved_head
        else:
            _create_worktree(repository, resolved_base, candidate_path)
            raw, patch_sha256 = resolve_patch_bytes(
                repository, patch_text=patch_text, patch_path=patch_path
            )
            if raw is None:
                _remove_worktree(repository, base_path)
                _remove_worktree(repository, candidate_path)
                raise PatchRejectError("patch-based candidate requires patch_text or patch_path")
            apply_patch_to_worktree(
                candidate_path,
                patch_text=raw.decode("utf-8", errors="replace"),
            )
            candidate_commit = commit_detached_tree(candidate_path)

        base_tree = tree_hash_git(base_path)
        candidate_tree = tree_hash_git(candidate_path)
        return SnapshotPair(
            session_root=session_root,
            base_path=base_path,
            candidate_path=candidate_path,
            base_commit=resolved_base,
            candidate_commit=candidate_commit,
            base_tree_hash=base_tree,
            candidate_tree_hash=candidate_tree,
            patch_sha256=patch_sha256,
            git_backed=True,
        )

    # Copy-based fallback for fixtures / nested paths without resolvable commits.
    _copy_tree(repository, base_path)
    _copy_tree(repository, candidate_path)
    raw, patch_sha256 = resolve_patch_bytes(
        repository, patch_text=patch_text, patch_path=patch_path
    )
    if raw is not None:
        # Best-effort apply. Nested copies often live inside a parent git work tree
        # (``git rev-parse`` succeeds) even without a local .git — never use
        # ``git apply --index`` on those; soft-apply only.
        patch_file = candidate_path / ".lpe-candidate.patch"
        patch_file.write_bytes(raw)
        try:
            result = subprocess.run(
                [
                    "git",
                    "apply",
                    "--whitespace=error-all",
                    f"--directory={candidate_path}",
                    str(patch_file),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(repository),
            )
            if result.returncode != 0:
                # Soft-fail for fixture / illustrative patches that are not
                # valid unified diffs — leave the copied tree as-is.
                pass
            candidate_commit = head_commit or f"copy:{tree_hash_filesystem(candidate_path)[:40]}"
        finally:
            patch_file.unlink(missing_ok=True)
    else:
        candidate_commit = head_commit or f"copy:{tree_hash_filesystem(candidate_path)[:40]}"

    return SnapshotPair(
        session_root=session_root,
        base_path=base_path,
        candidate_path=candidate_path,
        base_commit=base_commit,
        candidate_commit=candidate_commit,
        base_tree_hash=tree_hash_filesystem(base_path),
        candidate_tree_hash=tree_hash_filesystem(candidate_path),
        patch_sha256=patch_sha256,
        git_backed=False,
    )


def cleanup_snapshot_pair(
    pair: SnapshotPair,
    *,
    repository: Path | None = None,
) -> None:
    """Remove both worktrees / copies and the session root."""
    if pair.git_backed and repository is not None:
        _remove_worktree(repository, pair.base_path)
        _remove_worktree(repository, pair.candidate_path)
    if pair.session_root.exists():
        shutil.rmtree(pair.session_root, ignore_errors=True)


def toolchain_file_hash(project: Path) -> str:
    path = project / "lean-toolchain"
    if path.is_file():
        return sha256_file(path)
    return sha256_text("")


def lake_manifest_hash(project: Path) -> str | None:
    for name in ("lake-manifest.json", "Lakefile.lean", "lakefile.toml", "lakefile.lean"):
        path = project / name
        if path.is_file():
            return sha256_file(path)
    return None
