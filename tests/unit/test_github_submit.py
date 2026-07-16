"""GitHub Check payload → gh api adapter (dry-run default; mocked POST)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.github.check import packet_to_github_check, render_check_payload
from lpe.github.submit import (
    GitHubSubmitError,
    build_check_run_api_argv,
    classify_gh_api_failure,
    ensure_gh_on_path,
    format_gh_api_command_preview,
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
    preview = format_gh_api_command_preview(argv)
    assert preview.startswith("gh api repos/acme/widgets/check-runs")
    assert "--input -" in preview


def test_parse_owner_repo() -> None:
    assert parse_owner_repo("acme/widgets") == ("acme", "widgets")
    with pytest.raises(GitHubSubmitError):
        parse_owner_repo("not-a-slug")
    with pytest.raises(GitHubSubmitError):
        parse_owner_repo("acme/widgets/extra")


def test_plan_dry_run_default_fail_closed_escalate() -> None:
    payload = render_check_payload(packet_to_github_check(_packet()))
    plan = plan_check_run_submit(payload, owner="acme", repo="widgets")
    assert plan.dry_run is True
    assert plan.endpoint == "repos/acme/widgets/check-runs"
    assert plan.payload["head_sha"] == "a" * 40
    # Required-check fail-closed: ESCALATE → failure
    assert plan.payload["conclusion"] == "failure"
    data = plan.to_dict()
    assert data["argv"] == list(plan.argv)
    assert data["command_preview"] == format_gh_api_command_preview(plan.argv)
    assert data["stdin_json"] is True


def test_refuse_mock_or_missing_sha() -> None:
    payload = render_check_payload(
        packet_to_github_check(_packet(head=None))
    )
    payload["head_sha"] = "mock-sha"
    with pytest.raises(GitHubSubmitError, match="mock-sha"):
        plan_check_run_submit(payload, owner="acme", repo="widgets")


def test_refuse_unavailable_sha() -> None:
    payload = render_check_payload(packet_to_github_check(_packet(head=None)))
    assert payload["head_sha"] == "unavailable-sha"
    with pytest.raises(GitHubSubmitError, match="unavailable-sha"):
        plan_check_run_submit(payload, owner="acme", repo="widgets")


def test_ensure_gh_on_path_clear_error() -> None:
    with patch("lpe.github.submit.shutil.which", return_value=None):
        with pytest.raises(GitHubSubmitError, match="gh CLI not found"):
            ensure_gh_on_path()


def test_classify_auth_failure() -> None:
    msg = classify_gh_api_failure(
        returncode=1,
        stdout="",
        stderr="HTTP 401: Bad credentials",
    )
    assert "authentication" in msg.lower() or "auth" in msg.lower()
    assert "checks:write" in msg


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
    assert body["conclusion"] == "failure"


def test_submit_post_gh_missing_raises() -> None:
    payload = render_check_payload(packet_to_github_check(_packet()))
    with patch("lpe.github.submit.shutil.which", return_value=None):
        with pytest.raises(GitHubSubmitError, match="gh CLI not found"):
            submit_check_run(payload, owner="acme", repo="widgets", post=True)


def test_submit_post_auth_failure_raises_clear() -> None:
    payload = render_check_payload(packet_to_github_check(_packet()))
    mock_run = MagicMock(
        return_value=CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="gh: To get started with GitHub CLI, please run: gh auth login",
        )
    )
    with pytest.raises(GitHubSubmitError, match="auth"):
        submit_check_run(
            payload, owner="acme", repo="widgets", post=True, runner=mock_run
        )


def test_submit_post_failure_raises() -> None:
    payload = render_check_payload(packet_to_github_check(_packet()))
    mock_run = MagicMock(
        return_value=CompletedProcess(
            args=[], returncode=1, stdout="", stderr="HTTP 422 Unprocessable"
        )
    )
    with pytest.raises(GitHubSubmitError, match="422"):
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
    assert data["payload"]["conclusion"] == "failure"
    assert data["argv"] == [
        "gh",
        "api",
        "repos/acme/widgets/check-runs",
        "--method",
        "POST",
        "--input",
        "-",
    ]
    assert "command_preview" in data
    assert data["command_preview"].startswith("gh api ")


def test_cli_submit_check_refuses_mock_sha(tmp_path: Path) -> None:
    packet = _packet(head="mock-sha")
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(packet.model_dump_json(indent=2), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "github",
            "submit-check",
            str(packet_path),
            "--repo",
            "acme/widgets",
        ],
    )
    assert result.exit_code == 1
    assert "mock-sha" in (result.stderr or result.stdout)


def test_cli_submit_check_post_mocked_success(tmp_path: Path) -> None:
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(_packet().model_dump_json(indent=2), encoding="utf-8")
    mock_completed = CompletedProcess(
        args=[], returncode=0, stdout='{"id": 99, "html_url": "https://example"}', stderr=""
    )
    with patch("lpe.github.submit.subprocess.run", return_value=mock_completed) as mock_run:
        with patch("lpe.github.submit.shutil.which", return_value="/usr/bin/gh"):
            result = runner.invoke(
                app,
                [
                    "github",
                    "submit-check",
                    str(packet_path),
                    "--repo",
                    "acme/widgets",
                    "--post",
                ],
            )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    data = json.loads(result.stdout)
    assert data["posted"] is True
    assert data["exit_code"] == 0
    assert data["payload"]["conclusion"] == "failure"
    mock_run.assert_called_once()
    argv = mock_run.call_args[0][0]
    assert argv[:3] == ["gh", "api", "repos/acme/widgets/check-runs"]
