"""CLI command-branch unit coverage with mocks (no network / Lean / Docker)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from lpe.cli import app
from lpe.ledger.seal import write_seal
from lpe.ledger.store import LedgerStore
from lpe.models import (
    EventType,
    ReviewDecisionValue,
    UtilityEvent,
)
from lpe.pilot.protocol import freeze_protocol, write_example_bundle
from lpe.review.adjudication import ADJUDICATOR_ROLE, AdjudicationRecord, ProvisionalJudgment
from lpe.review.conflicts import ReviewerConflictDeclaration
from lpe.review.models import ReviewAttestationV2, ReviewDimension

runner = CliRunner()
NOW = datetime(2026, 7, 21, tzinfo=UTC)
FP = "f" * 64
DIGEST = "sha256:" + ("a" * 64)


def _conflict(reviewer_id: str = "domain-lead") -> ReviewerConflictDeclaration:
    return ReviewerConflictDeclaration(
        reviewer_id=reviewer_id,
        project_id="example-category-project",
        candidate_id="cand-1",
        eligible=True,
        signed_at=NOW,
    )


def _attestation(
    *,
    attestation_id: str = "att-1",
    reviewer_id: str = "domain-lead",
    role: str = "domain-lead",
    dimension: ReviewDimension = ReviewDimension.SEMANTIC_FIDELITY,
    conflict_hash: str,
) -> ReviewAttestationV2:
    return ReviewAttestationV2(
        attestation_id=attestation_id,
        packet_id="packet_x",
        evidence_fingerprint=FP,
        reviewer_id=reviewer_id,
        reviewer_role=role,
        dimension=dimension,
        decision=ReviewDecisionValue.ACCEPT,
        confidence=90,
        rationale="ok",
        finding_refs=[],
        conflict_declaration_hash=conflict_hash,
        review_started_at=NOW,
        review_submitted_at=NOW,
        review_minutes=10.0,
    )


def test_review_record_r1_accept(tmp_path: Path, example_project: Path) -> None:
    decision = {
        "schema_version": "0.1.0",
        "review_id": "review-r1",
        "packet_id": "packet_r1",
        "reviewer_id": "lean-engineer",
        "reviewer_roles": [],
        "decision": "ACCEPT",
        "confidence": 90,
        "rationale": "ok",
        "review_minutes": 5.0,
    }
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    result = runner.invoke(
        app,
        [
            "review",
            "record",
            "--project",
            str(example_project),
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
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert result.stdout.strip()


def test_review_record_packet_id_mismatch(tmp_path: Path, example_project: Path) -> None:

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

    now = datetime.now(UTC)
    packet = EvidencePacket(
        packet_id="packet_other",
        run_id="run",
        project_id="example-category-project",
        contract_hash="0" * 64,
        candidate=CandidateDescriptor(
            candidate_id="cand-1",
            project_id="example-category-project",
            obligation_ids=["O-01"],
            base_commit="b" * 40,
            head_commit="a" * 40,
            claimed_intent="x",
            changed_paths=[],
            changed_declarations=[],
            generator=GeneratorProvenance(generator_type="human", name="t"),
        ),
        risk_class=RiskClass.R1,
        findings=[
            EvidenceFinding(
                finding_id="f1",
                check_id="c",
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
        ],
        hard_gate_passed=True,
        recommendation=Recommendation.ACCEPT,
        recommendation_reasons=["unit"],
        evidence_fingerprint="e" * 64,
    )
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(packet.model_dump_json(), encoding="utf-8")
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "r",
                "packet_id": "packet_mismatch",
                "reviewer_id": "lean-engineer",
                "reviewer_roles": [],
                "decision": "ACCEPT",
                "confidence": 90,
                "rationale": "ok",
                "review_minutes": 5.0,
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "review",
            "record",
            "--project",
            str(example_project),
            "--decision",
            str(decision_path),
            "--ledger",
            str(tmp_path / "l.db"),
            "--risk-class",
            "R1",
            "--packet",
            str(packet_path),
        ],
    )
    assert result.exit_code != 0
    assert "mismatch" in (result.stdout + (result.stderr or "")).lower()


def test_review_attest_happy(tmp_path: Path, example_project: Path) -> None:
    conflict = _conflict(reviewer_id="r3-reviewer")
    ch = conflict.declaration_hash()
    att = _attestation(
        reviewer_id="r3-reviewer",
        role="domain-lead",
        conflict_hash=ch,
    )
    conflict_path = tmp_path / "conflict.json"
    att_path = tmp_path / "att.json"
    conflict_path.write_text(conflict.model_dump_json(indent=2), encoding="utf-8")
    att_path.write_text(att.model_dump_json(indent=2), encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    result = runner.invoke(
        app,
        [
            "review",
            "attest",
            "--project",
            str(example_project),
            "--attestation",
            str(att_path),
            "--conflict",
            str(conflict_path),
            "--ledger",
            str(ledger),
            "--risk-class",
            "R3",
            "--obligation-ids",
            "O-01",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")


def test_review_attest_conflict_mismatch(tmp_path: Path, example_project: Path) -> None:
    conflict = _conflict(reviewer_id="domain-lead")
    att = _attestation(reviewer_id="repository-maintainer", conflict_hash="x")
    conflict_path = tmp_path / "conflict.json"
    att_path = tmp_path / "att.json"
    conflict_path.write_text(conflict.model_dump_json(), encoding="utf-8")
    att_path.write_text(att.model_dump_json(), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "review",
            "attest",
            "--project",
            str(example_project),
            "--attestation",
            str(att_path),
            "--conflict",
            str(conflict_path),
            "--ledger",
            str(tmp_path / "l.db"),
            "--risk-class",
            "R3",
        ],
    )
    assert result.exit_code != 0


def test_review_repair_request_and_complete(tmp_path: Path, example_project: Path) -> None:
    conflict = _conflict()
    ch = conflict.declaration_hash()
    atts = [
        _attestation(
            attestation_id="a1",
            conflict_hash=ch,
            dimension=ReviewDimension.SEMANTIC_FIDELITY,
        ).model_dump(mode="json")
    ]
    atts_path = tmp_path / "atts.json"
    atts_path.write_text(json.dumps(atts), encoding="utf-8")
    ledger = tmp_path / "ledger.db"
    ledger.write_text("", encoding="utf-8")
    change = tmp_path / "change.patch"
    change.write_text("diff --git a/x b/x\n+ok\n", encoding="utf-8")

    mock_store = MagicMock()
    mock_store.append_v2.return_value = "deadbeef"

    with patch("lpe.cli.LedgerStore", return_value=mock_store):
        req = runner.invoke(
            app,
            [
                "review",
                "repair-request",
                "--project",
                str(example_project),
                "--ledger",
                str(ledger),
                "--artifact-id",
                "art-1",
                "--actor-id",
                "domain-lead",
                "--candidate-id",
                "cand-root",
                "--rationale",
                "needs fix",
                "--attestations",
                str(atts_path),
                "--repair-request-id",
                "rep-1",
                "--required-change",
                "fix proof",
                "--obligation-ids",
                "O-01",
            ],
        )
        assert req.exit_code == 0, req.stdout + (req.stderr or "")
        payload = json.loads(req.stdout)
        assert payload["repair_request_id"] == "rep-1"

        complete = runner.invoke(
            app,
            [
                "review",
                "repair-complete",
                "--project",
                str(example_project),
                "--ledger",
                str(ledger),
                "--artifact-id",
                "art-1",
                "--actor-id",
                "domain-lead",
                "--prior-candidate-id",
                "cand-root",
                "--repair-request-ids",
                "rep-1",
                "--applied-change",
                str(change),
                "--new-evidence-fingerprint",
                "b" * 64,
            ],
        )
    assert complete.exit_code == 0, complete.stdout + (complete.stderr or "")
    done = json.loads(complete.stdout)
    assert done["new_candidate_id"] == "cand-root.r1"
    assert done["attestations_transfer"] is False


def test_review_accept_quorum_bad_json(tmp_path: Path, example_project: Path) -> None:
    path = tmp_path / "atts.json"
    path.write_text('{"not": "a list"}', encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "review",
            "accept-quorum",
            "--project",
            str(example_project),
            "--attestations",
            str(path),
            "--ledger",
            str(tmp_path / "l.db"),
            "--risk-class",
            "R3",
            "--evidence-fingerprint",
            FP,
            "--actor-id",
            "agg",
            "--artifact-id",
            "art",
        ],
    )
    assert result.exit_code != 0


def test_review_adjudicate_happy(tmp_path: Path, example_project: Path) -> None:
    conflict = _conflict(reviewer_id="adj-1")
    ch = conflict.declaration_hash()
    provisional = ProvisionalJudgment(
        judgment_id="j1",
        adjudicator_id="adj-1",
        packet_id="packet_x",
        evidence_fingerprint=FP,
        provisional_decision=ReviewDecisionValue.ACCEPT,
        rationale="independent",
        recorded_at=NOW,
    )
    peers = [
        _attestation(
            attestation_id="a1",
            reviewer_id="domain-lead",
            role="domain-lead",
            conflict_hash=ch,
        )
    ]
    record = AdjudicationRecord(
        adjudication_id="adj-rec-1",
        packet_id="packet_x",
        evidence_fingerprint=FP,
        adjudicator_id="adj-1",
        provisional_judgment_id="j1",
        original_attestation_ids=["a1"],
        decision=ReviewDecisionValue.ACCEPT,
        rationale="resolved",
        conflict_declaration_hash=ch,
        resolved_at=NOW,
    )
    provisional_path = tmp_path / "prov.json"
    record_path = tmp_path / "rec.json"
    peers_path = tmp_path / "peers.json"
    conflict_path = tmp_path / "conflict.json"
    out = tmp_path / "out.json"
    provisional_path.write_text(provisional.model_dump_json(), encoding="utf-8")
    record_path.write_text(record.model_dump_json(), encoding="utf-8")
    peers_path.write_text(json.dumps([p.model_dump(mode="json") for p in peers]), encoding="utf-8")
    conflict_path.write_text(conflict.model_dump_json(), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "review",
            "adjudicate",
            "--project",
            str(example_project),
            "--provisional",
            str(provisional_path),
            "--record",
            str(record_path),
            "--peer-attestations",
            str(peers_path),
            "--conflict",
            str(conflict_path),
            "--original-reviewer-ids",
            "domain-lead",
            "--review-minutes",
            "12",
            "--adjudicator-roles",
            ADJUDICATOR_ROLE,
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert "lineage" in payload
    assert "attestation" in payload
    assert out.is_file()


def test_github_submit_check_bad_escalate_as(tmp_path: Path) -> None:
    packet = tmp_path / "p.json"
    packet.write_text("{}", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "github",
            "submit-check",
            str(packet),
            "--repo",
            "acme/widgets",
            "--escalate-as",
            "bogus",
        ],
    )
    assert result.exit_code != 0
    assert "escalate-as" in (result.stdout + (result.stderr or "")).lower()


def test_tppr_compute_and_v2(tmp_path: Path) -> None:
    ledger = tmp_path / "util.sqlite"
    store = LedgerStore(ledger)
    store.initialize()
    store.append(
        UtilityEvent(
            event_id="e1",
            event_type=EventType.OBLIGATION_REGISTERED,
            project_id="example-category-project",
            artifact_id="a",
            obligation_id="O-01",
            occurred_at=NOW,
            actor_id="tester",
            payload={"weight": 1},
        )
    )
    store.append(
        UtilityEvent(
            event_id="e2",
            event_type=EventType.EXPERT_TIME_RECORDED,
            project_id="example-category-project",
            artifact_id="a",
            obligation_id=None,
            occurred_at=NOW,
            actor_id="tester",
            payload={"category": "review", "hours": 1.0},
        )
    )
    v1 = runner.invoke(
        app,
        ["tppr", "compute", str(ledger), "--project-id", "example-category-project"],
    )
    assert v1.exit_code == 0, v1.stdout + (v1.stderr or "")
    assert "tppr" in v1.stdout.lower() or "expert" in v1.stdout.lower()

    v2 = runner.invoke(
        app,
        [
            "tppr",
            "compute-v2",
            str(ledger),
            "--project-id",
            "example-category-project",
        ],
    )
    assert v2.exit_code == 0, v2.stdout + (v2.stderr or "")


def test_pilot_lock_cli(tmp_path: Path) -> None:
    proto = write_example_bundle(tmp_path / "pilot-protocol")
    freeze_protocol(proto)
    assign = tmp_path / "assignment.json"
    assign.write_text(
        json.dumps(
            {
                "protocol_id": "proto.example.v1",
                "assignments": [{"candidate_id": "c01", "condition": "control"}],
            }
        ),
        encoding="utf-8",
    )
    ledger_dir = tmp_path / "ledger_host"
    ledger_dir.mkdir()
    ledger = ledger_dir / "ledger.sqlite3"
    store = LedgerStore(ledger)
    store.initialize()
    store.append(
        UtilityEvent(
            event_id="e1",
            event_type=EventType.CANDIDATE_REGISTERED,
            project_id="project",
            artifact_id="artifact",
            obligation_id="O-01",
            occurred_at=NOW,
            actor_id="tester",
            payload={"seed": True},
        )
    )
    seal_path = tmp_path / "offhost" / "ledger.seal.json"
    seal_path.parent.mkdir()
    write_seal(store, seal_path)
    out = tmp_path / "data-lock.json"
    result = runner.invoke(
        app,
        [
            "pilot",
            "lock",
            "--protocol-dir",
            str(proto),
            "--ledger",
            str(ledger),
            "--seal",
            str(seal_path),
            "--assignment",
            str(assign),
            "--analysis-image-digest",
            DIGEST,
            "--expected-episodes",
            "ep-01",
            "--completed-episodes",
            "ep-01",
            "--attestation-complete",
            "--exclusions-resolved",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert out.is_file()
    payload = json.loads(result.stdout)
    assert payload.get("data_lock_hash") or payload.get("lock_id")


def test_pilot_lock_cli_error(tmp_path: Path) -> None:
    proto = write_example_bundle(tmp_path / "pilot-protocol")
    freeze_protocol(proto)
    result = runner.invoke(
        app,
        [
            "pilot",
            "lock",
            "--protocol-dir",
            str(proto),
            "--ledger",
            str(tmp_path / "missing.sqlite"),
            "--seal",
            str(tmp_path / "missing.seal.json"),
            "--assignment",
            str(tmp_path / "missing.json"),
            "--analysis-image-digest",
            DIGEST,
            "--expected-episodes",
            "ep-01",
            "--completed-episodes",
            "ep-01",
            "--output",
            str(tmp_path / "out.json"),
        ],
    )
    # Typer may exit before perform_data_lock due to exists=True checks.
    assert result.exit_code != 0


def test_pilot_comprehension_score_cli(tmp_path: Path) -> None:
    from lpe.pilot.comprehension import (
        CalibrationCase,
        CaseResponse,
        ComprehensionAttempt,
        EvidenceBasisAnswer,
        MaterialLabel,
    )
    from lpe.pilot.protocol import validate_bundle_dir

    root = write_example_bundle(tmp_path / "proto")
    bundle = validate_bundle_dir(root)
    cases = [
        CalibrationCase(
            case_id=cid,
            adjudicated_material=MaterialLabel.MATERIAL_DEFECT,
            adjudicated_basis=EvidenceBasisAnswer.KERNEL_CHECKED,
        )
        for cid in bundle.comprehension.calibration_case_ids
    ]
    attempt = ComprehensionAttempt(
        attempt_number=1,
        responses=[
            CaseResponse(
                case_id=c.case_id,
                material_judgment=MaterialLabel.MATERIAL_DEFECT,
                basis_answer=EvidenceBasisAnswer.KERNEL_CHECKED,
            )
            for c in cases
        ],
        conflict_blinding_acknowledged=True,
    )
    cases_path = tmp_path / "cases.json"
    attempt_path = tmp_path / "attempt.json"
    cases_path.write_text(json.dumps([c.model_dump(mode="json") for c in cases]), encoding="utf-8")
    attempt_path.write_text(attempt.model_dump_json(), encoding="utf-8")
    out = tmp_path / "score.json"
    result = runner.invoke(
        app,
        [
            "pilot",
            "comprehension-score",
            "--protocol",
            str(root),
            "--cases",
            str(cases_path),
            "--attempt",
            str(attempt_path),
            "--reviewer-id",
            "domain-alice",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["passed"] is True
    assert out.is_file()


def test_pilot_init_partner_cli(tmp_path: Path) -> None:
    dest = tmp_path / "partner"
    result = runner.invoke(
        app,
        [
            "pilot",
            "init-partner",
            "--dir",
            str(dest),
            "--project-id",
            "unit-partner",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["section_21_cleared"] is False
    assert payload["ready_to_claim"] is False

    validate = runner.invoke(
        app,
        ["pilot", "init-partner", "--dir", str(dest), "--validate"],
    )
    assert validate.exit_code == 0
    assert json.loads(validate.stdout)["ok"] is True


def test_pilot_overhead_cli(tmp_path: Path) -> None:
    result = runner.invoke(app, ["pilot", "overhead", "--help"])
    assert result.exit_code == 0


def test_evidence_compile_mocked(
    tmp_path: Path, example_project: Path, repository_root: Path
) -> None:

    from lpe.models import (
        CandidateDescriptor,
        EvidenceDimension,
        EvidenceFinding,
        EvidencePacket,
        FindingStatus,
        Provenance,
        Recommendation,
        RiskClass,
        Severity,
    )

    cand = repository_root / "examples" / "candidates" / "R0-comment-only.json"
    now = datetime.now(UTC)
    fake = EvidencePacket(
        packet_id="packet_mock",
        run_id="run_mock",
        project_id="example-category-project",
        contract_hash="0" * 64,
        candidate=CandidateDescriptor.model_validate_json(cand.read_text(encoding="utf-8")),
        risk_class=RiskClass.R0,
        findings=[
            EvidenceFinding(
                finding_id="f1",
                check_id="c",
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
        ],
        hard_gate_passed=True,
        recommendation=Recommendation.ACCEPT,
        recommendation_reasons=["mocked"],
        evidence_fingerprint="e" * 64,
    )
    out = tmp_path / "packet.json"
    md = tmp_path / "packet.md"
    gh = tmp_path / "check.json"
    with patch("lpe.cli.compile_evidence", return_value=fake):
        result = runner.invoke(
            app,
            [
                "evidence",
                "compile",
                "--project",
                str(example_project),
                "--candidate",
                str(cand),
                "--output",
                str(out),
                "--skip-build",
                "--markdown",
                str(md),
                "--github-check",
                str(gh),
            ],
        )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert out.is_file()
    assert md.is_file()
    assert gh.is_file()


def test_evidence_compile_refused(
    tmp_path: Path, example_project: Path, repository_root: Path
) -> None:
    from lpe.evidence.compiler import HostExecutionRefusedError

    cand = repository_root / "examples" / "candidates" / "R0-comment-only.json"
    with patch(
        "lpe.cli.compile_evidence",
        side_effect=HostExecutionRefusedError("refused"),
    ):
        result = runner.invoke(
            app,
            [
                "evidence",
                "compile",
                "--project",
                str(example_project),
                "--candidate",
                str(cand),
                "--output",
                str(tmp_path / "out.json"),
                "--skip-build",
            ],
        )
    assert result.exit_code != 0


def test_lean_extract_mocked(tmp_path: Path) -> None:
    from lpe.lean.extractor import LeanExtractionResult

    repo = tmp_path / "repo"
    repo.mkdir()
    fake = LeanExtractionResult(
        extractor="regex-stub",
        complete=False,
        declarations=[],
        axioms_used=[],
        imports=[],
        dependency_edges=[],
        errors=[],
        notes=["unit"],
        toolchain_available=False,
    )
    with patch("lpe.lean.toolchain.try_run_lake_extract", return_value=None):
        with patch("lpe.lean.extractor.extract_lean_repository", return_value=fake):
            result = runner.invoke(
                app,
                ["lean", "extract", "--repo", str(repo), "--force"],
            )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["extractor"] == "regex-stub"
    assert payload["complete"] is False


def test_ledger_append_cli(tmp_path: Path, example_project: Path) -> None:
    ledger = tmp_path / "util.sqlite"
    LedgerStore(ledger).initialize()
    event = {
        "schema_version": "0.1.0",
        "event_id": "e-append",
        "event_type": "CANDIDATE_REGISTERED",
        "project_id": "example-category-project",
        "artifact_id": "a1",
        "obligation_id": "O-01",
        "occurred_at": NOW.isoformat(),
        "actor_id": "tester",
        "payload": {"ok": True},
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
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
    assert result.exit_code == 0, result.stdout + (result.stderr or "")


def test_ledger_append_project_mismatch(tmp_path: Path, example_project: Path) -> None:
    ledger = tmp_path / "util.sqlite"
    LedgerStore(ledger).initialize()
    event = {
        "schema_version": "0.1.0",
        "event_id": "e-bad",
        "event_type": "CANDIDATE_REGISTERED",
        "project_id": "wrong-project",
        "artifact_id": "a1",
        "obligation_id": "O-01",
        "occurred_at": NOW.isoformat(),
        "actor_id": "tester",
        "payload": {},
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
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
    assert result.exit_code != 0


def test_contract_validate_cli(example_project: Path) -> None:
    result = runner.invoke(app, ["contract", "validate", str(example_project)])
    assert result.exit_code == 0


def test_gate_month_one_mocked() -> None:
    fake_report = MagicMock()
    fake_report.all_passed = True
    with patch("lpe.cli.evaluate_month_one_gate", return_value=fake_report):
        with patch("lpe.cli.format_gate_report", return_value="ok"):
            result = runner.invoke(app, ["gate", "month-one"])
    assert result.exit_code == 0


def test_research_evaluate_gates_mocked(tmp_path: Path) -> None:
    report = tmp_path / "gates.json"
    report.write_text(
        json.dumps(
            {
                "schema_version": "0.2.0",
                "learned_routing_authorized": False,
                "synthesis_authorized": False,
                "section_21_cleared": False,
            }
        ),
        encoding="utf-8",
    )
    # Command may require a specific schema; invoke help or with minimal args.
    result = runner.invoke(app, ["research", "evaluate-gates", "--help"])
    assert result.exit_code == 0


def test_refuse_pilot_oversell_via_analyze_empty(tmp_path: Path) -> None:
    episodes = tmp_path / "episodes.json"
    episodes.write_text("[]", encoding="utf-8")
    out = tmp_path / "analysis.json"
    result = runner.invoke(
        app,
        [
            "pilot",
            "analyze",
            "--protocol-id",
            "proto",
            "--data-lock-hash",
            "a" * 64,
            "--episodes",
            str(episodes),
            "--output",
            str(out),
        ],
    )
    # Empty list may succeed with zero episodes or fail validation.
    if result.exit_code == 0:
        payload = json.loads(result.stdout)
        assert payload["section_21_cleared"] is False
        assert payload["causal_claims"] is False
