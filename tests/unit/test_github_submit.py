"""GitHub Check payload → gh api adapter (dry-run default; mocked POST)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.github.check import packet_to_github_check, render_check_payload
from lpe.github.submit import (
    GitHubSubmitError,
    build_check_run_api_argv,
    parse_owner_repo,
    plan_check_run_submit,
    submit_check_run,
)
from lpe.models import (
    CandidateDescriptor,
    EvidenceDimension,
    EvidenceFinding,
    EvidencePacket,
    FindingStatus,
    GeneratorProvenance,
    Provenance,
    Recommendation,
    RiskClass,
    Severity,
)

runner = CliRunner()


def _packet(*, head: str | None = "a" * 40) -> EvidencePacket:
    now = datetime.now(timezone.utc)
    finding = EvidenceFinding(
        finding_id="f1",
        check_id="contract.valid",
        check_version="0.1.0",
        dimension=EvidenceDimension.REPOSITORY,
        status=FindingStatus.PASS,
        severity=Severity.INFO,
        summary="ok",
        provenance=Provenance(
            tool="t",
            tool_version="0",
            input_hash="x",
            started_at=now,
            finished_at=now,
            elapsed_ms=0,
        ),
    )
    return EvidencePacket(
        packet_id="packet_gh_submit",
        run_id="run_gh_submit",
        project_id="example-category-project",
        contract_hash="0" * 64,
        candidate=CandidateDescriptor(
            candidate_id="candidate-gh",
            project_id="example-category-project",
            obligation_ids=["O-01"],
            base_commit="b" * 40,
            head_commit=head,
            patch_text="+--\n",
            claimed_intent="x",
            changed_paths=[],
            changed_declarations=[],
            generator=GeneratorProvenance(generator_type="human", name="test"),
        ),
        risk_class=RiskClass.R0,
        findings=[finding],
        hard_gate_passed=True,
        recommendation=Recommendation.ESCALATE,
        recommendation_reasons=["test"],
    )


def test_build_argv_shape() -> None:
    argv = build_check_run_api_argv(owner="acme", repo="widgets")
    assert argv == [
        "gh",
        "api",
        "repos/acme/widgets/check-runs",
        "--method",
        "POST",
        "--input",
        "-",
    ]


def test_parse_owner_repo() -> None:
    assert parse_owner_repo("acme/widgets") == ("acme", "widgets")
    with pytest.raises(GitHubSubmitError):
        parse_owner_repo("not-a-slug")
    with pytest.raises(GitHubSubmitError):
        parse_owner_repo("acme/widgets/extra")


def test_plan_dry_run_default() -> None:
    payload = render_check_payload(packet_to_github_check(_packet()))
    plan = plan_check_run_submit(payload, owner="acme", repo="widgets")
    assert plan.dry_run is True
    assert plan.endpoint == "repos/acme/widgets/check-runs"
    assert plan.payload["head_sha"] == "a" * 40
    assert plan.payload["conclusion"] == "failure"


def test_refuse_mock_or_missing_sha() -> None:
    payload = render_check_payload(
        packet_to_github_check(_packet(head=None))
    )
    # unavailable-sha is labeled but still not a real commit — allow plan for
    # dry-run inspection; POST path also needs a non-mock value. Explicit mock:
    payload["head_sha"] = "mock-sha"
    with pytest.raises(GitHubSubmitError, match="mock"):
        plan_check_run_submit(payload, owner="acme", repo="widgets")


def test_submit_dry_run_does_not_invoke_runner() -> None:
    payload = render_check_payload(packet_to_github_check(_packet()))
    mock_run = MagicMock()
    result = submit_check_run(
        payload, owner="acme", repo="widgets", post=False, runner=mock_run
    )
    assert result.posted is False
    assert result.plan.dry_run is True
    mock_run.assert_not_called()


def test_submit_post_uses_gh_api_stdin() -> None:
    payload = render_check_payload(packet_to_github_check(_packet()))
    mock_run = MagicMock(
        return_value=CompletedProcess(
            args=[], returncode=0, stdout='{"id": 1}', stderr=""
        )
    )
    result = submit_check_run(
        payload, owner="acme", repo="widgets", post=True, runner=mock_run
    )
    assert result.posted is True
    assert result.exit_code == 0
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0][0:3] == ["gh", "api", "repos/acme/widgets/check-runs"]
    body = json.loads(kwargs["input"])
    assert body["head_sha"] == "a" * 40
    assert body["name"] == "lean-project-evidence"


def test_submit_post_failure_raises() -> None:
    payload = render_check_payload(packet_to_github_check(_packet()))
    mock_run = MagicMock(
        return_value=CompletedProcess(
            args=[], returncode=1, stdout="", stderr="HTTP 403"
        )
    )
    with pytest.raises(GitHubSubmitError, match="403"):
        submit_check_run(
            payload, owner="acme", repo="widgets", post=True, runner=mock_run
        )


def test_cli_submit_check_dry_run(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(_packet().model_dump_json(indent=2), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "github",
            "submit-check",
            str(packet_path),
            "--repo",
            "acme/widgets",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert data["posted"] is False
    assert data["payload"]["head_sha"] == "a" * 40
    assert "gh" in data["argv"]
