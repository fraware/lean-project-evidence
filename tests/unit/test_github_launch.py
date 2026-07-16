from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"


def _load_github_launch():
    spec = importlib.util.spec_from_file_location("github_launch", SCRIPTS / "github_launch.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_issue_body_includes_dependencies() -> None:
    github_launch = _load_github_launch()
    body = github_launch.issue_body(
        {
            "issue_id": "ISSUE-002",
            "milestone": "M0",
            "depends_on": "EPIC-001",
            "acceptance_criteria": "Models reject unknown fields.",
            "title": "Example",
            "labels": "type:feature",
        }
    )
    assert "ISSUE-002" in body
    assert "EPIC-001" in body
    assert "Models reject unknown fields." in body
    assert "backlog/issues.csv" in body


def test_milestone_title_mapping() -> None:
    github_launch = _load_github_launch()
    assert github_launch.milestone_title("M0") == "M0 Foundation"
    assert github_launch.milestone_title("M7") == "M7 Project-Targeted Synthesis"


def test_import_issues_dry_run() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS / "github_launch.py"), "import-issues"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "EPIC-001" in completed.stdout
    assert "Dry run" in completed.stdout


def test_labels_dry_run() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS / "github_launch.py"), "labels"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "type:epic" in completed.stdout


@pytest.mark.parametrize(
    "command",
    ["labels", "milestones", "import-issues"],
)
def test_github_launch_dry_run_exit_code(command: str) -> None:
    subprocess.run(
        [sys.executable, str(SCRIPTS / "github_launch.py"), command],
        cwd=REPO_ROOT,
        check=True,
    )
