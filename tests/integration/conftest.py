"""Integration fixtures (git seed, ledger paths; Lean Docker optional via @pytest.mark.docker)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def ledger_path(tmp_path: Path) -> Path:
    return tmp_path / "integration-ledger.sqlite3"


@pytest.fixture
def temp_project_copy(tmp_path: Path, example_project: Path) -> Path:
    """Isolated copy of the example project for CLI mutations."""
    dest = tmp_path / "project"
    shutil.copytree(example_project, dest)
    return dest


@pytest.fixture
def git_seeded_project(tmp_path: Path, example_project: Path) -> Path:
    """Minimal git repo with contract seeded from the example project."""
    repo = tmp_path / "git-project"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "integration@example.org"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Integration"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    shutil.copytree(
        example_project / ".lean-project-contract",
        repo / ".lean-project-contract",
    )
    (repo / "README.md").write_text("integration fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


@pytest.fixture
def escalate_decision_path(tmp_path: Path) -> Path:
    path = tmp_path / "decision-escalate.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "review-integration-escalate",
                "packet_id": "packet_pending",
                "reviewer_id": "r3-reviewer",
                "reviewer_roles": [],
                "decision": "REQUEST_REPAIR",
                "confidence": 80,
                "rationale": "integration smoke: escalate for repair",
                "review_minutes": 30.0,
                "required_repair": "Clarify signature change intent",
            }
        ),
        encoding="utf-8",
    )
    return path
