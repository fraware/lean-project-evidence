"""P0 contract CLI smoke — no Lean Docker required."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from lpe.cli import app

runner = CliRunner()


def test_contract_validate_example_project_exits_zero(example_project: Path) -> None:
    result = runner.invoke(app, ["contract", "validate", str(example_project)])
    assert result.exit_code == 0
    assert '"valid": true' in result.stdout.lower()


def test_contract_schema_check_example_project(example_project: Path) -> None:
    result = runner.invoke(app, ["contract", "schema-check", str(example_project)])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_contract_schema_check_rejects_unsupported(repository_root: Path) -> None:
    fixture = repository_root / "tests" / "fixtures" / "contracts" / "unsupported-schema-version"
    result = runner.invoke(app, ["contract", "schema-check", str(fixture)])
    assert result.exit_code == 1


def test_candidate_validate_r3_example(repository_root: Path, example_project: Path) -> None:
    candidate = repository_root / "examples" / "candidates" / "R3-definition-change.json"
    result = runner.invoke(
        app,
        [
            "candidate",
            "validate",
            str(candidate),
            "--project",
            str(example_project),
        ],
    )
    assert result.exit_code == 0
    assert "R3" in result.stdout or "candidate_id" in result.stdout
