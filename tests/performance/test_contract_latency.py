"""Contract load + validate wall time (§17: < 1 s hard / 2 s soft)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.contract.loader import load_contract
from tests.performance.budgets import assert_within_soft_budget
from tests.performance.metrics import record, timed

runner = CliRunner()


@pytest.mark.performance
def test_contract_load_and_validate_within_budget(example_project: Path) -> None:
    # Warm filesystem once; measure steady-state load+hash.
    load_contract(example_project)

    with timed() as elapsed:
        contract = load_contract(example_project)
        assert contract.contract_hash
    load_s = elapsed[0]
    record("contract_load_s", load_s, unit="s", notes="load_contract steady-state")
    assert_within_soft_budget("contract_validate_s", load_s)

    with timed() as elapsed:
        result = runner.invoke(app, ["contract", "validate", str(example_project)])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    cli_s = elapsed[0]
    record(
        "contract_validate_cli_s",
        cli_s,
        unit="s",
        notes="lpe contract validate CLI wall",
    )
    assert_within_soft_budget("contract_validate_s", cli_s)
