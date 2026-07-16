"""GitHub Check live POST — env-gated E2E (default skipped in CI).

Requires:
  LPE_GH_CHECK_E2E=1
  LPE_GH_CHECK_REPO=owner/repo  (throwaway)
  LPE_GH_CHECK_SHA=real-commit-sha
  Authenticated ``gh`` on PATH

Operator runbook: docs/github_check_e2e.md
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

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


def _env_enabled() -> bool:
    return os.environ.get("LPE_GH_CHECK_E2E", "").strip() in {"1", "true", "yes"}


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
    if not head_sha or head_sha == "mock-sha":
        pytest.skip("LPE_GH_CHECK_SHA must be a real commit SHA (not mock-sha)")

    owner, name = parse_owner_repo(repo)
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
    packet = EvidencePacket(
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
    check = packet_to_github_check(packet)
    payload = render_check_payload(check)
    payload["head_sha"] = head_sha
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
