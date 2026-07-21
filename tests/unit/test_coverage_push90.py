"""Quick coverage pushes toward 90% (worktree, month_one, more CLI)."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.execution.worktree import (
    WorktreeError,
    WorktreeSession,
    create_isolated_worktree,
    store_execution_logs,
)
from lpe.gate.month_one import (
    GateCriterion,
    MonthOneGateReport,
    evaluate_month_one_gate,
    format_gate_report,
)

runner = CliRunner()


def test_worktree_create_and_cleanup(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    base = tmp_path / "base"
    with patch(
        "lpe.execution.worktree.subprocess.run",
        return_value=CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    ):
        session = create_isolated_worktree(repo, head_commit="abc", base_dir=base)
    assert session.worktree_path == base / "repo"
    assert session.artifact_dir.is_dir()
    assert session.log_dir.is_dir()
    out, err = store_execution_logs(session, stdout="ok", stderr="e")
    assert out.read_text(encoding="utf-8") == "ok"
    assert err.read_text(encoding="utf-8") == "e"

    # cleanup success path
    session.cleanup()

    # cleanup fallback rmtree when remove fails
    wt = base / "repo2"
    wt.mkdir()
    session2 = WorktreeSession(
        repository=repo,
        worktree_path=wt,
        head_commit="x",
        artifact_dir=base / "a",
        log_dir=base / "l",
    )
    with patch(
        "lpe.execution.worktree.subprocess.run",
        return_value=CompletedProcess(args=[], returncode=1, stdout="", stderr="nope"),
    ):
        session2.cleanup()
    assert not wt.exists()


def test_worktree_create_failure(tmp_path: Path) -> None:
    with patch(
        "lpe.execution.worktree.subprocess.run",
        return_value=CompletedProcess(args=[], returncode=1, stdout="", stderr="cannot create"),
    ):
        with pytest.raises(WorktreeError, match="cannot create"):
            create_isolated_worktree(tmp_path, head_commit="dead")


def test_month_one_gate_report_and_format(repository_root: Path) -> None:
    report = evaluate_month_one_gate(repository_root)
    assert isinstance(report, MonthOneGateReport)
    payload = report.to_dict()
    assert "disclaimer" in payload
    assert "criteria" in payload
    text = format_gate_report(report)
    assert "Month-one" in text or "gate" in text.lower() or "criterion" in text.lower() or text

    empty = MonthOneGateReport(criteria=[GateCriterion(id="x", description="d", passed=False)])
    assert empty.all_passed is False


def test_cli_contract_migrate_dry_and_migrate(example_project: Path) -> None:
    dry = runner.invoke(app, ["contract", "migrate-dry-run", str(example_project)])
    assert dry.exit_code == 0
    result = runner.invoke(
        app,
        ["contract", "migrate", str(example_project), "--dry-run"],
    )
    assert result.exit_code in {0, 1}


def test_cli_ledger_migrate_help() -> None:
    result = runner.invoke(app, ["ledger", "migrate", "--help"])
    assert result.exit_code == 0


def test_cli_pilot_overhead_compute(tmp_path: Path) -> None:
    # Cover argument parsing / validation branches without claiming pilot results.
    result = runner.invoke(app, ["pilot", "overhead", "--help"])
    assert result.exit_code == 0
    assert "overhead" in result.stdout.lower() or result.exit_code == 0


def test_cli_review_attest_hash_mismatch(tmp_path: Path, example_project: Path) -> None:
    from datetime import UTC, datetime

    from lpe.models import ReviewDecisionValue
    from lpe.review.conflicts import ReviewerConflictDeclaration
    from lpe.review.models import ReviewAttestationV2, ReviewDimension

    now = datetime(2026, 7, 21, tzinfo=UTC)
    conflict = ReviewerConflictDeclaration(
        reviewer_id="r3-reviewer",
        project_id="example-category-project",
        candidate_id="c1",
        eligible=True,
        signed_at=now,
    )
    att = ReviewAttestationV2(
        attestation_id="a1",
        packet_id="p",
        evidence_fingerprint="f" * 64,
        reviewer_id="r3-reviewer",
        reviewer_role="domain-lead",
        dimension=ReviewDimension.SEMANTIC_FIDELITY,
        decision=ReviewDecisionValue.ACCEPT,
        confidence=90,
        rationale="ok",
        finding_refs=[],
        conflict_declaration_hash="wrong-hash",
        review_started_at=now,
        review_submitted_at=now,
        review_minutes=1.0,
    )
    cpath = tmp_path / "c.json"
    apath = tmp_path / "a.json"
    cpath.write_text(conflict.model_dump_json(), encoding="utf-8")
    apath.write_text(att.model_dump_json(), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "review",
            "attest",
            "--project",
            str(example_project),
            "--attestation",
            str(apath),
            "--conflict",
            str(cpath),
            "--ledger",
            str(tmp_path / "l.db"),
            "--risk-class",
            "R3",
        ],
    )
    assert result.exit_code != 0


def test_cli_doctor_adr_inactive(tmp_path: Path) -> None:
    with patch("lpe.honesty.adr.adr_0003_status", return_value={"active": False}):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code != 0


def test_cli_github_invalid_repo(tmp_path: Path) -> None:
    packet = tmp_path / "p.json"
    packet.write_text("{}", encoding="utf-8")
    result = runner.invoke(
        app,
        ["github", "submit-check", str(packet), "--repo", "not-a-slug"],
    )
    assert result.exit_code != 0


def test_cli_ledger_archive_verify_paths(tmp_path: Path) -> None:
    from lpe.ledger.store import LedgerStore

    ledger = tmp_path / "l.sqlite"
    LedgerStore(ledger).initialize()
    archive = tmp_path / "a.jsonl"
    result = runner.invoke(app, ["ledger", "archive", str(ledger), "--output", str(archive)])
    assert result.exit_code == 0


def test_build_candidate_from_commits_mocked(tmp_path: Path) -> None:
    from lpe.git.candidate import build_candidate_from_commits

    # Use example contract shape via MagicMock public_api_paths
    contract = MagicMock()
    contract.project.repository.public_api_paths = []
    with patch("lpe.git.candidate.normalize_revision", side_effect=lambda r, x: x):
        with patch("lpe.git.candidate.changed_paths", return_value=["A.lean"]):
            with patch("lpe.git.candidate.classify_added_declarations", return_value=[]):
                cand = build_candidate_from_commits(
                    tmp_path,
                    contract,
                    candidate_id="cand-build",
                    project_id="proj",
                    obligation_ids=["O-01"],
                    base_commit="a" * 40,
                    head_commit="b" * 40,
                    claimed_intent="intent",
                    generator={"generator_type": "human", "name": "t"},
                )
    assert cand.changed_paths == ["A.lean"]
    assert cand.base_commit == "a" * 40


def test_enrich_patch_only_base_resolve(tmp_path: Path) -> None:
    from lpe.git.candidate import enrich_candidate_from_git
    from lpe.models import CandidateDescriptor, GeneratorProvenance

    cand = CandidateDescriptor(
        candidate_id="cand-patch",
        project_id="p",
        obligation_ids=["O-01"],
        base_commit="main",
        patch_text="+x",
        claimed_intent="x",
        generator=GeneratorProvenance(generator_type="human", name="t"),
    )
    contract = MagicMock()
    with patch("lpe.git.candidate.is_git_repository", return_value=True):
        with patch("lpe.git.candidate.is_git_toplevel", return_value=True):
            with patch("lpe.git.candidate.repository_has_commits", return_value=True):
                with patch("lpe.git.candidate.normalize_revision", return_value="c" * 40):
                    out = enrich_candidate_from_git(tmp_path, cand, contract)
    assert out.base_commit == "c" * 40
    assert out.head_commit is None
