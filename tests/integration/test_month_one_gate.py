"""Month-one gate CLI smoke (P0) — does not imply production / §21 clearance."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from lpe.cli import app

runner = CliRunner()


def test_month_one_gate_passes_on_clean_repo(repository_root: Path) -> None:
    """Scaffold gate must exit 0 on this repository; not production clearance."""
    result = runner.invoke(app, ["gate", "month-one", "--repo", str(repository_root)])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    combined = (result.stdout or "") + (result.stderr or "")
    assert "does NOT mean production-ready" in combined or "not production" in combined.lower()
    assert "pilot authorization" in combined.lower() or "production" in combined.lower()


def test_doctor_exits_zero() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "lpe_version" in result.stdout
