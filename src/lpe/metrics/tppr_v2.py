"""TPPR v2 reducer and audit report (CLOSURE-025).

Credit once when freeze → quorum accept → integration → downstream →
persistence elapsed → no unresolved regression → not credited elsewhere.
Legacy ``compute_tppr`` remains the 0.1 read path until migration is complete.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator

from lpe.ledger.events import (
    AcceptanceAggregatedPayload,
    CandidateRegisteredPayload,
    ConditionAssignedPayload,
    DownstreamEnabledPayload,
    EventTypeV2,
    ExpertTimePayload,
    IntegrationConfirmedPayload,
    ObligationFreezePayload,
    PersistenceConfirmedPayload,
    PersistenceRule,
    RegressionDetectedPayload,
    UtilityEventV2,
)
from lpe.models import StrictModel


class TPPRAntiGamingError(ValueError):
    """Raised when an event sequence would game the TPPR numerator/denominator."""


class MeasurementConfidence(StrEnum):
    EXACT_TIMER = "exact_timer"
    CONTEMPORANEOUS_ENTRY = "contemporaneous_entry"
    RETROSPECTIVE_ESTIMATE = "retrospective_estimate"


PRIMARY_TIME_CATEGORIES = frozenset({"specification", "review", "repair", "integration"})

DEFAULT_PERSISTENCE_RULE = PersistenceRule(
    rule_id="persist-default-calendar-30",
    mode="calendar_days",
    threshold=30,
    required_downstream_suite_ids=[],
    regression_policy="revoke",
)


class NumeratorAuditRow(StrictModel):
    obligation_id: str
    weight: float
    freeze_id: str | None = None
    candidate_id: str | None = None
    quorum: bool = False
    integration: bool = False
    downstream: bool = False
    persistence: bool = False
    credited: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)


class TimeAuditRow(StrictModel):
    event_id: str
    actor_id: str
    candidate_id: str | None
    obligation_ids: list[str]
    category: str
    minutes: float
    hours: float
    condition_tag: str | None
    measurement_confidence: MeasurementConfidence
    included_in_primary: bool


class ConditionCohortTPPR(StrictModel):
    cohort_id: str
    condition_tag: str | None = None
    risk_class: str | None = None
    artifact_type: str | None = None
    reviewer_id: str | None = None
    numerator: float
    denominator_hours: float
    tppr: float | None
    credited_obligations: list[str] = Field(default_factory=list)


class TPPRReportV2(StrictModel):
    """Audit-complete TPPR report (§14). Uses schema 0.3.0 independently of packet 0.2.0."""

    schema_version: Literal["0.3.0"] = "0.3.0"
    project_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evaluator_version: str = "tppr_v2.1"
    weighted_credited: float
    specification_hours: float
    review_hours: float
    repair_hours: float
    integration_hours: float
    expert_hours_primary: float
    retrospective_hours: float
    tppr_complete_case: float | None
    tppr_conservative_lower: float | None
    denominator_completeness_rate: float
    missing_persistence_outcomes: int
    unresolved_legacy_events: int
    credited_obligations: list[str]
    pending_persistence_obligations: list[str]
    numerator_audit: list[NumeratorAuditRow]
    time_audit: list[TimeAuditRow]
    cohorts: list[ConditionCohortTPPR] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    anti_gaming_rejects: list[str] = Field(default_factory=list)

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return value


def _hours_from_payload(payload: ExpertTimePayload) -> float:
    if payload.hours > 0:
        return float(payload.hours)
    return float(payload.minutes) / 60.0


def _minutes_from_payload(payload: ExpertTimePayload) -> float:
    if payload.minutes > 0:
        return float(payload.minutes)
    return float(payload.hours) * 60.0


class _ObligationState:
    __slots__ = (
        "accepted",
        "candidate_id",
        "condition_tag",
        "credited_elsewhere",
        "downstream",
        "downstream_suites",
        "freeze_at",
        "freeze_event_id",
        "freeze_id",
        "integration",
        "persistence",
        "persistence_at",
        "persistence_rule",
        "quorum_ok",
        "registered_at",
        "regression_blocking",
        "risk_class",
        "root_candidate_id",
        "weight",
        "weights_seen",
    )

    def __init__(self) -> None:
        self.weight: float | None = None
        self.freeze_id: str | None = None
        self.freeze_event_id: str | None = None
        self.freeze_at: datetime | None = None
        self.persistence_rule: PersistenceRule | None = None
        self.candidate_id: str | None = None
        self.root_candidate_id: str | None = None
        self.risk_class: str | None = None
        self.registered_at: datetime | None = None
        self.accepted: bool = False
        self.quorum_ok: bool = False
        self.integration: bool = False
        self.downstream: bool = False
        self.downstream_suites: set[str] = set()
        self.persistence: bool = False
        self.persistence_at: datetime | None = None
        self.regression_blocking: bool = False
        self.credited_elsewhere: bool = False
        self.condition_tag: str | None = None
        self.weights_seen: set[float] = set()


def compute_tppr_v2(
    events: list[UtilityEventV2],
    project_id: str,
    *,
    include_retrospective_in_primary: bool = False,
    as_of: datetime | None = None,
) -> TPPRReportV2:
    """Compute TPPR v2 with full numerator/denominator audit tables.

    Raises ``TPPRAntiGamingError`` for hard anti-gaming violations that must
    fail closed (duplicate credit attempt, persistence before integration, etc.).
    Soft exclusions (unknown category, anonymous actor) are listed in the report.
    """
    as_of = as_of or datetime.now(UTC)
    relevant = [e for e in events if e.project_id == project_id]
    states: dict[str, _ObligationState] = defaultdict(_ObligationState)
    anti_gaming: list[str] = []
    exclusions: list[str] = []
    time_audit: list[TimeAuditRow] = []
    hours = {
        "specification": 0.0,
        "review": 0.0,
        "repair": 0.0,
        "integration": 0.0,
    }
    retrospective_hours = 0.0
    known_time_events = 0
    complete_time_events = 0
    unresolved_legacy = 0
    credited_lineages: dict[str, str] = {}  # root_candidate_id -> obligation

    # Condition assignment map candidate -> tag
    condition_by_candidate: dict[str, str] = {}

    for event in relevant:
        if event.event_type is EventTypeV2.LEGACY_UNRESOLVED:
            unresolved_legacy += 1
            exclusions.append(f"legacy unresolved {event.event_id}")
            continue

        if event.actor_id.strip().lower() in {"", "anonymous", "unknown"}:
            anti_gaming.append(f"anonymous actor in {event.event_id}")
            raise TPPRAntiGamingError(f"anonymous actors are rejected ({event.event_id})")

        if event.event_type is EventTypeV2.CONDITION_ASSIGNED:
            payload = event.payload
            if not isinstance(payload, ConditionAssignedPayload):
                raise TPPRAntiGamingError(f"CONDITION_ASSIGNED payload mismatch ({event.event_id})")
            condition_by_candidate[payload.candidate_id] = payload.condition_tag
            continue

        if event.event_type is EventTypeV2.OBLIGATION_FROZEN:
            payload = event.payload
            assert isinstance(payload, ObligationFreezePayload)
            for oid in payload.obligation_ids:
                st = states[oid]
                weight = float(payload.obligation_weights.get(oid, 1.0))
                if st.weight is None:
                    st.weight = weight
                    st.weights_seen.add(weight)
                elif weight != st.weight:
                    raise TPPRAntiGamingError(f"multiple weights for freeze of obligation {oid}")
                elif st.freeze_id is not None and st.freeze_id != payload.freeze_id:
                    raise TPPRAntiGamingError(f"multiple freezes for obligation {oid}")
                st.freeze_id = payload.freeze_id
                st.freeze_event_id = event.event_id
                st.freeze_at = event.occurred_at
                st.persistence_rule = payload.persistence_rule
            continue

        if event.event_type is EventTypeV2.CANDIDATE_REGISTERED:
            payload = event.payload
            assert isinstance(payload, CandidateRegisteredPayload)
            for oid in event.obligation_ids or []:
                st = states[oid]
                if st.freeze_at is None or st.freeze_id is None:
                    raise TPPRAntiGamingError(
                        f"obligation {oid} registered without prior freeze "
                        f"(candidate {payload.candidate_id})"
                    )
                if event.occurred_at < st.freeze_at:
                    raise TPPRAntiGamingError(
                        f"candidate registered before obligation freeze for {oid}"
                    )
                st.candidate_id = payload.candidate_id
                st.root_candidate_id = payload.root_candidate_id
                st.risk_class = payload.risk_class
                st.registered_at = event.occurred_at
                st.condition_tag = condition_by_candidate.get(payload.candidate_id)
            continue

        if event.event_type is EventTypeV2.ARTIFACT_ACCEPTED:
            payload = event.payload
            assert isinstance(payload, AcceptanceAggregatedPayload)
            if not (
                payload.semantic_fidelity
                or payload.repository_accepted
                or payload.implementation_accepted
                or payload.quorum_policy_id.startswith("quorum.r0")
            ):
                # R0 may accept with empty attestation list when policy allows.
                if not payload.quorum_policy_id:
                    raise TPPRAntiGamingError(
                        f"acceptance without required attestations ({event.event_id})"
                    )
            for oid in payload.accepted_obligation_ids or event.obligation_ids:
                st = states[oid]
                st.accepted = True
                st.quorum_ok = True
            continue

        if event.event_type is EventTypeV2.INTEGRATION_CONFIRMED:
            payload = event.payload
            assert isinstance(payload, IntegrationConfirmedPayload)
            for oid in event.obligation_ids:
                st = states[oid]
                if st.candidate_id and st.candidate_id != payload.candidate_id:
                    # Allow if root matches
                    if st.root_candidate_id != payload.candidate_id:
                        continue
                st.integration = True
            continue

        if event.event_type is EventTypeV2.DOWNSTREAM_ENABLED:
            payload = event.payload
            assert isinstance(payload, DownstreamEnabledPayload)
            for oid in event.obligation_ids:
                st = states[oid]
                st.downstream = True
                st.downstream_suites.update(payload.suite_ids)
            continue

        if event.event_type is EventTypeV2.PERSISTENCE_CONFIRMED:
            payload = event.payload
            assert isinstance(payload, PersistenceConfirmedPayload)
            for oid in event.obligation_ids:
                st = states[oid]
                if not st.integration:
                    raise TPPRAntiGamingError(f"persistence before integration for {oid}")
                rule = st.persistence_rule or DEFAULT_PERSISTENCE_RULE
                if rule.mode == "calendar_days" and st.freeze_at is not None:
                    threshold = int(rule.threshold)
                    elapsed_days = (payload.confirmed_at - st.freeze_at).days
                    # Prefer integration→persistence window when available.
                    if st.registered_at is not None:
                        elapsed_days = max(
                            elapsed_days,
                            (payload.confirmed_at - st.registered_at).days,
                        )
                    if not payload.window_elapsed and elapsed_days < threshold:
                        raise TPPRAntiGamingError(f"persistence before rule threshold for {oid}")
                st.persistence = True
                st.persistence_at = payload.confirmed_at
            continue

        if event.event_type is EventTypeV2.REGRESSION_DETECTED:
            payload = event.payload
            assert isinstance(payload, RegressionDetectedPayload)
            for oid in event.obligation_ids:
                st = states[oid]
                rule = st.persistence_rule or DEFAULT_PERSISTENCE_RULE
                if payload.severity == "blocking" and rule.regression_policy == "revoke":
                    st.regression_blocking = True
                    st.persistence = False
            continue

        if event.event_type is EventTypeV2.EXPERT_TIME_RECORDED:
            payload = event.payload
            assert isinstance(payload, ExpertTimePayload)
            known_time_events += 1
            category = payload.category.strip().lower()
            if category not in PRIMARY_TIME_CATEGORIES:
                exclusions.append(f"unknown expert time category in {event.event_id}: {category}")
                raise TPPRAntiGamingError(f"time with unknown category rejected ({event.event_id})")
            hours_val = _hours_from_payload(payload)
            minutes_val = _minutes_from_payload(payload)
            conf = MeasurementConfidence(payload.measurement_confidence)
            is_retro = conf is MeasurementConfidence.RETROSPECTIVE_ESTIMATE
            include = (not is_retro) or include_retrospective_in_primary
            if include:
                hours[category] += hours_val
                complete_time_events += 1
            else:
                retrospective_hours += hours_val
            cand = None
            if isinstance(event.payload, ExpertTimePayload):
                # candidate may be artifact_id by convention
                cand = event.artifact_id if event.artifact_id != project_id else None
            time_audit.append(
                TimeAuditRow(
                    event_id=event.event_id,
                    actor_id=event.actor_id,
                    candidate_id=cand,
                    obligation_ids=list(event.obligation_ids),
                    category=category,
                    minutes=minutes_val,
                    hours=hours_val,
                    condition_tag=payload.condition_tag or condition_by_candidate.get(cand or ""),
                    measurement_confidence=conf,
                    included_in_primary=include,
                )
            )
            continue

        if event.event_type is EventTypeV2.CORRECTION_RECORDED:
            exclusions.append(
                f"correction {event.event_id} recorded for {event.supersedes_event_id or 'unknown'}"
            )
            continue

    # Credit assignment
    numerator_audit: list[NumeratorAuditRow] = []
    credited: list[str] = []
    pending: list[str] = []
    weighted = 0.0

    for oid, st in sorted(states.items()):
        reasons: list[str] = []
        if st.weight is None:
            reasons.append("no freeze weight")
            weight = 0.0
        else:
            weight = st.weight
        if st.freeze_id is None:
            reasons.append("not frozen")
        if not st.quorum_ok:
            reasons.append("quorum not satisfied")
        if not st.integration:
            reasons.append("integration missing")
        if not st.downstream:
            reasons.append("downstream missing")
        else:
            rule = st.persistence_rule or DEFAULT_PERSISTENCE_RULE
            required = set(rule.required_downstream_suite_ids)
            if required and not required.issubset(st.downstream_suites):
                reasons.append("required downstream suites incomplete")
                st.downstream = False
        if not st.persistence:
            reasons.append("persistence missing")
        if st.regression_blocking:
            reasons.append("unresolved blocking regression")
        if st.root_candidate_id and st.root_candidate_id in credited_lineages:
            other = credited_lineages[st.root_candidate_id]
            if other != oid:
                reasons.append(f"credited elsewhere under {other}")
                st.credited_elsewhere = True

        ok = (
            weight > 0
            and st.freeze_id is not None
            and st.quorum_ok
            and st.integration
            and st.downstream
            and st.persistence
            and not st.regression_blocking
            and not st.credited_elsewhere
        )
        if ok:
            if st.root_candidate_id:
                if st.root_candidate_id in credited_lineages:
                    raise TPPRAntiGamingError(
                        f"duplicate credit for lineage {st.root_candidate_id}"
                    )
                credited_lineages[st.root_candidate_id] = oid
            credited.append(oid)
            weighted += weight
        elif st.accepted and not st.persistence:
            pending.append(oid)

        numerator_audit.append(
            NumeratorAuditRow(
                obligation_id=oid,
                weight=weight,
                freeze_id=st.freeze_id,
                candidate_id=st.candidate_id,
                quorum=st.quorum_ok,
                integration=st.integration,
                downstream=st.downstream,
                persistence=st.persistence,
                credited=ok,
                blocking_reasons=reasons,
            )
        )

    expert_primary = sum(hours.values())
    complete_case = weighted / expert_primary if expert_primary > 0 else None

    # Conservative lower: unresolved accepted work as zero credit (already),
    # include known primary time only.
    missing_persistence = len(pending)
    conservative_num = weighted  # pending already excluded
    conservative = conservative_num / expert_primary if expert_primary > 0 else None

    denom_completeness = complete_time_events / known_time_events if known_time_events else 1.0

    cohorts = _build_cohorts(states, credited, hours, condition_by_candidate)

    return TPPRReportV2(
        project_id=project_id,
        generated_at=as_of,
        weighted_credited=weighted,
        specification_hours=hours["specification"],
        review_hours=hours["review"],
        repair_hours=hours["repair"],
        integration_hours=hours["integration"],
        expert_hours_primary=expert_primary,
        retrospective_hours=retrospective_hours,
        tppr_complete_case=complete_case,
        tppr_conservative_lower=conservative,
        denominator_completeness_rate=denom_completeness,
        missing_persistence_outcomes=missing_persistence,
        unresolved_legacy_events=unresolved_legacy,
        credited_obligations=credited,
        pending_persistence_obligations=pending,
        numerator_audit=numerator_audit,
        time_audit=time_audit,
        cohorts=cohorts,
        exclusions=exclusions,
        anti_gaming_rejects=anti_gaming,
    )


def _build_cohorts(
    states: dict[str, _ObligationState],
    credited: list[str],
    hours: dict[str, float],
    condition_by_candidate: dict[str, str],
) -> list[ConditionCohortTPPR]:
    """Build overall + condition cohorts (risk/artifact/reviewer when available)."""
    overall_num = sum((states[o].weight or 0.0) for o in credited if states[o].weight is not None)
    denom = sum(hours.values())
    cohorts = [
        ConditionCohortTPPR(
            cohort_id="overall",
            numerator=overall_num,
            denominator_hours=denom,
            tppr=overall_num / denom if denom > 0 else None,
            credited_obligations=list(credited),
        )
    ]
    by_condition: dict[str, list[str]] = defaultdict(list)
    for oid in credited:
        tag = states[oid].condition_tag
        if tag is None and states[oid].candidate_id:
            tag = condition_by_candidate.get(states[oid].candidate_id or "")
        by_condition[tag or "unspecified"].append(oid)
    for tag, oids in sorted(by_condition.items()):
        num = sum((states[o].weight or 0.0) for o in oids)
        cohorts.append(
            ConditionCohortTPPR(
                cohort_id=f"condition:{tag}",
                condition_tag=tag,
                numerator=num,
                denominator_hours=denom,  # shared until per-condition time exists
                tppr=num / denom if denom > 0 else None,
                credited_obligations=oids,
            )
        )
    by_risk: dict[str, list[str]] = defaultdict(list)
    for oid in credited:
        rc = states[oid].risk_class or "unknown"
        by_risk[rc].append(oid)
    for rc, oids in sorted(by_risk.items()):
        num = sum((states[o].weight or 0.0) for o in oids)
        cohorts.append(
            ConditionCohortTPPR(
                cohort_id=f"risk:{rc}",
                risk_class=rc,
                numerator=num,
                denominator_hours=denom,
                tppr=num / denom if denom > 0 else None,
                credited_obligations=oids,
            )
        )
    return cohorts


def events_from_legacy_dicts(
    raw_events: list[dict[str, Any]],
) -> list[UtilityEventV2]:
    """Best-effort adapter for tests; prefer typed UtilityEventV2 inputs."""
    return [UtilityEventV2.model_validate(item) for item in raw_events]
