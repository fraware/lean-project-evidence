from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.evidence.compiler import compile_evidence
from lpe.models import CandidateDescriptor, GeneratorProvenance
from lpe.paths import PathTraversalError, assert_safe_repo_relative
from lpe.pilot.instrumentation import PilotInstrumentation
from lpe.ledger.store import LedgerStore


runner = CliRunner()


def test_assert_safe_repo_relative_accepts_nested(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    target = assert_safe_repo_relative(tmp_path, "src/Foo.lean")
    assert target == (tmp_path / "src" / "Foo.lean").resolve()


@pytest.mark.parametrize(
    "relative",
    [
        "../etc/passwd",
        "..\\Windows\\System32",
        "/etc/passwd",
        "src/../../secret",
        "C:/Windows/System32",
    ],
)
def test_assert_safe_repo_relative_rejects_traversal(tmp_path: Path, relative: str) -> None:
    with pytest.raises(PathTraversalError):
        assert_safe_repo_relative(tmp_path, relative)


def test_compile_evidence_rejects_path_traversal(example_project: Path) -> None:
    candidate = CandidateDescriptor(
        candidate_id="c-traversal",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        claimed_intent="probe",
        changed_paths=["../../../etc/passwd"],
        patch_text="diff --git a/x b/x\n",
        generator=GeneratorProvenance(generator_type="human", name="test", version="0"),
    )
    with pytest.raises(PathTraversalError, match="\\.\\."):
        compile_evidence(example_project, candidate, skip_build=True)


def test_ledger_append_rejects_anonymous_via_cli(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite3"
    event_path = tmp_path / "event.json"
    event_path.write_text(
        """
        {
          "schema_version": "0.1.0",
          "event_id": "evt-1",
          "event_type": "CANDIDATE_REGISTERED",
          "project_id": "example-category-project",
          "artifact_id": "art-1",
          "occurred_at": "2026-01-01T00:00:00+00:00",
          "actor_id": "anonymous",
          "payload": {}
        }
        """,
        encoding="utf-8",
    )
    result = runner.invoke(app, ["ledger", "append", str(ledger), str(event_path)])
    assert result.exit_code == 1
    assert "anonymous" in result.stdout.lower() or "anonymous" in (result.stderr or "").lower()


def test_ledger_append_project_id_mismatch(example_project: Path, tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.sqlite3"
    event_path = tmp_path / "event.json"
    event_path.write_text(
        """
        {
          "schema_version": "0.1.0",
          "event_id": "evt-1",
          "event_type": "CANDIDATE_REGISTERED",
          "project_id": "other-project",
          "artifact_id": "art-1",
          "occurred_at": "2026-01-01T00:00:00+00:00",
          "actor_id": "reviewer-1",
          "payload": {}
        }
        """,
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "ledger",
            "append",
            str(ledger),
            str(event_path),
            "--project",
            str(example_project),
        ],
    )
    assert result.exit_code == 1
    assert "does not match" in (result.stdout + result.stderr)


def test_contract_schema_check_ok(example_project: Path) -> None:
    result = runner.invoke(app, ["contract", "schema-check", str(example_project)])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout
    assert "bump_path" in result.stdout


def test_contract_schema_check_refuses_unknown(tmp_path: Path) -> None:
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "contracts"
        / "unsupported-schema-version"
    )
    result = runner.invoke(app, ["contract", "schema-check", str(fixture)])
    assert result.exit_code == 1
    assert "unsupported schema_version" in (result.stdout + result.stderr).lower()


def test_pilot_optional_ledger_snapshot(tmp_path: Path) -> None:
    pilot = PilotInstrumentation()
    pilot.register_candidate(
        candidate_id="c1",
        project_id="project",
        obligation_ids=["O-01"],
        condition_tag="control",
    )
    pilot.record_expert_time(
        candidate_id="c1",
        category="review",
        minutes=12.0,
        condition_tag="control",
    )
    store = LedgerStore(tmp_path / "ledger.sqlite3")
    digests = pilot.append_snapshot_to_ledger(
        store, actor_id="pilot-operator", project_id="project"
    )
    assert len(digests) == 1
    store.verify()
    events = store.events()
    assert events[0].payload["source"] == "pilot_instrumentation_snapshot"
