"""GitHub Check live POST — env-gated E2E (default skipped in CI).

Requires:
  LPE_GH_CHECK_E2E=1
  LPE_GH_CHECK_REPO=owner/repo  (throwaway)
  LPE_GH_CHECK_SHA=real-commit-sha
  Authenticated ``gh`` on PATH

Operator runbook: docs/github_check_e2e.md

Non-network coverage for ``--post`` lives in
``tests/unit/test_github_submit.py`` (mocked ``subprocess.run``).
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from lpe.cli import app
from lpe.github.check import packet_to_github_check, render_check_payload
from lpe.github.submit import parse_owner_repo, submit_check_run
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

_cli = CliRunner()


def _env_enabled() -> bool:
    return os.environ.get("LPE_GH_CHECK_E2E", "").strip() in {"1", "true", "yes"}


def _minimal_packet(*, head_sha: str) -> EvidencePacket:
    now = datetime.now(timezone.utc)
    finding = EvidenceFinding(
        finding_id="finding-gh-e2e",
        check_id="docs.presence",
        check_version="0.1.0",
        dimension=EvidenceDimension.KERNEL,
        status=FindingStatus.PASS,
        severity=Severity.INFO,
        summary="E2E placeholder finding",
        provenance=Provenance(
            tool="lean-project-evidence",
            tool_version="0.1.0",
            input_hash="0" * 64,
            started_at=now,
            finished_at=now,
            elapsed_ms=0,
        ),
    )
    return EvidencePacket(
        packet_id="pkt-gh-e2e",
        run_id="run-gh-e2e",
        project_id="example-category-project",
        contract_hash="0" * 64,
        candidate=CandidateDescriptor(
            candidate_id="cand-gh-e2e",
            project_id="example-category-project",
            obligation_ids=["O-01"],
            base_commit="b" * 40,
            head_commit=head_sha,
            patch_text="# e2e\n",
            claimed_intent="github check e2e",
            changed_paths=["README.md"],
            changed_declarations=[],
            generator=GeneratorProvenance(
                generator_type="test", name="gh-e2e", version="0"
            ),
        ),
        risk_class=RiskClass.R0,
        findings=[finding],
        hard_gate_passed=True,
        recommendation=Recommendation.ESCALATE,
        recommendation_reasons=["e2e"],
    )


def test_cli_post_success_mocked_subprocess(tmp_path: Path) -> None:
    """Integration-style CLI --post path with mocked gh (no network/secrets)."""
    head_sha = "c" * 40
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(
        _minimal_packet(head_sha=head_sha).model_dump_json(indent=2),
        encoding="utf-8",
    )
    mock_completed = CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"id": 42, "name": "lean-project-evidence"}',
        stderr="",
    )
    with patch("lpe.github.submit.subprocess.run", return_value=mock_completed) as mock_run:
        with patch("lpe.github.submit.shutil.which", return_value="/usr/bin/gh"):
            result = _cli.invoke(
                app,
                [
                    "github",
                    "submit-check",
                    str(packet_path),
                    "--repo",
                    "acme/sandbox",
                    "--post",
                ],
            )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    data = json.loads(result.stdout)
    assert data["posted"] is True
    assert data["payload"]["conclusion"] == "failure"
    assert data["payload"]["head_sha"] == head_sha
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0][:3] == [
        "gh",
        "api",
        "repos/acme/sandbox/check-runs",
    ]


@pytest.mark.skipif(
    not _env_enabled(),
    reason="Set LPE_GH_CHECK_E2E=1 and LPE_GH_CHECK_REPO for live Check POST",
)
def test_github_check_live_post_env_gated(tmp_path: Path) -> None:
    if shutil.which("gh") is None:
        pytest.skip("gh CLI not on PATH")
    repo = os.environ.get("LPE_GH_CHECK_REPO", "").strip()
    if not repo or "/" not in repo:
        pytest.skip("LPE_GH_CHECK_REPO=owner/repo required")
    head_sha = os.environ.get("LPE_GH_CHECK_SHA", "").strip()
    if not head_sha or head_sha in {"mock-sha", "unavailable-sha"}:
        pytest.skip("LPE_GH_CHECK_SHA must be a real commit SHA (not sentinel)")

    owner, name = parse_owner_repo(repo)
    packet = _minimal_packet(head_sha=head_sha)
    check = packet_to_github_check(packet)
    payload = render_check_payload(check)
    payload["head_sha"] = head_sha
    assert payload["conclusion"] == "failure"  # ESCALATE fail-closed
    result = submit_check_run(
        owner=owner,
        repo=name,
        payload=payload,
        post=True,
    )
    assert result.posted is True
    assert result.exit_code == 0
    receipt = tmp_path / "gh-check-e2e-receipt.json"
    receipt.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
