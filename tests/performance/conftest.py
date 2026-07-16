"""Performance suite fixtures and optional benchmark artifact emit."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.performance.metrics import maybe_write_benchmark_artifact

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def lean_diff_repo(tmp_path: Path, example_project: Path) -> tuple[Path, str, str]:
    """Small git repo with a normal-PR-sized Lean declaration change."""
    repo = tmp_path / "diff-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "perf@example.org"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Perf"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    shutil.copytree(
        example_project / ".lean-project-contract",
        repo / ".lean-project-contract",
    )
    lean_dir = repo / "Example" / "Public"
    lean_dir.mkdir(parents=True)
    (lean_dir / "Comparison.lean").write_text(
        "def comparisonFunctor : Nat := 0\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text("perf fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "base"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (lean_dir / "Comparison.lean").write_text(
        "def comparisonFunctor : Nat := 1\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "head"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repo, base, head


@pytest.fixture(scope="session", autouse=True)
def _emit_benchmarks_on_session_end() -> None:
    yield
    maybe_write_benchmark_artifact(_REPO_ROOT)
