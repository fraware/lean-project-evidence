from __future__ import annotations

from typer.testing import CliRunner

from lpe.cli import app


runner = CliRunner()


def test_doctor() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "lpe_version" in result.stdout


def test_contract_validate(example_project) -> None:
    result = runner.invoke(app, ["contract", "validate", str(example_project)])
    assert result.exit_code == 0
    assert '"valid": true' in result.stdout.lower()
