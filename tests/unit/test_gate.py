from __future__ import annotations

from pathlib import Path

from lpe.gate.month_one import evaluate_month_one_gate


def test_month_one_gate_evaluates(repository_root: Path) -> None:
    report = evaluate_month_one_gate(repository_root)
    assert len(report.criteria) >= 5
    ids = {c.id for c in report.criteria}
    assert "tests_pass" in ids
    assert "schema_stable" in ids
    assert "sandbox_design" in ids
    assert "example_contract" in ids
    by_id = {c.id: c for c in report.criteria}
    # AUDIT-013: real contract validate, not path existence only.
    assert by_id["example_contract"].passed is True
    assert "validated" in by_id["example_contract"].details.lower()
    # AUDIT-013: sandbox requires import + allowlist, not file existence alone.
    assert by_id["sandbox_design"].passed is True
    assert "allowlist" in by_id["sandbox_design"].details.lower()
    # Gate clearance is not production readiness.
    assert "production" in report.disclaimer.lower()
    assert report.to_dict()["disclaimer"]
