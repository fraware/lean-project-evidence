"""Unit coverage for contract migration (no network; integration also covers CLI)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from lpe.contract.migration import (
    apply_contract_migration,
    check_contract_schema_versions,
    dry_run_contract_migration,
    register_migration_rewriter,
)
from lpe.models import LEGACY_SCHEMA_VERSION, SCHEMA_VERSION


def test_check_contract_schema_versions_ok(example_project: Path) -> None:
    report = check_contract_schema_versions(example_project)
    assert "versions" in report
    assert len(report["versions"]) == 5


def test_check_contract_schema_versions_missing(tmp_path: Path) -> None:
    (tmp_path / ".lean-project-contract").mkdir()
    with pytest.raises(ValueError, match="missing contract file"):
        check_contract_schema_versions(tmp_path)


def test_check_contract_schema_versions_unsupported(example_project: Path, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    shutil.copytree(example_project, dest)
    path = dest / ".lean-project-contract" / "project.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["schema_version"] = "9.9.9"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported schema_version"):
        check_contract_schema_versions(dest)


def test_apply_migration_write_false_is_plan(example_project: Path) -> None:
    plan = apply_contract_migration(example_project, write=False)
    assert plan["written"] is False
    assert plan["mutated"] is False


def test_apply_migration_write_true(example_project: Path, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    shutil.copytree(example_project, dest)
    result = apply_contract_migration(dest, target_version=SCHEMA_VERSION, write=True)
    assert result["written"] is True
    assert result["action"] == "rewrote"
    assert len(result["written_files"]) == 5
    project = yaml.safe_load(
        (dest / ".lean-project-contract" / "project.yaml").read_text(encoding="utf-8")
    )
    assert project["schema_version"] == SCHEMA_VERSION


def test_apply_migration_no_op_write(example_project: Path, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    shutil.copytree(example_project, dest)
    apply_contract_migration(dest, target_version=SCHEMA_VERSION, write=True)
    again = apply_contract_migration(dest, target_version=SCHEMA_VERSION, write=True)
    assert again["action"] == "no_op"
    assert again["written"] is False


def test_apply_migration_refuses_unsupported(example_project: Path, tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    shutil.copytree(example_project, dest)
    result = apply_contract_migration(dest, target_version="0.9.0", write=True)
    assert result["ok"] is False
    assert result["written"] is False
    # Files unchanged at legacy.
    project = yaml.safe_load(
        (dest / ".lean-project-contract" / "project.yaml").read_text(encoding="utf-8")
    )
    assert project["schema_version"] == LEGACY_SCHEMA_VERSION


def test_register_custom_rewriter(
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

    def _rewriter(raw: dict, _from: str, to: str) -> None:
        raw["schema_version"] = to
        raw["migrated_by"] = "unit-test"

    register_migration_rewriter(LEGACY_SCHEMA_VERSION, "0.1.1", _rewriter)
    result = apply_contract_migration(dest, target_version="0.1.1", write=True)
    assert result["written"] is True
    project = yaml.safe_load(
        (dest / ".lean-project-contract" / "project.yaml").read_text(encoding="utf-8")
    )
    assert project["schema_version"] == "0.1.1"
    assert project["migrated_by"] == "unit-test"


def test_dry_run_empty_target_raises(example_project: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        dry_run_contract_migration(example_project, target_version="  ")
