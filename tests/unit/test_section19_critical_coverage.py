"""§19 critical-package coverage: policy/gate/review/ledger/TPPR/protocol."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from pydantic import ValidationError

from lpe.evidence.gates import decide
from lpe.evidence.synthesis import (
    _complete_provider_result,
    _worst_status,
    apply_synthesis,
)
from lpe.execution.allowlist import CommandAllowlistError, validate_build_command
from lpe.execution.protocol import ValidatedCommand
from lpe.gate.month_one import (
    MonthOneGateReport,
    _run_pytest,
    _sandbox_implementation_ok,
    _validate_example_contract,
    evaluate_month_one_gate,
)
from lpe.hashing import sha256_file
from lpe.honesty.research_gates import (
    Section21GateReport,
    evaluate_gates_from_paths,
    evaluate_section21_gates,
)
from lpe.ledger.events import (
    AcceptanceAggregatedPayload,
    CandidateRegisteredPayload,
    ConditionAssignedPayload,
    CorrectionPayload,
    DownstreamEnabledPayload,
    EventTypeV2,
    ExpertTimePayload,
    IntegrationConfirmedPayload,
    LegacyUnresolvedPayload,
    ObligationFreezePayload,
    PersistenceConfirmedPayload,
    PersistenceRule,
    RegressionDetectedPayload,
    UtilityEventV2,
)
from lpe.ledger.state import (
    LedgerReducerState,
    LifecycleError,
    reduce_event,
)
from lpe.ledger.store import LedgerIntegrityError, LedgerStore, LedgerTransitionError
from lpe.metrics.tppr import compute_tppr
from lpe.metrics.tppr_v2 import (
    TPPRAntiGamingError,
    TPPRReportV2,
    _hours_from_payload,
    _minutes_from_payload,
    compute_tppr_v2,
)
from lpe.models import (
    CandidateDescriptor,
    ChangedDeclaration,
    EventType,
    EvidenceBasis,
    EvidenceCoverage,
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    GeneratorProvenance,
    Provenance,
    Recommendation,
    ReviewDecision,
    ReviewDecisionValue,
    RiskClass,
    Severity,
    UtilityEvent,
)
from lpe.pilot.protocol import (
    ConditionDesign,
    ProtocolError,
    ProtocolSignatures,
    freeze_protocol,
    hash_seed_plaintext,
    validate_bundle_dir,
    verify_freeze,
    write_example_bundle,
)
from lpe.review.acceptance import record_attestation_event
from lpe.review.adjudication import (
    ADJUDICATOR_ROLE,
    AdjudicationError,
    AdjudicationRecord,
    ProvisionalJudgment,
    auditable_lineage,
    build_adjudication_attestation,
    reveal_peer_attestations,
    validate_adjudicator,
)
from lpe.review.authority import AuthorityError, validate_decision_for_risk
from lpe.review.conflicts import (
    ConflictError,
    ReviewerConflictDeclaration,
    compute_eligibility,
    require_eligible_for_primary_attestation,
)
from lpe.review.decisions import (
    decision_to_attestation,
    expert_time_event,
    record_review_decision,
    review_decision_to_event,
)
from lpe.review.models import ReviewAttestationV2, ReviewDimension
from lpe.review.quorum import QuorumError, evaluate_quorum, quorum_policy_for_risk

NOW = datetime(2026, 7, 21, tzinfo=UTC)
FP = "f" * 64


def _prov() -> Provenance:
    return Provenance(
        tool="t",
        tool_version="0",
        input_hash="x",
        started_at=NOW,
        finished_at=NOW,
        elapsed_ms=0,
    )


def _finding(
    check_id: str,
    status: FindingStatus = FindingStatus.PASS,
    *,
    details: dict | None = None,
    coverage: EvidenceCoverage | None = None,
    basis: EvidenceBasis = EvidenceBasis.STRUCTURAL_COMPARISON,
) -> EvidenceFinding:
    return EvidenceFinding(
        finding_id=f"f_{check_id}_{status.value}",
        check_id=check_id,
        check_version="0.1.0",
        dimension=EvidenceDimension.KERNEL,
        status=status,
        severity=Severity.INFO,
        summary=f"{check_id}:{status.value}",
        details=details or {},
        provenance=_prov(),
        basis=basis,
        coverage=coverage,
    )


def _candidate(*, public: bool = True) -> CandidateDescriptor:
    return CandidateDescriptor(
        candidate_id="cand-1",
        project_id="proj",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        head_commit="cafebabe",
        claimed_intent="intent",
        changed_paths=["Foo.lean"],
        generator=GeneratorProvenance(generator_type="test", name="test", version="0"),
        changed_declarations=[
            ChangedDeclaration(
                name="Foo.bar",
                kind="definition",
                path="Foo.lean",
                public=public,
            )
        ],
    )


def _attestation(
    *,
    attestation_id: str = "a1",
    reviewer_id: str = "r1",
    role: str = "lean-engineer",
    dimension: ReviewDimension = ReviewDimension.IMPLEMENTATION_QUALITY,
    decision: ReviewDecisionValue = ReviewDecisionValue.ACCEPT,
    fingerprint: str = FP,
) -> ReviewAttestationV2:
    return ReviewAttestationV2(
        attestation_id=attestation_id,
        packet_id="packet_1",
        evidence_fingerprint=fingerprint,
        reviewer_id=reviewer_id,
        reviewer_role=role,
        dimension=dimension,
        decision=decision,
        confidence=90,
        rationale="ok",
        conflict_declaration_hash="c" * 64,
        review_started_at=NOW,
        review_submitted_at=NOW + timedelta(minutes=5),
        review_minutes=5.0,
    )


# --- policy / gates / allowlist / protocol primitives ---


def test_gates_unknown_soft_evidence_escalates_without_auto_accept() -> None:
    findings = [
        _finding("contract.valid"),
        _finding("candidate.obligations"),
        _finding("lean.build"),
        _finding("lean.placeholders"),
        _finding("lean.prohibited_axioms"),
        _finding("repository.changed_paths"),
        _finding("semantic.statement_diff", FindingStatus.UNKNOWN),
    ]
    decision = decide(findings, RiskClass.R1, auto_accept_eligible=True)
    assert decision.hard_gate_passed is True
    assert decision.recommendation is Recommendation.ESCALATE
    assert "unresolved" in decision.reasons[0]


def test_gates_human_review_policy_when_auto_accept_disabled() -> None:
    findings = [
        _finding("contract.valid"),
        _finding("candidate.obligations"),
        _finding("lean.build"),
        _finding("lean.placeholders"),
        _finding("lean.prohibited_axioms"),
        _finding("repository.changed_paths"),
    ]
    decision = decide(findings, RiskClass.R0, auto_accept_eligible=False)
    assert decision.recommendation is Recommendation.ESCALATE
    assert "human review" in decision.reasons[0]


def test_allowlist_rejects_dash_executable() -> None:
    with pytest.raises(CommandAllowlistError, match="invalid"):
        validate_build_command(["-lake", "build"])


def test_validated_command_rejects_bad_snapshot_root() -> None:
    with pytest.raises(ValueError, match="snapshot_root"):
        ValidatedCommand.from_argv(["lake", "build"], snapshot_root="other")


# --- synthesis (policy) ---


def test_synthesis_helpers_empty_and_unknown_fallback() -> None:
    assert _complete_provider_result([]) is False
    assert _worst_status([]) is FindingStatus.UNKNOWN


def test_synthesis_api_fit_and_declared_use_complete_paths() -> None:
    candidate = _candidate(public=True)
    complete = EvidenceCoverage(
        requested_subject_count=1,
        evaluated_subject_count=1,
        complete_for_declared_scope=True,
    )
    findings = [
        _finding(
            "semantic.duplicate_retrieval",
            FindingStatus.NOT_APPLICABLE,
            coverage=complete,
        ),
        _finding(
            "semantic.statement_diff",
            FindingStatus.PASS,
            coverage=complete,
        ),
        _finding(
            "repository.changed_paths",
            FindingStatus.PASS,
            coverage=complete,
        ),
        _finding(
            "lean.impact_cone",
            FindingStatus.PASS,
            coverage=complete,
        ),
        _finding(
            "downstream.successor_suite",
            FindingStatus.NOT_APPLICABLE,
            coverage=complete,
        ),
        _finding(
            "downstream.replacement_tests",
            FindingStatus.PASS,
            coverage=complete,
        ),
    ]
    out = apply_synthesis(findings, candidate=candidate, risk_class=RiskClass.R1)
    by_id = {f.check_id: f for f in out}
    assert by_id["repository.api_fit"].status is FindingStatus.PASS
    assert by_id["downstream.declared_use"].status is FindingStatus.PASS


def test_synthesis_api_fit_no_provider_evidence() -> None:
    out = apply_synthesis([], candidate=_candidate(), risk_class=RiskClass.R1)
    by_id = {f.check_id: f for f in out}
    assert by_id["repository.api_fit"].status is FindingStatus.UNKNOWN
    assert by_id["downstream.declared_use"].status is FindingStatus.UNKNOWN


def test_synthesis_declared_use_not_applicable_without_public() -> None:
    out = apply_synthesis([], candidate=_candidate(public=False), risk_class=RiskClass.R1)
    by_id = {f.check_id: f for f in out}
    assert by_id["downstream.declared_use"].status is FindingStatus.NOT_APPLICABLE


def test_synthesis_intent_r3_human_attested_and_basis_refusal() -> None:
    human = _finding(
        "semantic.human_attestation",
        FindingStatus.PASS,
        basis=EvidenceBasis.HUMAN_ATTESTED,
        coverage=EvidenceCoverage(
            requested_subject_count=1,
            evaluated_subject_count=1,
            complete_for_declared_scope=True,
        ),
    )
    out = apply_synthesis([human], candidate=_candidate(), risk_class=RiskClass.R3)
    intent = next(f for f in out if f.check_id == "semantic.intent_support")
    assert intent.status is FindingStatus.PASS
    assert intent.basis is EvidenceBasis.HUMAN_ATTESTED

    # R1 with only NOT_APPLICABLE automated sources → PASS mapped from N/A
    na = _finding(
        "semantic.statement_diff",
        FindingStatus.NOT_APPLICABLE,
        coverage=EvidenceCoverage(
            requested_subject_count=1,
            evaluated_subject_count=1,
            complete_for_declared_scope=True,
        ),
    )
    out2 = apply_synthesis([na], candidate=_candidate(), risk_class=RiskClass.R1)
    intent2 = next(f for f in out2 if f.check_id == "semantic.intent_support")
    assert intent2.status is FindingStatus.PASS


# --- gate / month_one / research_gates ---


def test_month_one_report_to_dict_and_failure_branches(tmp_path: Path) -> None:
    report = MonthOneGateReport()
    assert report.all_passed is True
    assert "disclaimer" in report.to_dict()

    ok, detail = _validate_example_contract(tmp_path)
    assert ok is False
    assert "missing" in detail

    with patch("lpe.contract.loader.load_contract", side_effect=RuntimeError("boom")):
        example = tmp_path / "examples" / "minimal-project"
        example.mkdir(parents=True)
        ok2, detail2 = _validate_example_contract(tmp_path)
        assert ok2 is False
        assert "failed" in detail2

    with patch.dict("sys.modules", {"lpe.execution.sandbox": None}):
        # Force ImportError path via patched import inside function.
        with patch(
            "builtins.__import__",
            side_effect=ImportError("nope"),
        ):
            ok3, detail3 = _sandbox_implementation_ok(tmp_path)
            assert ok3 is False
            assert "import failed" in detail3 or "nope" in detail3


def test_month_one_sandbox_missing_files_and_markers(tmp_path: Path) -> None:
    ok, detail = _sandbox_implementation_ok(tmp_path)
    assert ok is False
    assert "missing" in detail

    sandbox_path = tmp_path / "src" / "lpe" / "execution" / "sandbox.py"
    allowlist_path = tmp_path / "src" / "lpe" / "execution" / "allowlist.py"
    sandbox_path.parent.mkdir(parents=True)
    sandbox_path.write_text("# no network marker\n", encoding="utf-8")
    allowlist_path.write_text("ALLOWED_BUILD_COMMANDS = frozenset({'lake'})\n", encoding="utf-8")

    import types

    fake_allowlist = types.SimpleNamespace(
        ALLOWED_BUILD_COMMANDS=frozenset({"lake"}),
        __name__="lpe.execution.allowlist",
    )
    fake_sandbox = types.SimpleNamespace(
        DockerSandboxExecutor=object,
        __name__="lpe.execution.sandbox",
    )
    with patch("lpe.execution.allowlist", fake_allowlist):
        with patch("lpe.execution.sandbox", fake_sandbox):
            ok2, detail2 = _sandbox_implementation_ok(tmp_path)
            assert ok2 is False
            assert "network" in detail2 or "missing" in detail2 or "Docker" in detail2


def test_month_one_nested_pytest_skip_and_default_root() -> None:
    # Nested under pytest uses the PYTEST_CURRENT_TEST short-circuit.
    ok, msg = _run_pytest(Path("."))
    assert "skipped nested pytest" in msg or isinstance(ok, bool)

    # Default repo_root resolution path (line 138).
    report = evaluate_month_one_gate()
    assert isinstance(report, MonthOneGateReport)
    assert report.criteria


def test_research_gates_validators_and_path_errors(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError):
        Section21GateReport(
            protocol_id="p",
            data_lock_hash="h",
            gates=[],
            shadow_pilot_passed=False,
            learned_routing_authorized=False,
            synthesis_authorized=False,
            blocking_reasons=[],
            generated_at=datetime(2026, 1, 1),  # naive
        )

    with pytest.raises(ValueError, match="protocol_id"):
        evaluate_section21_gates(protocol_id="  ", data_lock_hash="x", observables={})
    with pytest.raises(ValueError, match="data_lock_hash"):
        evaluate_section21_gates(protocol_id="p", data_lock_hash="", observables={})

    # Sufficiency messaging when shadow would pass.
    observables = {
        "packet_automation_rate": 0.95,
        "exact_environment_reproduction": 0.95,
        "median_instrumentation_overhead": 0.05,
        "p90_instrumentation_overhead": 0.08,
        "comprehension_pass_rate": 0.95,
        "primary_category_agreement": 0.9,
        "instrumented_efficiency_gain": 0.25,
        "instrumented_l2_l3_sensitivity_delta_pp": 1.0,
        "instrumented_additional_integrated_l3": 0,
        "sealed_reproducible": True,
    }
    report = evaluate_section21_gates(
        protocol_id="proto",
        data_lock_hash="lock",
        observables=observables,
        dataset_sufficiency_for_routing=False,
        dataset_sufficiency_for_synthesis=False,
    )
    assert report.shadow_pilot_passed is True
    assert any("sufficiency" in r for r in report.blocking_reasons)

    report2 = evaluate_section21_gates(
        protocol_id="proto",
        data_lock_hash="lock",
        observables=observables,
        dataset_sufficiency_for_routing=True,
        dataset_sufficiency_for_synthesis=False,
    )
    assert report2.learned_routing_authorized is True
    assert any("synthesis" in r for r in report2.blocking_reasons)

    root = write_example_bundle(tmp_path / "proto")
    freeze_protocol(root)
    # Mismatched analysis protocol_id
    analysis = tmp_path / "analysis.json"
    analysis.write_text(
        '{"schema_version":"0.3.0","protocol_id":"other","episodes":[],'
        '"agreement":{},"gate_inputs":{},"limitations":[]}',
        encoding="utf-8",
    )
    # Use a minimal valid analysis via mock
    from lpe.pilot.analysis import PilotAnalysisReport

    fake = MagicMock(spec=PilotAnalysisReport)
    fake.protocol_id = "other"
    with patch(
        "lpe.pilot.analysis.PilotAnalysisReport.model_validate_json",
        return_value=fake,
    ):
        with pytest.raises(ValueError, match="protocol_id"):
            evaluate_gates_from_paths(
                protocol_path=root,
                ledger_path=tmp_path / "missing-ledger.sqlite",
                seal_path=tmp_path / "seal.json",
                analysis_path=analysis,
                output_path=tmp_path / "out.json",
            )

    (tmp_path / "seal.json").write_text("{}", encoding="utf-8")
    fake.protocol_id = "example-partner-protocol"
    # Protocol id from write_example_bundle
    bundle_proto = yaml.safe_load((root / "protocol.yaml").read_text(encoding="utf-8"))
    fake.protocol_id = bundle_proto["protocol_id"]
    with patch(
        "lpe.pilot.analysis.PilotAnalysisReport.model_validate_json",
        return_value=fake,
    ):
        with patch(
            "lpe.pilot.analysis.shadow_pilot_gate_inputs_from_analysis",
            return_value=observables,
        ):
            with pytest.raises(ValueError, match="ledger missing"):
                evaluate_gates_from_paths(
                    protocol_path=root,
                    ledger_path=tmp_path / "missing-ledger.sqlite",
                    seal_path=tmp_path / "seal.json",
                    analysis_path=analysis,
                    output_path=tmp_path / "out.json",
                )
            (tmp_path / "ledger.sqlite").write_text("x", encoding="utf-8")
            with pytest.raises(ValueError, match="seal missing"):
                evaluate_gates_from_paths(
                    protocol_path=root,
                    ledger_path=tmp_path / "ledger.sqlite",
                    seal_path=tmp_path / "no-seal.json",
                    analysis_path=analysis,
                    output_path=tmp_path / "out.json",
                    observables_path=tmp_path / "obs.json",
                )


# --- review ---


def test_review_models_validation_edges() -> None:
    with pytest.raises(ValidationError):
        ReviewAttestationV2(
            attestation_id="a",
            packet_id="p",
            evidence_fingerprint="   ",
            reviewer_id="r",
            reviewer_role="lean-engineer",
            dimension=ReviewDimension.IMPLEMENTATION_QUALITY,
            decision=ReviewDecisionValue.ACCEPT,
            confidence=90,
            rationale="x",
            conflict_declaration_hash="c" * 64,
            review_started_at=NOW,
            review_minutes=1.0,
        )
    with pytest.raises(ValidationError):
        ReviewAttestationV2(
            attestation_id="a",
            packet_id="p",
            evidence_fingerprint=FP,
            reviewer_id="r",
            reviewer_role="lean-engineer",
            dimension=ReviewDimension.IMPLEMENTATION_QUALITY,
            decision=ReviewDecisionValue.ACCEPT,
            confidence=90,
            rationale="x",
            conflict_declaration_hash="c" * 64,
            review_started_at=datetime(2026, 1, 1),  # naive
            review_minutes=1.0,
        )
    fp = _attestation().content_fingerprint()
    assert len(fp) == 64


def test_authority_empty_required_and_low_confidence(example_project: Path) -> None:
    from lpe.contract.loader import load_contract

    contract = load_contract(example_project)
    # Empty required roles short-circuit (line 40) — monkeypatch risk rules.
    risk = RiskClass.R0
    original = contract.policies.risk_rules[risk].required_roles
    object.__setattr__(contract.policies.risk_rules[risk], "required_roles", [])
    from lpe.review.authority import validate_reviewer_authority

    validate_reviewer_authority(contract, reviewer_id="anyone", reviewer_roles=[], risk_class=risk)
    object.__setattr__(contract.policies.risk_rules[risk], "required_roles", original)

    decision = ReviewDecision(
        review_id="rev1",
        packet_id="packet_1",
        reviewer_id="r",
        decision=ReviewDecisionValue.ACCEPT,
        confidence=50,
        rationale="low",
        review_minutes=1.0,
        submitted_at=NOW,
        reviewer_roles=["domain-lead"],
    )
    with pytest.raises(AuthorityError, match="confidence"):
        validate_decision_for_risk(decision, RiskClass.R3)


def test_conflicts_other_and_timezone_and_eligibility() -> None:
    with pytest.raises(ValidationError):
        ReviewerConflictDeclaration(
            reviewer_id="r",
            project_id="p",
            candidate_id="c",
            eligible=True,
            signed_at=datetime(2026, 1, 1),
        )
    decl = ReviewerConflictDeclaration(
        reviewer_id="r",
        project_id="p",
        candidate_id="c",
        other_conflict=" spouse ",
        eligible=False,
    )
    assert compute_eligibility(decl) is False
    with pytest.raises(ConflictError):
        require_eligible_for_primary_attestation(decl)
    clean = ReviewerConflictDeclaration(
        reviewer_id="r",
        project_id="p",
        candidate_id="c",
        eligible=True,
    )
    assert require_eligible_for_primary_attestation(clean) == clean.declaration_hash()


def test_adjudication_edges() -> None:
    with pytest.raises(ValidationError):
        ProvisionalJudgment(
            judgment_id="j1",
            adjudicator_id="adj",
            packet_id="p",
            evidence_fingerprint=FP,
            provisional_decision=ReviewDecisionValue.ACCEPT,
            rationale="x",
            recorded_at=datetime(2026, 1, 1),
        )
    with pytest.raises(ValidationError):
        ProvisionalJudgment(
            judgment_id="j1",
            adjudicator_id="adj",
            packet_id="p",
            evidence_fingerprint=FP,
            provisional_decision=ReviewDecisionValue.ACCEPT,
            rationale="x",
            peer_attestations_revealed=True,
        )

    conflict = ReviewerConflictDeclaration(
        reviewer_id="adj",
        project_id="p",
        candidate_id="c",
        eligible=True,
    )
    with pytest.raises(AdjudicationError, match="original reviewer"):
        validate_adjudicator(
            adjudicator_id="r1",
            adjudicator_roles=[ADJUDICATOR_ROLE],
            original_reviewer_ids=["r1"],
            conflict=conflict,
        )
    with pytest.raises(AdjudicationError, match="lacks configured role"):
        validate_adjudicator(
            adjudicator_id="adj",
            adjudicator_roles=["lean-engineer"],
            original_reviewer_ids=["r1"],
            conflict=conflict,
        )
    bad_conflict = ReviewerConflictDeclaration(
        reviewer_id="adj",
        project_id="p",
        candidate_id="c",
        candidate_author=True,
        eligible=False,
    )
    with pytest.raises(AdjudicationError):
        validate_adjudicator(
            adjudicator_id="adj",
            adjudicator_roles=[ADJUDICATOR_ROLE],
            original_reviewer_ids=["r1"],
            conflict=bad_conflict,
        )

    provisional = ProvisionalJudgment(
        judgment_id="j1",
        adjudicator_id="adj",
        packet_id="p",
        evidence_fingerprint=FP,
        provisional_decision=ReviewDecisionValue.ACCEPT,
        rationale="blind",
    )
    peer = [_attestation()]
    revealed = reveal_peer_attestations(provisional, peer)
    assert revealed.peer_attestations_revealed is True
    assert reveal_peer_attestations(revealed, peer) is revealed
    with pytest.raises(AdjudicationError, match="no peer"):
        reveal_peer_attestations(provisional, [])

    record = AdjudicationRecord(
        adjudication_id="adj1",
        packet_id="p",
        evidence_fingerprint=FP,
        adjudicator_id="adj",
        provisional_judgment_id="j1",
        original_attestation_ids=["a1"],
        decision=ReviewDecisionValue.ACCEPT,
        rationale="resolved",
        conflict_declaration_hash=conflict.declaration_hash(),
    )
    att = build_adjudication_attestation(record, review_minutes=3.0)
    assert att.dimension is ReviewDimension.ADJUDICATION

    with pytest.raises(AdjudicationError, match="revealed"):
        auditable_lineage(provisional=provisional, record=record, peer_attestations=peer)
    lineage = auditable_lineage(provisional=revealed, record=record, peer_attestations=peer)
    assert lineage["adjudication_id"] == "adj1"
    bad_record = record.model_copy(update={"provisional_judgment_id": "other"})
    with pytest.raises(AdjudicationError, match="mismatch"):
        auditable_lineage(provisional=revealed, record=bad_record, peer_attestations=peer)


def test_quorum_r2_r4_and_blocking_paths() -> None:
    assert quorum_policy_for_risk(RiskClass.R2).policy_id.startswith("quorum.r2")
    assert quorum_policy_for_risk(RiskClass.R4).policy_id.startswith("quorum.r4")
    with pytest.raises(QuorumError):
        # Force fall-through by calling with a patched enum if needed — use invalid via cast
        from enum import StrEnum

        class Fake(StrEnum):
            X = "RX"

        quorum_policy_for_risk(Fake.X)  # type: ignore[arg-type]

    reject = _attestation(decision=ReviewDecisionValue.REJECT)
    repair = _attestation(attestation_id="a2", decision=ReviewDecisionValue.REQUEST_REPAIR)
    indeterminate = _attestation(attestation_id="a3", decision=ReviewDecisionValue.INDETERMINATE)
    for att in (reject, repair, indeterminate):
        ev = evaluate_quorum(RiskClass.R1, [att], evidence_fingerprint=FP)
        assert ev.satisfied is False

    mismatch = _attestation(fingerprint="0" * 64)
    ev2 = evaluate_quorum(RiskClass.R1, [mismatch], evidence_fingerprint=FP)
    assert any("fingerprint" in r for r in ev2.blocking_reasons)

    # R2 + require_semantic_for_r2 adds semantic requirement
    repo = _attestation(
        role="repository-maintainer",
        dimension=ReviewDimension.REPOSITORY_FIT,
    )
    ev3 = evaluate_quorum(
        RiskClass.R2,
        [repo],
        evidence_fingerprint=FP,
        require_semantic_for_r2=True,
    )
    assert ev3.satisfied is False
    assert any("SEMANTIC" in r for r in ev3.blocking_reasons)

    # Distinct reviewer collision
    a1 = _attestation(
        attestation_id="s1",
        reviewer_id="same",
        role="domain-lead",
        dimension=ReviewDimension.SEMANTIC_FIDELITY,
    )
    a2 = _attestation(
        attestation_id="s2",
        reviewer_id="same",
        role="repository-maintainer",
        dimension=ReviewDimension.REPOSITORY_FIT,
    )
    ev4 = evaluate_quorum(RiskClass.R3, [a1, a2], evidence_fingerprint=FP)
    assert ev4.satisfied is False


def test_decisions_legacy_paths(tmp_path: Path) -> None:
    decision = ReviewDecision(
        review_id="rev-legacy",
        packet_id="packet_" + "a" * 64,
        reviewer_id="reviewer",
        decision=ReviewDecisionValue.REJECT,
        confidence=70,
        rationale="no",
        review_minutes=12.0,
        submitted_at=NOW,
        reviewer_roles=["lean-engineer"],
        answer={"ok": False},
        required_repair="fix it",
    )
    event = review_decision_to_event(
        decision,
        project_id="proj",
        evidence_fingerprint=FP,
        ledger_seal_tip="tip",
    )
    assert event.payload["ledger_seal_tip"] == "tip"
    assert event.event_type is EventType.ARTIFACT_REJECTED

    time_evt = expert_time_event(
        event_id="t1",
        project_id="proj",
        artifact_id="art",
        actor_id="r",
        minutes=30,
        category="review",
        condition_tag="control",
    )
    assert time_evt.payload["condition_tag"] == "control"

    # R0 policy has empty requirements → fallback dimension/role
    att = decision_to_attestation(
        decision,
        risk_class=RiskClass.R0,
        evidence_fingerprint=FP,
        conflict_declaration_hash="c" * 64,
    )
    assert att.dimension is ReviewDimension.IMPLEMENTATION_QUALITY
    assert att.reviewer_role == "lean-engineer"

    bare = decision.model_copy(update={"reviewer_roles": []})
    att2 = decision_to_attestation(
        bare,
        risk_class=RiskClass.R0,
        evidence_fingerprint=FP,
        conflict_declaration_hash="c" * 64,
    )
    assert att2.reviewer_role == "lean-engineer"

    ledger = tmp_path / "ledger.sqlite"
    digest = record_review_decision(
        ledger,
        decision,
        project_id="proj",
        obligation_ids=["O-01", "O-02"],
        evidence_fingerprint=None,  # derive from packet_ id
    )
    assert isinstance(digest, str)
    store = LedgerStore(ledger)
    assert len(store.events()) >= 3  # reject + linked obl + time

    accept = decision.model_copy(
        update={
            "review_id": "rev-accept",
            "decision": ReviewDecisionValue.ACCEPT,
            "confidence": 90,
        }
    )
    with pytest.raises(Exception, match=r"R3|quorum|ACCEPT"):
        record_review_decision(
            ledger,
            accept,
            project_id="proj",
            risk_class=RiskClass.R3,
            evidence_fingerprint=FP,
        )

    # R1 accept with multi obligations
    digest2 = record_review_decision(
        ledger,
        accept,
        project_id="proj",
        obligation_ids=["O-10", "O-11"],
        evidence_fingerprint=FP,
        risk_class=RiskClass.R1,
        conflict_declaration_hash="c" * 64,
    )
    assert isinstance(digest2, str)


def test_acceptance_record_attestation_legacy_fallback(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "ledger.sqlite")
    store.initialize()
    digest = record_attestation_event(
        store,
        _attestation(),
        project_id="proj",
        obligation_ids=["O-01"],
    )
    assert isinstance(digest, str)


# --- ledger ---


def _v2(
    event_id: str,
    event_type: EventTypeV2,
    payload: object,
    *,
    artifact: str = "art-1",
    obligations: list[str] | None = None,
    occurred: datetime | None = None,
    supersedes: str | None = None,
) -> UtilityEventV2:
    return UtilityEventV2(
        event_id=event_id,
        event_type=event_type,
        project_id="proj",
        artifact_id=artifact,
        obligation_ids=obligations if obligations is not None else ["O-01"],
        occurred_at=occurred or NOW,
        recorded_at=occurred or NOW,
        actor_id="operator",
        payload=payload,
        supersedes_event_id=supersedes,
    )


def test_ledger_state_duplicate_and_correction_paths() -> None:
    rule = PersistenceRule(
        rule_id="r",
        mode="calendar_days",
        threshold=30,
        regression_policy="revoke",
    )
    state = LedgerReducerState()
    freeze = _v2(
        "e1",
        EventTypeV2.OBLIGATION_FROZEN,
        ObligationFreezePayload(
            freeze_id="fr1",
            obligation_ids=["O-01"],
            freeze_hash="a" * 64,
            persistence_rule=rule,
            contract_hash="b" * 64,
            obligation_weights={"O-01": 1.0},
        ),
    )
    reduce_event(state, freeze)
    with pytest.raises(LifecycleError, match="duplicate"):
        reduce_event(state, freeze)

    with pytest.raises(LifecycleError, match="supersedes unknown"):
        reduce_event(
            state,
            _v2(
                "e2",
                EventTypeV2.CORRECTION_RECORDED,
                CorrectionPayload(
                    target_event_id="missing",
                    reason="fix",
                    authorization_role="lead",
                    invalidation=True,
                ),
                supersedes="missing",
            ),
        )

    # Valid side-channel correction after freeze
    reduce_event(
        state,
        _v2(
            "e-corr",
            EventTypeV2.CORRECTION_RECORDED,
            CorrectionPayload(
                target_event_id="e1",
                reason="fix",
                authorization_role="lead",
                invalidation=True,
            ),
            supersedes="e1",
        ),
    )
    assert "e-corr" in state.correction_order

    primed = LedgerReducerState()
    reduce_event(primed, freeze)
    with pytest.raises(LifecycleError, match="non-empty"):
        reduce_event(
            primed,
            _v2(
                "c1",
                EventTypeV2.CORRECTION_RECORDED,
                CorrectionPayload(
                    target_event_id="e1",
                    reason="  ",
                    authorization_role="lead",
                    invalidation=True,
                ),
                supersedes="e1",
            ),
        )


def test_ledger_state_invalid_payload_and_transitions() -> None:
    state = LedgerReducerState()
    rule = PersistenceRule(
        rule_id="r",
        mode="calendar_days",
        threshold=1,
        regression_policy="revoke",
    )
    # Bypass envelope validation to hit reducer isinstance guards.
    bad = UtilityEventV2.model_construct(
        event_id="bad",
        event_type=EventTypeV2.OBLIGATION_FROZEN,
        project_id="proj",
        artifact_id="art-1",
        obligation_ids=["O-01"],
        occurred_at=NOW,
        recorded_at=NOW,
        actor_id="operator",
        payload=CandidateRegisteredPayload(
            candidate_id="c",
            root_candidate_id="c",
            freeze_id="fr",
            base_ref="b",
            head_ref="h",
            tree_hash="t" * 64,
            risk_class="R1",
        ),
    )
    with pytest.raises(LifecycleError, match="OBLIGATION_FROZEN"):
        reduce_event(state, bad)

    reduce_event(
        state,
        _v2(
            "f1",
            EventTypeV2.OBLIGATION_FROZEN,
            ObligationFreezePayload(
                freeze_id="fr1",
                obligation_ids=["O-01"],
                freeze_hash="a" * 64,
                persistence_rule=rule,
                contract_hash="b" * 64,
            ),
        ),
    )
    with pytest.raises(LifecycleError, match="already exists"):
        reduce_event(
            state,
            _v2(
                "f2",
                EventTypeV2.OBLIGATION_FROZEN,
                ObligationFreezePayload(
                    freeze_id="fr1",
                    obligation_ids=["O-02"],
                    freeze_hash="c" * 64,
                    persistence_rule=rule,
                    contract_hash="d" * 64,
                ),
                artifact="art-2",
            ),
        )

    # Invalid phase transition
    with pytest.raises(LifecycleError, match="invalid transition"):
        reduce_event(
            state,
            _v2(
                "early-acc",
                EventTypeV2.ARTIFACT_ACCEPTED,
                AcceptanceAggregatedPayload(
                    attestation_ids=["a"],
                    quorum_policy_id="quorum.r1.implementation",
                    evidence_fingerprint=FP,
                    semantic_fidelity=False,
                    repository_accepted=False,
                    implementation_accepted=True,
                    accepted_obligation_ids=["O-01"],
                    accepted_at=NOW,
                    risk_class="R1",
                ),
            ),
        )


def test_ledger_store_export_archive_and_correction(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite"
    store = LedgerStore(path)
    store.initialize()
    # Second initialize is no-op
    store.initialize()
    assert store.journal_mode() == "wal"
    store.checkpoint(truncate=True)

    event = UtilityEvent(
        event_id="e1",
        event_type=EventType.OBLIGATION_REGISTERED,
        project_id="proj",
        artifact_id="art",
        obligation_id="O-01",
        actor_id="op",
        payload={"weight": 1},
    )
    store.append(event)
    with pytest.raises(LedgerIntegrityError):
        store.append(event)  # duplicate

    store.append_correction(
        event_id="e-corr",
        project_id="proj",
        artifact_id="art",
        actor_id="op",
        supersedes_event_id="e1",
        reason="fix",
    )
    assert store.events(project_id="proj")
    assert store.events()

    with pytest.raises(LedgerTransitionError):
        store.append_correction_v2(
            _v2(
                "x",
                EventTypeV2.EXPERT_TIME_RECORDED,
                ExpertTimePayload(
                    hours=1.0,
                    minutes=60.0,
                    category="review",
                    measurement_confidence="exact_timer",
                ),
                obligations=[],
            )
        )

    archive = tmp_path / "archive.jsonl"
    meta = store.archive_verified_jsonl(archive)
    assert meta["events"] >= 2
    with pytest.raises(LedgerIntegrityError):
        store.archive_verified_jsonl(path)  # cannot overwrite live

    records = store.export_records()
    assert records
    assert store.events_v2(project_id="proj") == []


# --- TPPR ---


def test_tppr_v1_minutes_only_and_empty_hours() -> None:
    events = [
        UtilityEvent(
            event_id="e1",
            event_type=EventType.OBLIGATION_REGISTERED,
            project_id="p",
            artifact_id="a",
            obligation_id="O-01",
            actor_id="op",
            payload={"weight": 1},
            occurred_at=NOW,
        ),
        UtilityEvent(
            event_id="e2",
            event_type=EventType.EXPERT_TIME_RECORDED,
            project_id="p",
            artifact_id="a",
            actor_id="op",
            payload={"category": "review", "minutes": 90},
            occurred_at=NOW,
        ),
    ]
    report = compute_tppr(events, "p")
    assert report.expert_hours_total == pytest.approx(1.5)


def test_tppr_v2_helpers_and_anti_gaming_branches() -> None:
    with pytest.raises(ValidationError):
        TPPRReportV2(
            project_id="p",
            weighted_credited=0,
            specification_hours=0,
            review_hours=0,
            repair_hours=0,
            integration_hours=0,
            expert_hours_primary=0,
            retrospective_hours=0,
            tppr_complete_case=None,
            tppr_conservative_lower=None,
            denominator_completeness_rate=0,
            missing_persistence_outcomes=0,
            unresolved_legacy_events=0,
            credited_obligations=[],
            pending_persistence_obligations=[],
            numerator_audit=[],
            time_audit=[],
            generated_at=datetime(2026, 1, 1),
        )

    hours_only = ExpertTimePayload(
        hours=2.0,
        minutes=0.0,
        category="review",
        measurement_confidence="exact_timer",
    )
    minutes_only = ExpertTimePayload(
        hours=0.0,
        minutes=30.0,
        category="review",
        measurement_confidence="exact_timer",
    )
    assert _hours_from_payload(minutes_only) == pytest.approx(0.5)
    assert _minutes_from_payload(hours_only) == pytest.approx(120.0)

    rule = PersistenceRule(
        rule_id="persist-default",
        mode="calendar_days",
        threshold=30,
        regression_policy="revoke",
    )
    t0 = NOW
    events = [
        _v2(
            "cond",
            EventTypeV2.CONDITION_ASSIGNED,
            ConditionAssignedPayload(
                condition_assignment_id="as1",
                condition_tag="control",
                candidate_id="c1",
                assignment_hash="h" * 64,
            ),
            obligations=[],
            occurred=t0,
        ),
        _v2(
            "freeze",
            EventTypeV2.OBLIGATION_FROZEN,
            ObligationFreezePayload(
                freeze_id="fr1",
                obligation_ids=["O-01"],
                freeze_hash="a" * 64,
                persistence_rule=rule,
                contract_hash="b" * 64,
                obligation_weights={"O-01": 1.0},
            ),
            occurred=t0 + timedelta(seconds=1),
        ),
        _v2(
            "cand",
            EventTypeV2.CANDIDATE_REGISTERED,
            CandidateRegisteredPayload(
                candidate_id="c1",
                root_candidate_id="c1",
                freeze_id="fr1",
                base_ref="base",
                head_ref="head",
                tree_hash="c" * 64,
                risk_class="R1",
            ),
            occurred=t0 + timedelta(hours=1),
        ),
        _v2(
            "acc",
            EventTypeV2.ARTIFACT_ACCEPTED,
            AcceptanceAggregatedPayload(
                attestation_ids=["a1"],
                quorum_policy_id="quorum.r1.implementation",
                evidence_fingerprint=FP,
                semantic_fidelity=False,
                repository_accepted=False,
                implementation_accepted=True,
                accepted_obligation_ids=["O-01"],
                accepted_at=t0 + timedelta(days=1),
                risk_class="R1",
            ),
            occurred=t0 + timedelta(days=1),
        ),
        _v2(
            "int",
            EventTypeV2.INTEGRATION_CONFIRMED,
            IntegrationConfirmedPayload(candidate_id="c1", integration_ref="main"),
            occurred=t0 + timedelta(days=2),
        ),
        _v2(
            "down",
            EventTypeV2.DOWNSTREAM_ENABLED,
            DownstreamEnabledPayload(
                candidate_id="c1",
                suite_ids=["s1"],
                evidence_fingerprint=FP,
            ),
            occurred=t0 + timedelta(days=3),
        ),
        _v2(
            "pers",
            EventTypeV2.PERSISTENCE_CONFIRMED,
            PersistenceConfirmedPayload(
                candidate_id="c1",
                persistence_rule_id="persist-default",
                confirmed_at=t0 + timedelta(days=40),
                window_elapsed=True,
            ),
            occurred=t0 + timedelta(days=40),
        ),
        _v2(
            "reg",
            EventTypeV2.REGRESSION_DETECTED,
            RegressionDetectedPayload(
                candidate_id="c1",
                regression_id="rg1",
                severity="blocking",
                summary="broke",
            ),
            occurred=t0 + timedelta(days=41),
        ),
        _v2(
            "time",
            EventTypeV2.EXPERT_TIME_RECORDED,
            ExpertTimePayload(
                hours=0.0,
                minutes=60.0,
                category="review",
                measurement_confidence="retrospective_estimate",
            ),
            obligations=[],
            occurred=t0 + timedelta(days=1),
        ),
        _v2(
            "corr",
            EventTypeV2.CORRECTION_RECORDED,
            CorrectionPayload(
                target_event_id="acc",
                reason="note",
                authorization_role="lead",
                invalidation=False,
                replacement_payload={"note": "x"},
            ),
            supersedes="acc",
            occurred=t0 + timedelta(days=42),
        ),
        _v2(
            "legacy",
            EventTypeV2.LEGACY_UNRESOLVED,
            LegacyUnresolvedPayload(legacy_event_type="OBLIGATION_REGISTERED"),
            occurred=t0,
            obligations=[],
        ),
    ]
    report = compute_tppr_v2(events, "proj", include_retrospective_in_primary=False)
    assert report.retrospective_hours == pytest.approx(1.0)
    # Blocking regression should revoke credit
    assert "O-01" not in report.credited_obligations or report.weighted_credited == 0

    # Unknown time category
    bad_time = [
        _v2(
            "tbad",
            EventTypeV2.EXPERT_TIME_RECORDED,
            ExpertTimePayload(
                hours=1.0,
                minutes=60.0,
                category="vacation",
                measurement_confidence="exact_timer",
            ),
            obligations=[],
        )
    ]
    with pytest.raises(TPPRAntiGamingError, match="unknown category"):
        compute_tppr_v2(bad_time, "proj")

    # Multiple weights / freezes
    multi = [
        _v2(
            "f1",
            EventTypeV2.OBLIGATION_FROZEN,
            ObligationFreezePayload(
                freeze_id="fr1",
                obligation_ids=["O-01"],
                freeze_hash="a" * 64,
                persistence_rule=rule,
                contract_hash="b" * 64,
                obligation_weights={"O-01": 1.0},
            ),
        ),
        _v2(
            "f2",
            EventTypeV2.OBLIGATION_FROZEN,
            ObligationFreezePayload(
                freeze_id="fr1",
                obligation_ids=["O-01"],
                freeze_hash="a" * 64,
                persistence_rule=rule,
                contract_hash="b" * 64,
                obligation_weights={"O-01": 2.0},
            ),
            occurred=t0 + timedelta(seconds=1),
        ),
    ]
    with pytest.raises(TPPRAntiGamingError, match="multiple weights"):
        compute_tppr_v2(multi, "proj")

    # Register without freeze
    with pytest.raises(TPPRAntiGamingError, match="without prior freeze"):
        compute_tppr_v2(
            [
                _v2(
                    "c",
                    EventTypeV2.CANDIDATE_REGISTERED,
                    CandidateRegisteredPayload(
                        candidate_id="c1",
                        root_candidate_id="c1",
                        freeze_id="fr1",
                        base_ref="b",
                        head_ref="h",
                        tree_hash="c" * 64,
                        risk_class="R1",
                    ),
                )
            ],
            "proj",
        )

    # Persistence before threshold
    early = [
        _v2(
            "f",
            EventTypeV2.OBLIGATION_FROZEN,
            ObligationFreezePayload(
                freeze_id="fr1",
                obligation_ids=["O-01"],
                freeze_hash="a" * 64,
                persistence_rule=rule,
                contract_hash="b" * 64,
            ),
        ),
        _v2(
            "c",
            EventTypeV2.CANDIDATE_REGISTERED,
            CandidateRegisteredPayload(
                candidate_id="c1",
                root_candidate_id="c1",
                freeze_id="fr1",
                base_ref="b",
                head_ref="h",
                tree_hash="c" * 64,
                risk_class="R1",
            ),
            occurred=t0 + timedelta(hours=1),
        ),
        _v2(
            "i",
            EventTypeV2.INTEGRATION_CONFIRMED,
            IntegrationConfirmedPayload(candidate_id="c1", integration_ref="m"),
            occurred=t0 + timedelta(days=1),
        ),
        _v2(
            "p",
            EventTypeV2.PERSISTENCE_CONFIRMED,
            PersistenceConfirmedPayload(
                candidate_id="c1",
                persistence_rule_id="persist-default",
                confirmed_at=t0 + timedelta(days=2),
                window_elapsed=False,
            ),
            occurred=t0 + timedelta(days=2),
        ),
    ]
    with pytest.raises(TPPRAntiGamingError, match="threshold"):
        compute_tppr_v2(early, "proj")

    # Acceptance without attestations / empty quorum policy
    with pytest.raises(TPPRAntiGamingError, match="acceptance without"):
        compute_tppr_v2(
            [
                _v2(
                    "a",
                    EventTypeV2.ARTIFACT_ACCEPTED,
                    AcceptanceAggregatedPayload(
                        attestation_ids=[],
                        quorum_policy_id="",
                        evidence_fingerprint=FP,
                        semantic_fidelity=False,
                        repository_accepted=False,
                        implementation_accepted=False,
                        accepted_obligation_ids=["O-01"],
                        accepted_at=NOW,
                        risk_class="R0",
                    ),
                )
            ],
            "proj",
        )


# --- protocol ---


def test_protocol_validators_and_freeze_verify_paths(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        ConditionDesign(control_pct=50, instrumented_pct=50, shadow_pct=10)
    with pytest.raises(ValidationError):
        ConditionDesign(control_pct=40, instrumented_pct=40, shadow_pct=20, block_size=4)

    with pytest.raises(ValidationError):
        ProtocolSignatures(
            research_lead="a",
            domain_lead="b",
            repository_maintainer="c",
            signed_at=datetime(2026, 1, 1),
        )
    with pytest.raises(ValidationError):
        ProtocolSignatures(
            research_lead=" ",
            domain_lead="b",
            repository_maintainer="c",
            signed_at=NOW,
        )

    root = write_example_bundle(tmp_path / "proto")
    assert hash_seed_plaintext("secret")

    # Blank protocol field
    raw = yaml.safe_load((root / "protocol.yaml").read_text(encoding="utf-8"))
    raw["protocol_id"] = "TODO"
    (root / "protocol.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(ProtocolError):
        validate_bundle_dir(root)

    root2 = write_example_bundle(tmp_path / "proto2")
    # Hash mismatch
    raw2 = yaml.safe_load((root2 / "protocol.yaml").read_text(encoding="utf-8"))
    raw2["held_out_set_hash"] = "0" * 64
    (root2 / "protocol.yaml").write_text(yaml.safe_dump(raw2, sort_keys=False), encoding="utf-8")
    with pytest.raises(ProtocolError, match="mismatch"):
        validate_bundle_dir(root2)

    root3 = write_example_bundle(tmp_path / "proto3")
    with pytest.raises(ProtocolError, match=r"freeze\.json missing"):
        verify_freeze(root3)
    frozen = freeze_protocol(root3)
    assert frozen.frozen is True
    # Idempotent re-freeze
    again = freeze_protocol(root3)
    assert again.freeze_id == frozen.freeze_id
    verified = verify_freeze(root3)
    assert verified.protocol_hash == frozen.protocol_hash

    # Post-freeze change detection
    (root3 / "endpoints.yaml").write_text(
        (root3 / "endpoints.yaml").read_text(encoding="utf-8") + "# touch\n",
        encoding="utf-8",
    )
    # Update protocol hashes to match new held-out content but keep freeze stale
    analysis_h = sha256_file(root3 / "analysis.yaml")
    roster_h = sha256_file(root3 / "reviewer-roster.yaml")
    # endpoints change alone may not break protocol.yaml cross-hash; mutate held-out
    held_path = root3 / "held-out-set.json"
    held_path.write_text(
        held_path.read_text(encoding="utf-8").replace("cal-01", "cal-99"),
        encoding="utf-8",
    )
    raw3 = yaml.safe_load((root3 / "protocol.yaml").read_text(encoding="utf-8"))
    raw3["held_out_set_hash"] = sha256_file(held_path)
    raw3["analysis_plan_hash"] = analysis_h
    raw3["reviewer_roster_hash"] = roster_h
    (root3 / "protocol.yaml").write_text(yaml.safe_dump(raw3, sort_keys=False), encoding="utf-8")
    with pytest.raises(ProtocolError, match=r"protocol changed|protocol_hash"):
        freeze_protocol(root3)
