"""CLI smoke for repair lineage / adjudication helpers (CLOSURE-024)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from lpe.cli import app

_cli = CliRunner()


def test_review_repair_lineage_cli(tmp_path: Path) -> None:
    change = tmp_path / "fix.patch"
    change.write_text("diff --git a/x b/x\n+ok\n", encoding="utf-8")
    result = _cli.invoke(
        app,
        [
            "review",
            "repair-lineage",
            "--prior-candidate-id",
            "cand-root",
            "--repair-request-ids",
            "rep-1",
            "--applied-change",
            str(change),
            "--new-evidence-fingerprint",
            "a" * 64,
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    data = json.loads(result.stdout)
    assert data["new_candidate_id"] == "cand-root.r1"
    assert data["repair_sequence"] == 1
    assert data["note"].startswith("Prior attestations")
    assert len(data["applied_change_hash"]) == 64
