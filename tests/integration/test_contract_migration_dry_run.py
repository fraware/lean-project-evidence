"""Contract migrate-dry-run: plan rewrites without mutating YAML."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from lpe.cli import app
from lpe.contract.migration import dry_run_contract_migration
from lpe.models import LEGACY_SCHEMA_VERSION, SCHEMA_VERSION

runner = CliRunner()


def test_dry_run_no_op_when_already_at_target(example_project: Path) -> None:
    # Example contracts remain on 0.1.0 while SCHEMA_VERSION is 0.2.0.
    report = dry_run_contract_migration(example_project, target_version=LEGACY_SCHEMA_VERSION)
    assert report["ok"] is True
    assert report["action"] == "no_op"
    assert report["mutated"] is False
    assert report["files_to_rewrite"] == []
    assert "18_CONTRACT_MIGRATION" in report["bump_path"]


def test_dry_run_would_rewrite_0_1_to_current(example_project: Path) -> None:
    report = dry_run_contract_migration(example_project, target_version=SCHEMA_VERSION)
    assert report["ok"] is True
    assert report["action"] == "would_rewrite"
    assert report["mutated"] is False
    assert len(report["files_to_rewrite"]) == 5


def test_dry_run_refuses_unsupported_target(example_project: Path, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    shutil.copytree(example_project, dest)
    before = {
        name: (dest / ".lean-project-contract" / name).read_text(encoding="utf-8")
        for name in (
            "project.yaml",
            "terminology.yaml",
            "obligations.yaml",
            "policies.yaml",
            "review.yaml",
        )
    }
    report = dry_run_contract_migration(dest, target_version="0.3.0")
    assert report["ok"] is False
    assert report["action"] == "would_refuse"
    assert report["mutated"] is False
    assert report["target_version"] == "0.3.0"
    after = {
        name: (dest / ".lean-project-contract" / name).read_text(encoding="utf-8")
        for name in before
    }
    assert before == after


def test_dry_run_would_rewrite_when_files_differ(
    example_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import lpe.contract.migration as migration
    import lpe.models as models

    dest = tmp_path / "proj"
    shutil.copytree(example_project, dest)
    monkeypatch.setattr(
        models,
        "SUPPORTED_SCHEMA_VERSIONS",
        frozenset({SCHEMA_VERSION, LEGACY_SCHEMA_VERSION, "0.1.1"}),
    )
    monkeypatch.setattr(
        migration,
        "SUPPORTED_SCHEMA_VERSIONS",
        frozenset({SCHEMA_VERSION, LEGACY_SCHEMA_VERSION, "0.1.1"}),
    )

    report = dry_run_contract_migration(dest, target_version="0.1.1")
    assert report["ok"] is True
    assert report["action"] == "would_rewrite"
    assert report["mutated"] is False
    assert len(report["files_to_rewrite"]) == 5
    raw = yaml.safe_load(
        (dest / ".lean-project-contract" / "project.yaml").read_text(encoding="utf-8")
    )
    assert raw["schema_version"] == LEGACY_SCHEMA_VERSION


def test_cli_migrate_dry_run(example_project: Path) -> None:
    result = runner.invoke(
        app,
        [
            "contract",
            "migrate-dry-run",
            str(example_project),
            "--to",
            LEGACY_SCHEMA_VERSION,
        ],
    )
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert data["action"] == "no_op"
    assert data["mutated"] is False


def test_cli_migrate_dry_run_refuses_future(example_project: Path) -> None:
    result = runner.invoke(
        app, ["contract", "migrate-dry-run", str(example_project), "--to", "9.9.9"]
    )
    assert result.exit_code == 1
    combined = result.stdout + (result.stderr or "")
    assert "would_refuse" in combined or "not in SUPPORTED" in combined
