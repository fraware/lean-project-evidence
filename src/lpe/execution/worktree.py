from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class WorktreeError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorktreeSession:
    """An isolated git worktree for candidate execution."""

    repository: Path
    worktree_path: Path
    head_commit: str
    artifact_dir: Path
    log_dir: Path

    def cleanup(self) -> None:
        result = subprocess.run(
            ["git", "-C", str(self.repository), "worktree", "remove", "--force", str(self.worktree_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 and self.worktree_path.exists():
            shutil.rmtree(self.worktree_path, ignore_errors=True)


def create_isolated_worktree(
    repository: Path,
    *,
    head_commit: str,
    base_dir: Path | None = None,
) -> WorktreeSession:
    """Create an isolated worktree checked out at head_commit."""
    repository = repository.resolve()
    if base_dir is None:
        base_dir = Path(tempfile.mkdtemp(prefix="lpe-worktree-"))
    else:
        base_dir.mkdir(parents=True, exist_ok=True)

    worktree_path = base_dir / "repo"
    artifact_dir = base_dir / "artifacts"
    log_dir = base_dir / "logs"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "worktree",
            "add",
            "--detach",
            str(worktree_path),
            head_commit,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise WorktreeError(result.stderr.strip() or f"cannot create worktree at {head_commit}")

    return WorktreeSession(
        repository=repository,
        worktree_path=worktree_path,
        head_commit=head_commit,
        artifact_dir=artifact_dir,
        log_dir=log_dir,
    )


def store_execution_logs(session: WorktreeSession, *, stdout: str, stderr: str) -> tuple[Path, Path]:
    stdout_path = session.log_dir / "stdout.log"
    stderr_path = session.log_dir / "stderr.log"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    return stdout_path, stderr_path
