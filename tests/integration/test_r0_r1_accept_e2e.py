"""R0/R1 ACCEPT E2E: sandboxed Lean build → review ACCEPT → ledger → TPPR.

When ``lpe-lean:4.14`` is present:
  sandboxed build+extract → toolchain-complete where applicable →
  low-risk ACCEPT (R0) or honest ESCALATE for policy/unresolved dims (R1) →
  authorized ``lpe review record`` ACCEPT → ledger + TPPR path.

Never auto-accepts or records ACCEPT for R3/R4 (ADR 0003).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from lpe.cli import app
from lpe.evidence.compiler import compile_evidence
from lpe.execution.sandbox import (
    DEFAULT_LEAN_DOCKER_IMAGE,
    docker_image_present,
)
from lpe.lean.extractor import TOOLCHAIN_EXTRACTOR
from lpe.ledger.store import LedgerStore
from lpe.models import (
    CandidateDescriptor,
    ChangedDeclaration,
    EventType,
    FindingStatus,
    GeneratorProvenance,
    Recommendation,
    RiskClass,
    UtilityEvent,
)
from lpe.review.authority import can_record_acceptance

LEAN_PROJECT = Path(__file__).resolve().parents[1] / "fixtures" / "lean_project"
EXAMPLE_CONTRACT = (
    Path(__file__).resolve().parents[2] / "examples" / "minimal-project" / ".lean-project-contract"
)
LEAN_DOCKER_IMAGE = os.environ.get("LPE_LEAN_DOCKER_IMAGE", DEFAULT_LEAN_DOCKER_IMAGE)

runner = CliRunner()


def _generator() -> GeneratorProvenance:
    return GeneratorProvenance(generator_type="test", name="r0-r1-accept-e2e", version="0")


def _init_git(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "accept-e2e@example.org"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "AcceptE2E"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _commit_all(repo: Path, message: str) -> str:
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _seed_lean_project(dest: Path) -> Path:
    shutil.copytree(
        LEAN_PROJECT,
        dest,
        ignore=shutil.ignore_patterns(
            ".lake", "lake-manifest.json", ".lpe", ".lean-project-contract"
        ),
    )
    shutil.copytree(EXAMPLE_CONTRACT, dest / ".lean-project-contract")
    project_yaml = dest / ".lean-project-contract" / "project.yaml"
    data = yaml.safe_load(project_yaml.read_text(encoding="utf-8"))
    data["project_id"] = "lpe-fixture-project"
    data["repository"]["public_api_paths"] = ["LpeFixture"]
    data["execution"]["build_command"] = ["lake", "build"]
    data["execution"]["network_policy"] = "deny"
    data["execution"]["timeout_seconds"] = 600
    project_yaml.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return dest


def _require_lean_docker_image() -> None:
    if not docker_image_present(LEAN_DOCKER_IMAGE):
        pytest.skip(
            f"Lean Docker image {LEAN_DOCKER_IMAGE!r} not present "
            "(build with scripts/build_lean_docker_image.ps1 or .sh)"
        )


@pytest.mark.docker
def test_r0_sandbox_accept_review_ledger_tppr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Docs-only R0: sandbox toolchain → ACCEPT → authorized review → TPPR."""
    _require_lean_docker_image()
    project = _seed_lean_project(tmp_path / "r0_accept")
    _init_git(project)
    base = _commit_all(project, "seed")

    docs = project / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "notes.md").write_text("# notes\nfixture docs only\n", encoding="utf-8")
    _commit_all(project, "docs notes")

    monkeypatch.setenv("LPE_DOCKER_IMAGE", LEAN_DOCKER_IMAGE)
    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: None)

    candidate = CandidateDescriptor(
        candidate_id="cand-r0-accept-e2e",
        project_id="lpe-fixture-project",
        obligation_ids=["O-01"],
        base_commit=base,
        head_commit=None,
        patch_text="+<!-- documentation only -->\n",
        claimed_intent="Documentation-only R0 accept path",
        changed_paths=["docs/notes.md"],
        changed_declarations=[],
        generator=_generator(),
    )
    packet = compile_evidence(
        project,
        candidate,
        skip_build=False,
        insecure_host_exec=False,
        use_sandbox=True,
        use_worktree=False,
    )

    assert packet.risk_class is RiskClass.R0
    assert can_record_acceptance(packet.risk_class) is True

    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    assert isolation.status is FindingStatus.PASS
    assert isolation.details.get("sandbox_invocations") == 1

    build = next(f for f in packet.findings if f.check_id == "lean.build")
    assert build.status is FindingStatus.PASS, (build.details.get("stderr") or "")[:1200]

    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is FindingStatus.PASS
    assert axiom.details.get("extractor") == TOOLCHAIN_EXTRACTOR

    api_fit = next(f for f in packet.findings if f.check_id == "repository.api_fit")
    assert api_fit.status is FindingStatus.NOT_APPLICABLE
    declared = next(f for f in packet.findings if f.check_id == "downstream.declared_use")
    assert declared.status is FindingStatus.NOT_APPLICABLE

    assert packet.hard_gate_passed is True
    # R0 + auto_accept + no UNKNOWN → ACCEPT (not soft-theater ESCALATE).
    assert packet.recommendation is Recommendation.ACCEPT
    unknowns = [f.check_id for f in packet.findings if f.status is FindingStatus.UNKNOWN]
    assert unknowns == [], f"unexpected UNKNOWN findings: {unknowns}"

    packet_path = tmp_path / "packet-r0.json"
    packet_path.write_text(packet.model_dump_json(indent=2), encoding="utf-8")
    ledger = tmp_path / "ledger-r0.sqlite3"
    decision_path = tmp_path / "decision-r0.json"
    decision_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "review-r0-accept-e2e",
                "packet_id": packet.packet_id,
                "reviewer_id": "lean-engineer",
                "reviewer_roles": [],
                "decision": "ACCEPT",
                "confidence": 90,
                "rationale": "R0 docs-only ACCEPT e2e; authorized lean-engineer",
                "review_minutes": 5.0,
            }
        ),
        encoding="utf-8",
    )
    review = runner.invoke(
        app,
        [
            "review",
            "record",
            "--project",
            str(project),
            "--decision",
            str(decision_path),
            "--ledger",
            str(ledger),
            "--risk-class",
            "R0",
            "--obligation-ids",
            "O-01",
        ],
    )
    assert review.exit_code == 0, review.stdout + (review.stderr or "")

    store = LedgerStore(ledger)
    store.append(
        UtilityEvent(
            event_id="evt_obl_r0_accept",
            event_type=EventType.OBLIGATION_REGISTERED,
            project_id=packet.project_id,
            artifact_id=packet.packet_id,
            obligation_id="O-01",
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            actor_id="accept-e2e",
            payload={"weight": 2},
        )
    )
    store.append(
        UtilityEvent(
            event_id="evt_persist_r0_accept",
            event_type=EventType.PERSISTENCE_CONFIRMED,
            project_id=packet.project_id,
            artifact_id=packet.packet_id,
            obligation_id="O-01",
            occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            actor_id="accept-e2e",
            payload={"downstream_enabled": True, "remained_integrated": True},
        )
    )

    events = store.events(packet.project_id)
    assert any(e.event_type is EventType.ARTIFACT_ACCEPTED for e in events)
    accepted = next(e for e in events if e.event_type is EventType.ARTIFACT_ACCEPTED)
    assert accepted.obligation_id == "O-01"
    assert accepted.payload.get("semantic_fidelity") is True
    assert accepted.payload.get("repository_accepted") is True

    tppr = runner.invoke(
        app,
        ["tppr", "compute", str(ledger), "--project-id", packet.project_id],
    )
    assert tppr.exit_code == 0, tppr.stdout + (tppr.stderr or "")
    report = json.loads(tppr.stdout)
    assert report["expert_hours_total"] > 0
    assert report["weighted_accepted_sustained_obligations"] == 2.0
    assert "O-01" in report["credited_obligations"]


@pytest.mark.docker
def test_r1_sandbox_escalate_then_accept_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Private body-only R1: toolchain-complete → policy ESCALATE → human ACCEPT."""
    _require_lean_docker_image()
    project = _seed_lean_project(tmp_path / "r1_accept")
    _init_git(project)
    base = _commit_all(project, "seed")

    core = project / "LpeFixture" / "Core.lean"
    core.write_text(
        core.read_text(encoding="utf-8").replace(
            "def helper : Nat := coreVal + 1",
            "def helper : Nat := coreVal + 2",
        ),
        encoding="utf-8",
    )
    _commit_all(project, "private helper body bump")

    monkeypatch.setenv("LPE_DOCKER_IMAGE", LEAN_DOCKER_IMAGE)
    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: None)

    candidate = CandidateDescriptor(
        candidate_id="cand-r1-accept-e2e",
        project_id="lpe-fixture-project",
        obligation_ids=["O-01"],
        base_commit=base,
        head_commit=None,
        patch_text="+def helper : Nat := coreVal + 2\n",
        claimed_intent="Private helper body-only R1 accept path",
        changed_paths=["LpeFixture/Core.lean"],
        changed_declarations=[
            ChangedDeclaration(
                name="LpeFixture.Core.helper",
                kind="definition",
                path="LpeFixture/Core.lean",
                signature_changed=False,
                public=False,
                foundational=False,
            )
        ],
        generator=_generator(),
    )
    packet = compile_evidence(
        project,
        candidate,
        skip_build=False,
        insecure_host_exec=False,
        use_sandbox=True,
        use_worktree=False,
    )

    assert packet.risk_class is RiskClass.R1
    assert can_record_acceptance(packet.risk_class) is True
    assert packet.hard_gate_passed is True

    build = next(f for f in packet.findings if f.check_id == "lean.build")
    assert build.status is FindingStatus.PASS, (build.details.get("stderr") or "")[:1200]
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is FindingStatus.PASS
    assert axiom.details.get("extractor") == TOOLCHAIN_EXTRACTOR
    impact = next(f for f in packet.findings if f.check_id == "lean.impact_cone")
    assert impact.status is FindingStatus.PASS
    assert impact.details.get("complete") is True

    # R1 is never auto-accept eligible — ESCALATE for human review (or soft UNKNOWN).
    assert packet.recommendation is Recommendation.ESCALATE
    assert packet.recommendation is not Recommendation.ACCEPT
    reasons = " ".join(packet.recommendation_reasons).lower()
    assert "human" in reasons or "unresolved" in reasons or "policy" in reasons

    unknowns = [f for f in packet.findings if f.status is FindingStatus.UNKNOWN]
    hard_unknown = [
        f.check_id
        for f in unknowns
        if f.check_id
        in {
            "contract.valid",
            "candidate.obligations",
            "lean.build",
            "lean.placeholders",
            "lean.prohibited_axioms",
            "repository.changed_paths",
        }
    ]
    assert hard_unknown == [], f"hard-relevant UNKNOWN blocks honesty: {hard_unknown}"

    ledger = tmp_path / "ledger-r1.sqlite3"
    decision_path = tmp_path / "decision-r1.json"
    decision_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "review-r1-accept-e2e",
                "packet_id": packet.packet_id,
                "reviewer_id": "lean-engineer",
                "reviewer_roles": [],
                "decision": "ACCEPT",
                "confidence": 85,
                "rationale": "R1 private body ACCEPT after toolchain-complete gates",
                "review_minutes": 10.0,
            }
        ),
        encoding="utf-8",
    )
    review = runner.invoke(
        app,
        [
            "review",
            "record",
            "--project",
            str(project),
            "--decision",
            str(decision_path),
            "--ledger",
            str(ledger),
            "--risk-class",
            "R1",
            "--obligation-ids",
            "O-01",
        ],
    )
    assert review.exit_code == 0, review.stdout + (review.stderr or "")

    store = LedgerStore(ledger)
    events = store.events(packet.project_id)
    assert any(e.event_type is EventType.ARTIFACT_ACCEPTED for e in events)
    assert any(e.event_type is EventType.EXPERT_TIME_RECORDED for e in events)

    # ADR 0003: R3 ACCEPT still refused even for authorized multi-role reviewer.
    r3_decision = tmp_path / "decision-r3.json"
    r3_decision.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "review-r3-refuse",
                "packet_id": packet.packet_id,
                "reviewer_id": "r3-reviewer",
                "reviewer_roles": [],
                "decision": "ACCEPT",
                "confidence": 99,
                "rationale": "must refuse",
                "review_minutes": 1.0,
            }
        ),
        encoding="utf-8",
    )
    refused = runner.invoke(
        app,
        [
            "review",
            "record",
            "--project",
            str(project),
            "--decision",
            str(r3_decision),
            "--ledger",
            str(ledger),
            "--risk-class",
            "R3",
        ],
    )
    assert refused.exit_code == 1
    combined = (refused.stdout or "") + (refused.stderr or "")
    assert "ACCEPT" in combined or "ADR" in combined or "R3" in combined
    assert can_record_acceptance(RiskClass.R3) is False
    assert can_record_acceptance(RiskClass.R4) is False
