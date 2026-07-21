"""Pilot descriptive analysis and agreement statistics (CLOSURE-030)."""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from lpe.hashing import sha256_value
from lpe.models import StrictModel


class AnalysisError(ValueError):
    """Raised when analysis inputs are incomplete (fail closed)."""


class ConditionDescriptiveStats(StrictModel):
    condition_tag: str
    count: int
    risk_distribution: dict[str, int]
    artifact_type_distribution: dict[str, int]
    reviewer_distribution: dict[str, int]
    median_review_minutes: float | None
    iqr_review_minutes: tuple[float, float] | None
    acceptance_rate: float | None
    repair_rate: float | None
    rejection_rate: float | None
    indeterminate_rate: float | None
    automation_rate: float | None
    reproduction_rate: float | None
    l2_l3_recovery_rate: float | None
    tppr: float | None
    tppr_lower: float | None
    tppr_upper: float | None


class AgreementReport(StrictModel):
    method: str
    value: float | None
    n_pairs: int
    ci_low: float | None = None
    ci_high: float | None = None
    notes: str | None = None


class PilotEpisodeRecord(StrictModel):
    episode_id: str
    condition_tag: str
    risk_class: str
    artifact_type: str
    reviewer_id: str
    review_minutes: float
    repair_minutes: float = 0.0
    outcome: Literal["accept", "repair", "reject", "indeterminate"]
    automated_packet: bool = False
    exact_environment_reproduction: bool = False
    l2_l3_recovered_before_integration: bool | None = None
    integrated_l3_defect: bool = False
    weighted_accepted_obligations: float = 0.0
    instrumentation_overhead_pct: float | None = None
    primary_label: str | None = None
    peer_label: str | None = None


class PilotAnalysisReport(StrictModel):
    schema_version: Literal["0.3.0"] = "0.3.0"
    protocol_id: str
    data_lock_hash: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    by_condition: list[ConditionDescriptiveStats]
    agreement: list[AgreementReport]
    analysis_hash: str
    blocking_reasons: list[str] = Field(default_factory=list)

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return value


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _iqr(values: Sequence[float]) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    ordered = sorted(values)
    n = len(ordered)
    q1 = ordered[n // 4]
    q3 = ordered[(3 * n) // 4]
    return (float(q1), float(q3))


def _rate(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return num / den


def cohen_kappa(labels_a: Sequence[str], labels_b: Sequence[str]) -> float | None:
    """Cohen's kappa for two raters with nominal labels."""
    if len(labels_a) != len(labels_b) or not labels_a:
        return None
    n = len(labels_a)
    agree = sum(1 for a, b in zip(labels_a, labels_b, strict=True) if a == b)
    po = agree / n
    cats = sorted(set(labels_a) | set(labels_b))
    pe = 0.0
    for cat in cats:
        pa = sum(1 for x in labels_a if x == cat) / n
        pb = sum(1 for x in labels_b if x == cat) / n
        pe += pa * pb
    if math.isclose(1.0 - pe, 0.0):
        return 1.0 if math.isclose(po, 1.0) else 0.0
    return (po - pe) / (1.0 - pe)


def fleiss_kappa(ratings: Sequence[Sequence[str]]) -> float | None:
    """Fleiss' kappa for N items rated by a fixed number of raters."""
    if not ratings:
        return None
    n_raters = len(ratings[0])
    if n_raters < 2 or any(len(r) != n_raters for r in ratings):
        return None
    categories = sorted({label for row in ratings for label in row})
    n_items = len(ratings)
    n_cats = len(categories)
    if n_cats == 0:
        return None
    # Count matrix
    counts: list[list[int]] = []
    for row in ratings:
        c = Counter(row)
        counts.append([c.get(cat, 0) for cat in categories])
    p = 0.0
    for row_counts in counts:
        s = sum(v * v for v in row_counts)
        p += (s - n_raters) / (n_raters * (n_raters - 1))
    p /= n_items
    pj = [sum(row_counts[j] for row_counts in counts) / (n_items * n_raters) for j in range(n_cats)]
    pe = sum(x * x for x in pj)
    if math.isclose(1.0 - pe, 0.0):
        return 1.0 if math.isclose(p, 1.0) else 0.0
    return (p - pe) / (1.0 - pe)


def gwet_ac1(labels_a: Sequence[str], labels_b: Sequence[str]) -> float | None:
    """Gwet's AC1 (prevalence-robust agreement)."""
    if len(labels_a) != len(labels_b) or not labels_a:
        return None
    n = len(labels_a)
    po = sum(1 for a, b in zip(labels_a, labels_b, strict=True) if a == b) / n
    cats = sorted(set(labels_a) | set(labels_b))
    q = len(cats)
    if q == 0:
        return None
    pi = []
    for cat in cats:
        pi.append(
            (sum(1 for x in labels_a if x == cat) + sum(1 for x in labels_b if x == cat)) / (2 * n)
        )
    pe = (1.0 / (q * (q - 1))) * sum(p * (1 - p) for p in pi) * (q - 1) if q > 1 else 0.0
    # Standard Gwet AC1: pe = sum(pi*(1-pi))/(q-1)
    pe = sum(p * (1 - p) for p in pi) / (q - 1) if q > 1 else 0.0
    if math.isclose(1.0 - pe, 0.0):
        return 1.0 if math.isclose(po, 1.0) else 0.0
    return (po - pe) / (1.0 - pe)


def bootstrap_ci(
    values: Sequence[float],
    *,
    iterations: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    rng = random.Random(seed)
    n = len(values)
    samples: list[float] = []
    for _ in range(iterations):
        draw = [values[rng.randrange(n)] for _ in range(n)]
        samples.append(sum(draw) / n)
    samples.sort()
    lo = samples[int((alpha / 2) * iterations)]
    hi = samples[int((1 - alpha / 2) * iterations) - 1]
    return float(lo), float(hi)


def analyze_pilot(
    *,
    protocol_id: str,
    data_lock_hash: str,
    episodes: list[PilotEpisodeRecord],
    bootstrap_iterations: int = 2000,
) -> PilotAnalysisReport:
    if not episodes:
        raise AnalysisError("no episodes to analyze")
    if not data_lock_hash.strip():
        raise AnalysisError("data_lock_hash required")

    by_cond: dict[str, list[PilotEpisodeRecord]] = defaultdict(list)
    for ep in episodes:
        by_cond[ep.condition_tag].append(ep)

    stats: list[ConditionDescriptiveStats] = []
    for tag, rows in sorted(by_cond.items()):
        minutes = [r.review_minutes for r in rows]
        outcomes = Counter(r.outcome for r in rows)
        n = len(rows)
        auto = sum(1 for r in rows if r.automated_packet)
        repro = sum(1 for r in rows if r.exact_environment_reproduction)
        recovered = [r for r in rows if r.l2_l3_recovered_before_integration is not None]
        rec_ok = sum(1 for r in recovered if r.l2_l3_recovered_before_integration)
        weighted = sum(r.weighted_accepted_obligations for r in rows)
        hours = sum(r.review_minutes + r.repair_minutes for r in rows) / 60.0
        tppr = weighted / hours if hours > 0 else None
        tppr_vals = []
        for r in rows:
            h = (r.review_minutes + r.repair_minutes) / 60.0
            if h > 0:
                tppr_vals.append(r.weighted_accepted_obligations / h)
        lo, hi = bootstrap_ci(tppr_vals, iterations=bootstrap_iterations, seed=21)
        stats.append(
            ConditionDescriptiveStats(
                condition_tag=tag,
                count=n,
                risk_distribution=dict(Counter(r.risk_class for r in rows)),
                artifact_type_distribution=dict(Counter(r.artifact_type for r in rows)),
                reviewer_distribution=dict(Counter(r.reviewer_id for r in rows)),
                median_review_minutes=_median(minutes),
                iqr_review_minutes=_iqr(minutes),
                acceptance_rate=_rate(outcomes.get("accept", 0), n),
                repair_rate=_rate(outcomes.get("repair", 0), n),
                rejection_rate=_rate(outcomes.get("reject", 0), n),
                indeterminate_rate=_rate(outcomes.get("indeterminate", 0), n),
                automation_rate=_rate(auto, n),
                reproduction_rate=_rate(repro, n),
                l2_l3_recovery_rate=_rate(rec_ok, len(recovered)) if recovered else None,
                tppr=tppr,
                tppr_lower=lo,
                tppr_upper=hi,
            )
        )

    pairs_a = [e.primary_label for e in episodes if e.primary_label and e.peer_label]
    pairs_b = [e.peer_label for e in episodes if e.primary_label and e.peer_label]
    agreement: list[AgreementReport] = []
    if pairs_a and pairs_b:
        ck = cohen_kappa(pairs_a, pairs_b)
        ac1 = gwet_ac1(pairs_a, pairs_b)
        agreement.append(
            AgreementReport(
                method="cohen_kappa",
                value=ck,
                n_pairs=len(pairs_a),
            )
        )
        agreement.append(AgreementReport(method="gwet_ac1", value=ac1, n_pairs=len(pairs_a)))
        # Fleiss with 2 raters degenerates to similar; still report when labels present.
        ratings = list(zip(pairs_a, pairs_b, strict=True))
        fk = fleiss_kappa(ratings)
        agreement.append(AgreementReport(method="fleiss_kappa", value=fk, n_pairs=len(ratings)))

    report = PilotAnalysisReport(
        protocol_id=protocol_id,
        data_lock_hash=data_lock_hash,
        by_condition=stats,
        agreement=agreement,
        analysis_hash="",
    )
    report.analysis_hash = sha256_value(
        report.model_dump(mode="json", exclude={"analysis_hash", "generated_at"})
    )
    return report


def shadow_pilot_gate_inputs_from_analysis(
    report: PilotAnalysisReport,
    *,
    comprehension_pass_rate: float | None,
    median_overhead_pct: float | None,
    p90_overhead_pct: float | None,
    instrumented_vs_control_efficiency_gain: float | None,
    instrumented_l2_l3_sensitivity_delta_pp: float | None,
    instrumented_additional_integrated_l3: int | None,
    sealed_reproducible: bool | None,
) -> dict[str, Any]:
    """Extract the ten §16.3 gate observables (None = missing → fail closed)."""
    by = {s.condition_tag: s for s in report.by_condition}
    overall_n = sum(s.count for s in report.by_condition)
    auto = None
    repro = None
    if overall_n:
        auto_num = 0.0
        repro_num = 0.0
        for s in report.by_condition:
            if s.automation_rate is not None:
                auto_num += s.automation_rate * s.count
            if s.reproduction_rate is not None:
                repro_num += s.reproduction_rate * s.count
        auto = auto_num / overall_n
        repro = repro_num / overall_n

    agreement_values = [a.value for a in report.agreement if a.value is not None]
    best_agreement = max(agreement_values) if agreement_values else None

    return {
        "packet_automation_rate": auto,
        "exact_environment_reproduction": repro,
        "median_instrumentation_overhead": median_overhead_pct,
        "p90_instrumentation_overhead": p90_overhead_pct,
        "comprehension_pass_rate": comprehension_pass_rate,
        "primary_category_agreement": best_agreement,
        "instrumented_efficiency_gain": instrumented_vs_control_efficiency_gain,
        "instrumented_l2_l3_sensitivity_delta_pp": instrumented_l2_l3_sensitivity_delta_pp,
        "instrumented_additional_integrated_l3": instrumented_additional_integrated_l3,
        "sealed_reproducible": sealed_reproducible,
        "has_control": "control" in by,
        "has_instrumented": "instrumented" in by,
    }
