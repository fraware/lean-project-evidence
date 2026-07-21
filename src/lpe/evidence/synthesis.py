"""Versioned synthesis registry for canonical findings (CLOSURE-015).

Canonical checks ``repository.api_fit``, ``downstream.declared_use``, and
``semantic.intent_support`` are derived from provider outputs. Generic UNKNOWN
placeholders must not remain after complete provider results.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from lpe import __version__
from lpe.evidence.payloads import SynthesisFindingPayload
from lpe.hashing import sha256_value
from lpe.models import (
    CandidateDescriptor,
    EvidenceBasis,
    EvidenceCoverage,
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    Provenance,
    RiskClass,
    Severity,
    SubjectReference,
    basis_satisfies,
)

SYNTHESIS_RULES_VERSION = "synthesis.v1"
GATES_POLICY_VERSION = "gates.v1"
RECOMMENDATION_POLICY_ID = f"{GATES_POLICY_VERSION}+{SYNTHESIS_RULES_VERSION}"

# Ordered dependency lists: sources consulted when synthesizing each canonical check.
SYNTHESIS_RULES: dict[str, list[str]] = {
    "repository.api_fit": [
        "semantic.duplicate_retrieval",
        "semantic.statement_diff",
        "repository.changed_paths",
        "lean.impact_cone",
    ],
    "downstream.declared_use": [
        "downstream.successor_suite",
        "downstream.replacement_tests",
    ],
    "semantic.intent_support": [
        "semantic.statement_diff",
        "semantic.project_examples",
        "semantic.counterexamples",
        "semantic.human_attestation",
    ],
}

_CANONICAL_CHECK_IDS = frozenset(SYNTHESIS_RULES)


def recommendation_policy_id() -> str:
    return RECOMMENDATION_POLICY_ID


def _by_check(findings: list[EvidenceFinding]) -> dict[str, list[EvidenceFinding]]:
    grouped: dict[str, list[EvidenceFinding]] = {}
    for finding in findings:
        grouped.setdefault(finding.check_id, []).append(finding)
    return grouped


def _complete_provider_result(findings: list[EvidenceFinding]) -> bool:
    """True when every finding is a terminal non-placeholder status."""
    if not findings:
        return False
    return all(
        f.status
        in {
            FindingStatus.PASS,
            FindingStatus.FAIL,
            FindingStatus.WARN,
            FindingStatus.NOT_APPLICABLE,
        }
        or (
            f.status is FindingStatus.UNKNOWN
            and bool(f.details.get("attempted"))
            and f.coverage is not None
            and f.coverage.complete_for_declared_scope
        )
        for f in findings
    )


def _worst_status(statuses: list[FindingStatus]) -> FindingStatus:
    order = [
        FindingStatus.FAIL,
        FindingStatus.UNKNOWN,
        FindingStatus.WARN,
        FindingStatus.PASS,
        FindingStatus.NOT_APPLICABLE,
    ]
    for status in order:
        if status in statuses:
            return status
    return FindingStatus.UNKNOWN


def _provenance(*, check_id: str, details: dict[str, Any]) -> Provenance:
    now = datetime.now(UTC)
    return Provenance(
        tool="lean-project-evidence",
        tool_version=__version__,
        command=[],
        input_hash=sha256_value({"check_id": check_id, "details": details}),
        output_hash=None,
        started_at=now,
        finished_at=now,
        elapsed_ms=0,
        producer_id="evidence.synthesis",
        producer_version=SYNTHESIS_RULES_VERSION,
    )


def _synth_finding(
    *,
    check_id: str,
    dimension: EvidenceDimension,
    status: FindingStatus,
    severity: Severity,
    summary: str,
    details: dict[str, Any],
    basis: EvidenceBasis,
    coverage: EvidenceCoverage,
    subject_refs: list[SubjectReference] | None = None,
    required_basis: EvidenceBasis | None = None,
) -> EvidenceFinding:
    synth_ver = SYNTHESIS_RULES_VERSION.replace(".", "_")
    finding_id = f"finding_{check_id.replace('.', '_')}_synth_{synth_ver}"
    source_check_ids = list(SYNTHESIS_RULES.get(check_id, []))
    typed_payload = SynthesisFindingPayload(
        synthesis_rule=str(details.get("synthesis_rule") or check_id),
        source_check_ids=source_check_ids,
        notes=[str(details["note"])] if details.get("note") else [],
        details=dict(details),
    )
    return EvidenceFinding(
        finding_id=finding_id,
        check_id=check_id,
        check_version=SYNTHESIS_RULES_VERSION,
        dimension=dimension,
        status=status,
        severity=severity,
        summary=summary,
        details=details,
        provenance=_provenance(check_id=check_id, details=details),
        basis=basis,
        coverage=coverage,
        subject_refs=list(subject_refs or []),
        payload=typed_payload,
        required_basis=required_basis,
    )


def _synthesize_api_fit(
    grouped: dict[str, list[EvidenceFinding]],
    candidate: CandidateDescriptor,
) -> EvidenceFinding | None:
    public = [d.name for d in candidate.changed_declarations if d.public]
    if not public:
        return _synth_finding(
            check_id="repository.api_fit",
            dimension=EvidenceDimension.REPOSITORY,
            status=FindingStatus.NOT_APPLICABLE,
            severity=Severity.INFO,
            summary="No public declaration changes; repository API fit not applicable",
            details={"public_declarations": [], "synthesis_rule": "repository.api_fit"},
            basis=EvidenceBasis.STRUCTURAL_COMPARISON,
            coverage=EvidenceCoverage(
                requested_subject_count=0,
                evaluated_subject_count=0,
                complete_for_declared_scope=True,
            ),
        )

    sources = SYNTHESIS_RULES["repository.api_fit"]
    collected: list[EvidenceFinding] = []
    for check_id in sources:
        collected.extend(grouped.get(check_id, []))

    details: dict[str, Any] = {
        "public_declarations": public,
        "synthesis_rule": "repository.api_fit",
        "source_check_ids": sources,
        "source_statuses": {f.check_id: f.status.value for f in collected},
        "automated_evidence": [
            "public declaration additions/removals",
            "duplicate candidates",
            "statement/structure comparison",
            "impact-cone size",
        ],
        "note": (
            "Automated API evidence only; final R2-R4 repository acceptance remains human-attested"
        ),
    }

    if not collected:
        return _synth_finding(
            check_id="repository.api_fit",
            dimension=EvidenceDimension.REPOSITORY,
            status=FindingStatus.UNKNOWN,
            severity=Severity.L2,
            summary="Repository API fit unresolved: no provider evidence available",
            details=details,
            basis=EvidenceBasis.HEURISTIC_RETRIEVAL,
            coverage=EvidenceCoverage(
                requested_subject_count=len(public),
                evaluated_subject_count=0,
                complete_for_declared_scope=False,
                exclusion_reasons=["no_provider_evidence"],
            ),
        )

    if not _complete_provider_result(collected):
        return _synth_finding(
            check_id="repository.api_fit",
            dimension=EvidenceDimension.REPOSITORY,
            status=FindingStatus.UNKNOWN,
            severity=Severity.L2,
            summary="Repository API fit unresolved: provider evidence incomplete",
            details=details,
            basis=EvidenceBasis.STRUCTURAL_COMPARISON,
            coverage=EvidenceCoverage(
                requested_subject_count=len(public),
                evaluated_subject_count=len(collected),
                complete_for_declared_scope=False,
                exclusion_reasons=["incomplete_provider_evidence"],
            ),
        )

    status = _worst_status([f.status for f in collected])
    if status is FindingStatus.NOT_APPLICABLE:
        status = FindingStatus.PASS
    severity = (
        Severity.L2
        if status in {FindingStatus.FAIL, FindingStatus.WARN, FindingStatus.UNKNOWN}
        else Severity.INFO
    )
    return _synth_finding(
        check_id="repository.api_fit",
        dimension=EvidenceDimension.REPOSITORY,
        status=status,
        severity=severity,
        summary=(
            f"Repository API fit synthesized from {len(collected)} provider finding(s) "
            f"→ {status.value}"
        ),
        details=details,
        basis=EvidenceBasis.STRUCTURAL_COMPARISON,
        coverage=EvidenceCoverage(
            requested_subject_count=len(public),
            evaluated_subject_count=len(collected),
            complete_for_declared_scope=True,
        ),
        subject_refs=[SubjectReference(kind="declaration", ref=n) for n in public],
    )


def _synthesize_declared_use(
    grouped: dict[str, list[EvidenceFinding]],
    candidate: CandidateDescriptor,
) -> EvidenceFinding | None:
    public = [d.name for d in candidate.changed_declarations if d.public]
    sources = SYNTHESIS_RULES["downstream.declared_use"]
    collected: list[EvidenceFinding] = []
    for check_id in sources:
        collected.extend(grouped.get(check_id, []))

    details: dict[str, Any] = {
        "obligation_ids": list(candidate.obligation_ids),
        "synthesis_rule": "downstream.declared_use",
        "source_check_ids": sources,
        "source_statuses": {f.check_id: f.status.value for f in collected},
    }

    if not public:
        return _synth_finding(
            check_id="downstream.declared_use",
            dimension=EvidenceDimension.DOWNSTREAM,
            status=FindingStatus.NOT_APPLICABLE,
            severity=Severity.INFO,
            summary="No public declaration changes; declared downstream use not applicable",
            details=details,
            basis=EvidenceBasis.EXECUTED_TEST,
            coverage=EvidenceCoverage(
                requested_subject_count=0,
                evaluated_subject_count=0,
                complete_for_declared_scope=True,
            ),
        )

    if not collected:
        return _synth_finding(
            check_id="downstream.declared_use",
            dimension=EvidenceDimension.DOWNSTREAM,
            status=FindingStatus.UNKNOWN,
            severity=Severity.L2,
            summary="Declared downstream use unresolved: no successor/replacement evidence",
            details=details,
            basis=EvidenceBasis.EXECUTED_TEST,
            coverage=EvidenceCoverage(
                requested_subject_count=len(candidate.obligation_ids),
                evaluated_subject_count=0,
                complete_for_declared_scope=False,
                exclusion_reasons=["no_downstream_provider_evidence"],
            ),
        )

    if not _complete_provider_result(collected):
        return _synth_finding(
            check_id="downstream.declared_use",
            dimension=EvidenceDimension.DOWNSTREAM,
            status=FindingStatus.UNKNOWN,
            severity=Severity.L2,
            summary="Declared downstream use unresolved: provider evidence incomplete",
            details=details,
            basis=EvidenceBasis.EXECUTED_TEST,
            coverage=EvidenceCoverage(
                requested_subject_count=len(candidate.obligation_ids),
                evaluated_subject_count=len(collected),
                complete_for_declared_scope=False,
                exclusion_reasons=["incomplete_downstream_evidence"],
            ),
        )

    status = _worst_status([f.status for f in collected])
    if status is FindingStatus.NOT_APPLICABLE:
        status = FindingStatus.PASS
    return _synth_finding(
        check_id="downstream.declared_use",
        dimension=EvidenceDimension.DOWNSTREAM,
        status=status,
        severity=Severity.L2 if status is not FindingStatus.PASS else Severity.INFO,
        summary=(
            f"Declared downstream use synthesized from {len(collected)} provider "
            f"finding(s) → {status.value}"
        ),
        details=details,
        basis=EvidenceBasis.EXECUTED_TEST,
        coverage=EvidenceCoverage(
            requested_subject_count=len(candidate.obligation_ids),
            evaluated_subject_count=len(collected),
            complete_for_declared_scope=True,
        ),
    )


def _synthesize_intent_support(
    grouped: dict[str, list[EvidenceFinding]],
    candidate: CandidateDescriptor,
    risk_class: RiskClass,
) -> EvidenceFinding:
    sources = SYNTHESIS_RULES["semantic.intent_support"]
    collected: list[EvidenceFinding] = []
    for check_id in sources:
        collected.extend(grouped.get(check_id, []))

    human = grouped.get("semantic.human_attestation", [])
    human_ok = any(
        f.status is FindingStatus.PASS and f.basis is EvidenceBasis.HUMAN_ATTESTED for f in human
    )

    bundle = {
        "source_intent_reference": candidate.claimed_intent,
        "structural_statement_difference": [
            f.model_dump(mode="json") for f in grouped.get("semantic.statement_diff", [])
        ],
        "project_examples": [f.status.value for f in grouped.get("semantic.project_examples", [])],
        "counterexamples": [f.status.value for f in grouped.get("semantic.counterexamples", [])],
        "terminology_policy": [f.status.value for f in grouped.get("repository.terminology", [])],
        "human_semantic_attestation_status": ("PRESENT" if human_ok else "ABSENT"),
        "synthesis_rule": "semantic.intent_support",
        "source_check_ids": sources,
    }

    required = EvidenceBasis.HUMAN_ATTESTED
    if risk_class in {RiskClass.R3, RiskClass.R4}:
        if human_ok:
            status = FindingStatus.PASS
            basis = EvidenceBasis.HUMAN_ATTESTED
            summary = (
                "Semantic intent support satisfied by HUMAN_ATTESTED evidence "
                f"for {risk_class.value}"
            )
        else:
            status = FindingStatus.UNKNOWN
            basis = EvidenceBasis.STRUCTURAL_COMPARISON
            summary = (
                f"{risk_class.value} semantic fidelity requires HUMAN_ATTESTED; "
                "automated bundle present but not sufficient"
            )
    else:
        # Lower risk: report automated bundle; never claim human intent fidelity.
        auto_statuses = [f.status for f in collected if f.check_id != "semantic.human_attestation"]
        status = _worst_status(auto_statuses) if auto_statuses else FindingStatus.UNKNOWN
        if status is FindingStatus.NOT_APPLICABLE:
            status = FindingStatus.PASS
        basis = EvidenceBasis.STRUCTURAL_COMPARISON
        summary = (
            "Semantic intent support bundle assembled from automated providers; "
            "not a mathematical-intent certificate"
        )
        required = EvidenceBasis.STRUCTURAL_COMPARISON

    # PASS with weaker-than-required basis is refused by the model validator;
    # for R3/R4 without human attestation we emit UNKNOWN instead.
    if status is FindingStatus.PASS and not basis_satisfies(basis, required):
        status = FindingStatus.UNKNOWN
        summary = (
            f"Intent support PASS refused: basis {basis.value} weaker than "
            f"required {required.value}"
        )

    return _synth_finding(
        check_id="semantic.intent_support",
        dimension=EvidenceDimension.SEMANTIC,
        status=status,
        severity=Severity.L3 if status is not FindingStatus.PASS else Severity.INFO,
        summary=summary,
        details=bundle,
        basis=basis,
        coverage=EvidenceCoverage(
            requested_subject_count=len(sources),
            evaluated_subject_count=len(collected),
            complete_for_declared_scope=True,
            allows_partial_pass=False,
        ),
        required_basis=required if risk_class in {RiskClass.R3, RiskClass.R4} else None,
        subject_refs=[
            SubjectReference(kind="obligation", ref=oid) for oid in candidate.obligation_ids
        ],
    )


def apply_synthesis(
    findings: list[EvidenceFinding],
    *,
    candidate: CandidateDescriptor,
    risk_class: RiskClass,
) -> list[EvidenceFinding]:
    """Replace contradictory generic UNKNOWN canonical findings with synthesized ones.

    Provider findings for non-canonical checks are preserved. Existing canonical
    placeholders (``repository.api_fit``, ``downstream.declared_use``) are removed
    and re-emitted from the registry. ``semantic.intent_support`` is always added.
    """
    grouped = _by_check(findings)
    retained = [f for f in findings if f.check_id not in _CANONICAL_CHECK_IDS]

    api_fit = _synthesize_api_fit(grouped, candidate)
    declared = _synthesize_declared_use(grouped, candidate)
    intent = _synthesize_intent_support(grouped, candidate, risk_class)

    synthesized = [f for f in (api_fit, declared, intent) if f is not None]
    return retained + synthesized
