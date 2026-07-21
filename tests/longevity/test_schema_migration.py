"""Schema migration drill: unknown refused; supported loads; bump path documented.

See ``docs/18_CONTRACT_MIGRATION.md``. This test does **not** mutate
``SUPPORTED_SCHEMA_VERSIONS`` — it proves fail-closed refusal and documents
how a future minor bump would be accepted.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from lpe.cli import app
from lpe.contract.loader import load_contract
from lpe.contract.migration import check_contract_schema_versions
from lpe.models import SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS

runner = CliRunner()

BUMP_PATH_HINT = "docs/18_CONTRACT_MIGRATION.md"


@pytest.mark.longevity
def test_unknown_schema_version_refused(repository_root: Path) -> None:
    fixture = repository_root / "tests" / "fixtures" / "contracts" / "unsupported-schema-version"
    with pytest.raises(ValueError, match="unsupported schema_version"):
        check_contract_schema_versions(fixture)

    result = runner.invoke(app, ["contract", "schema-check", str(fixture)])
    assert result.exit_code == 1
    combined = (result.stdout + (result.stderr or "")).lower()
    assert "unsupported schema_version" in combined
    assert "bump path" in combined or "supported" in combined


@pytest.mark.longevity
def test_supported_schema_version_loads(example_project: Path) -> None:
    assert SCHEMA_VERSION in SUPPORTED_SCHEMA_VERSIONS
    assert "0.1.0" in SUPPORTED_SCHEMA_VERSIONS
    report = check_contract_schema_versions(example_project)
    # Contracts may remain on 0.1.0 while writers emit SCHEMA_VERSION 0.2.0.
    assert set(report["versions"].values()).issubset(SUPPORTED_SCHEMA_VERSIONS)
    contract = load_contract(example_project)
    assert contract.project.schema_version in SUPPORTED_SCHEMA_VERSIONS

    result = runner.invoke(app, ["contract", "schema-check", str(example_project)])
    assert result.exit_code == 0, result.stdout
    assert contract.project.schema_version in result.stdout
    assert "bump_path" in result.stdout


@pytest.mark.longevity
def test_schema_bump_path_documented_and_future_minor_refused_until_listed(
    example_project: Path, tmp_path: Path, repository_root: Path
) -> None:
    """A future minor (e.g. 0.3.0) is refused until listed in SUPPORTED_SCHEMA_VERSIONS.

    Documented bump steps (``docs/18_CONTRACT_MIGRATION.md``):
    1. Export schemas via ``scripts/export_schemas.py``.
    2. Add the new version to ``SCHEMA_VERSION`` / ``SUPPORTED_SCHEMA_VERSIONS``.
    3. Migrate example contracts; re-run ``lpe contract schema-check``.
    """
    migration_doc = repository_root / "docs" / "18_CONTRACT_MIGRATION.md"
    assert migration_doc.is_file()
    doc_text = migration_doc.read_text(encoding="utf-8")
    assert "SUPPORTED_SCHEMA_VERSIONS" in doc_text
    assert "schema-check" in doc_text

    future = "0.3.0"
    assert future not in SUPPORTED_SCHEMA_VERSIONS

    dest = tmp_path / "future-contract-project"
    shutil.copytree(example_project, dest)
    contract_dir = dest / ".lean-project-contract"
    for name in (
        "project.yaml",
        "terminology.yaml",
        "obligations.yaml",
        "policies.yaml",
        "review.yaml",
    ):
        path = contract_dir / name
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        raw["schema_version"] = future
        path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported schema_version"):
        check_contract_schema_versions(dest)

    result = runner.invoke(app, ["contract", "schema-check", str(dest)])
    assert result.exit_code == 1
    combined = result.stdout + (result.stderr or "")
    assert future in combined
    assert "unsupported schema_version" in combined.lower()
    assert "SUPPORTED_SCHEMA_VERSIONS" in combined or "bump path" in combined.lower()
    assert "18_CONTRACT_MIGRATION" in combined or BUMP_PATH_HINT in combined
