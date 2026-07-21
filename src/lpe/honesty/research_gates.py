"""M6-M7 research gates and §21 evaluator (CLOSURE-030 / CLOSURE-037-038).

Training entrypoints remain blocked until a machine-readable
``Section21GateReport`` sets authorization flags. Evaluators fail closed on
missing data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator

from lpe.hashing import sha256_value
from lpe.models import StrictModel

EVALUATOR_VERSION = "section21.v1"


class ResearchGateBlocked(RuntimeError):
    """Raised when a research / training entrypoint is invoked before §21."""


class GateEvaluation(StrictModel):
    gate_id: str
    description: str
    threshold: str
    observed: float | bool | int | None
    passed: bool
    blocking_reason: str | None = None


class Section21GateReport(StrictModel):
    schema_version: Literal["0.3.0"] = "0.3.0"
    protocol_id: str
    data_lock_hash: str
    gates: list[GateEvaluation]
    shadow_pilot_passed: bool
    learned_routing_authorized: bool
    synthesis_authorized: bool
    blocking_reasons: list[str]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evaluator_version: str = EVALUATOR_VERSION
    report_hash: str = ""

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return value


# Gate matrix printed by ``lpe research status`` and doctor.
RESEARCH_GATE_MATRIX: tuple[dict[str, str], ...] = (
    {
        "id": "EPIC-039",
        "milestone": "M6",
        "title": "Learn review routing",
        "status": "BLOCKED",
        "until": "machine-readable Section21GateReport.learned_routing_authorized=true",
        "shipped": "DeterministicRoutingBaseline scaffold only (no training)",
    },
    {
        "id": "EPIC-040",
        "milestone": "M7",
        "title": "Project-targeted synthesis",
        "status": "BLOCKED",
        "until": "machine-readable Section21GateReport.synthesis_authorized=true",
        "shipped": "SynthesisEvalHarness fixture comparison only (no training)",
    },
    {
        "id": "ADR-0003",
        "milestone": "review",
        "title": "R3/R4 human authority",
        "status": "ACTIVE",
        "until": "quorum path only (no auto-accept)",
        "shipped": "single-reviewer ACCEPT refused; accept-quorum after attestations",
    },
    {
        "id": "SECTION-21",
        "milestone": "science",
        "title": "Shadow-pilot + learned-routing clearance",
        "status": "NOT_PASSED",
        "until": "frozen protocol + data lock + evaluate-gates pass",
        "shipped": "evaluate-gates fail-closed evaluator (CLOSURE-030)",
    },
    {
        "id": "CLOSURE-037",
        "milestone": "post-gate",
        "title": "Learned routing implementation",
        "status": "BLOCKED",
        "until": "learned_routing_authorized=true",
        "shipped": "none (do not implement training)",
    },
    {
        "id": "CLOSURE-038",
        "milestone": "post-gate",
        "title": "Project-targeted synthesis evaluation",
        "status": "BLOCKED",
        "until": "synthesis_authorized=true",
        "shipped": "none (do not implement training)",
    },
)

_BLOCKED_ENTRYPOINTS = frozenset(
    {
        "routing",
        "routing.train",
        "routing.learned",
        "synthesis",
        "synthesis.train",
        "m6",
        "m7",
        "epic-039",
        "epic-040",
        "train",
        "closure-037",
        "closure-038",
    }
)


def refuse_research_entrypoint(name: str) -> None:
    """Exit-path guard for CLI / module callers that imply M6-M7 training."""
    key = name.strip().lower().replace("_", ".").replace(" ", ".")
    aliases = {
        "lpe.routing": "routing",
        "lpe.synthesis": "synthesis",
        "learned_routing": "routing.learned",
        "learn_routing": "routing.learned",
        "research.train": "train",
        "lpe.research.train": "train",
    }
    key = aliases.get(key, key)
    if key in _BLOCKED_ENTRYPOINTS or key.startswith("routing.") or key.startswith("synthesis."):
        epic = "EPIC-039/040"
        if "synthesis" in key or key in {"m7", "epic-040", "closure-038"}:
            epic = "EPIC-040 / CLOSURE-038"
        elif "routing" in key or key in {"m6", "epic-039", "closure-037"}:
            epic = "EPIC-039 / CLOSURE-037"
        raise ResearchGateBlocked(
            f"{epic} blocked until machine-readable §21 authorization. "
            f"Entrypoint {name!r} is not available; training does not exist. "
            "Run `lpe research status` or `lpe research evaluate-gates`. "
            "See docs/NON_CLAIMS.md."
        )


def format_research_status(*, as_markdown: bool = False) -> str:
    """Human-readable research gate matrix."""
    if as_markdown:
        lines = [
            "# Research gate status",
            "",
            "M6-M7 training entrypoints **do not exist**. CLOSURE-037/038 remain "
            "BLOCKED until a Section21GateReport authorizes them.",
            "",
            "| ID | Milestone | Status | Until | Shipped |",
            "| --- | --- | --- | --- | --- |",
        ]
        for row in RESEARCH_GATE_MATRIX:
            lines.append(
                f"| {row['id']} | {row['milestone']} | **{row['status']}** | "
                f"{row['until']} | {row['shipped']} |"
            )
        lines.append("")
        return "\n".join(lines)

    lines = ["research_gate_matrix:"]
    for row in RESEARCH_GATE_MATRIX:
        lines.append(f"  - {row['id']} ({row['milestone']}): {row['status']} until {row['until']}")
    lines.append("training_entrypoints: none (blocked until §21 authorization)")
    return "\n".join(lines)


def research_status_payload() -> dict[str, Any]:
    return {
        "section_21_cleared": False,
        "training_entrypoints_exist": False,
        "m6_m7_blocked_until": "Section21GateReport authorization flags",
        "learned_routing_authorized": False,
        "synthesis_authorized": False,
        "gates": list(RESEARCH_GATE_MATRIX),
        "non_claims_doc": "docs/NON_CLAIMS.md",
    }


def _gate(
    gate_id: str,
    description: str,
    threshold: str,
    observed: float | bool | int | None,
    passed: bool,
    *,
    missing_msg: str,
) -> GateEvaluation:
    reason = None
    if observed is None:
        passed = False
        reason = missing_msg
    elif not passed:
        reason = f"failed threshold {threshold} (observed={observed!r})"
    return GateEvaluation(
        gate_id=gate_id,
        description=description,
        threshold=threshold,
        observed=observed,
        passed=passed,
        blocking_reason=reason,
    )


def _as_fraction(value: float) -> float:
    """Accept either a fraction (0.08) or a percent (8.0) for overhead gates."""
    return float(value) / 100.0 if float(value) > 1.0 else float(value)


def evaluate_section21_gates(
    *,
    protocol_id: str,
    data_lock_hash: str,
    observables: dict[str, Any],
    dataset_sufficiency_for_routing: bool = False,
    dataset_sufficiency_for_synthesis: bool = False,
) -> Section21GateReport:
    """Evaluate the ten shadow-pilot gates (§16.3). Missing data → fail closed."""
    if not protocol_id.strip():
        raise ValueError("protocol_id required")
    if not data_lock_hash.strip():
        raise ValueError("data_lock_hash required")

    auto = observables.get("packet_automation_rate")
    repro = observables.get("exact_environment_reproduction")
    med_oh = observables.get("median_instrumentation_overhead")
    p90_oh = observables.get("p90_instrumentation_overhead")
    comp = observables.get("comprehension_pass_rate")
    agree = observables.get("primary_category_agreement")
    eff = observables.get("instrumented_efficiency_gain")
    sens = observables.get("instrumented_l2_l3_sensitivity_delta_pp")
    l3 = observables.get("instrumented_additional_integrated_l3")
    sealed = observables.get("sealed_reproducible")

    gates = [
        _gate(
            "G1",
            "packet automation rate >= 80%",
            ">=0.80",
            auto,
            isinstance(auto, (int, float)) and float(auto) >= 0.80,
            missing_msg="missing packet_automation_rate",
        ),
        _gate(
            "G2",
            "exact-environment reproduction >= 90%",
            ">=0.90",
            repro,
            isinstance(repro, (int, float)) and float(repro) >= 0.90,
            missing_msg="missing exact_environment_reproduction",
        ),
        _gate(
            "G3",
            "median instrumentation overhead < 10%",
            "<0.10 (or <10 if percent)",
            med_oh,
            isinstance(med_oh, (int, float)) and _as_fraction(float(med_oh)) < 0.10,
            missing_msg="missing median_instrumentation_overhead",
        ),
        _gate(
            "G4",
            "p90 instrumentation overhead < 20%",
            "<0.20 (or <20 if percent)",
            p90_oh,
            isinstance(p90_oh, (int, float)) and _as_fraction(float(p90_oh)) < 0.20,
            missing_msg="missing p90_instrumentation_overhead",
        ),
        _gate(
            "G5",
            "reviewer comprehension pass rate >= 80%",
            ">=0.80",
            comp,
            isinstance(comp, (int, float)) and float(comp) >= 0.80,
            missing_msg="missing comprehension_pass_rate",
        ),
        _gate(
            "G6",
            "primary-category agreement >= 0.70",
            ">=0.70",
            agree,
            isinstance(agree, (int, float)) and float(agree) >= 0.70,
            missing_msg="missing primary_category_agreement",
        ),
        _gate(
            "G7",
            "instrumented review+repair efficiency >= 20% vs control",
            ">=0.20",
            eff,
            isinstance(eff, (int, float)) and float(eff) >= 0.20,
            missing_msg="missing instrumented_efficiency_gain",
        ),
        _gate(
            "G8",
            "instrumented L2/L3 sensitivity within 5pp of control",
            ">= -5.0 percentage points",
            sens,
            isinstance(sens, (int, float)) and float(sens) >= -5.0,
            missing_msg="missing instrumented_l2_l3_sensitivity_delta_pp",
        ),
        _gate(
            "G9",
            "no additional integrated L3 in instrumented condition",
            "==0",
            l3,
            isinstance(l3, int) and l3 == 0,
            missing_msg="missing instrumented_additional_integrated_l3",
        ),
        _gate(
            "G10",
            "protocol, ledger, analysis, report sealed and reproducible",
            "true",
            sealed,
            sealed is True,
            missing_msg="missing sealed_reproducible",
        ),
    ]

    blocking = [g.blocking_reason for g in gates if g.blocking_reason]
    shadow_ok = all(g.passed for g in gates)
    routing_ok = shadow_ok and dataset_sufficiency_for_routing
    synthesis_ok = routing_ok and dataset_sufficiency_for_synthesis
    if shadow_ok and not dataset_sufficiency_for_routing:
        blocking.append("shadow pilot passed but §17 dataset sufficiency not met")
    if routing_ok and not dataset_sufficiency_for_synthesis:
        blocking.append("routing authorized path incomplete for synthesis")

    report = Section21GateReport(
        protocol_id=protocol_id,
        data_lock_hash=data_lock_hash,
        gates=gates,
        shadow_pilot_passed=shadow_ok,
        learned_routing_authorized=routing_ok,
        synthesis_authorized=synthesis_ok,
        blocking_reasons=list(blocking),
    )
    report.report_hash = sha256_value(
        report.model_dump(mode="json", exclude={"report_hash", "generated_at"})
    )
    return report


def evaluate_gates_from_paths(
    *,
    protocol_path: Path,
    ledger_path: Path,
    seal_path: Path,
    analysis_path: Path,
    output_path: Path,
    observables_path: Path | None = None,
) -> Section21GateReport:
    """CLI entry: load analysis + optional observables JSON; write gate report.

    Fail closed if protocol/analysis hashes are blank or observables incomplete.
    """
    import json

    from lpe.pilot.analysis import PilotAnalysisReport, shadow_pilot_gate_inputs_from_analysis
    from lpe.pilot.protocol import verify_freeze

    protocol_root = protocol_path if protocol_path.is_dir() else protocol_path.parent
    bundle = verify_freeze(protocol_root)
    analysis = PilotAnalysisReport.model_validate_json(analysis_path.read_text(encoding="utf-8"))
    if analysis.protocol_id != bundle.protocol.protocol_id:
        raise ValueError("analysis protocol_id does not match frozen protocol")

    # Ledger + seal presence only (full verify is done at data lock).
    if not ledger_path.is_file():
        raise ValueError(f"ledger missing: {ledger_path}")
    if not seal_path.is_file():
        raise ValueError(f"seal missing: {seal_path}")

    extra: dict[str, Any] = {}
    if observables_path is not None:
        extra = json.loads(observables_path.read_text(encoding="utf-8"))

    observables = shadow_pilot_gate_inputs_from_analysis(
        analysis,
        comprehension_pass_rate=extra.get("comprehension_pass_rate"),
        median_overhead_pct=extra.get("median_instrumentation_overhead"),
        p90_overhead_pct=extra.get("p90_instrumentation_overhead"),
        instrumented_vs_control_efficiency_gain=extra.get("instrumented_efficiency_gain"),
        instrumented_l2_l3_sensitivity_delta_pp=extra.get(
            "instrumented_l2_l3_sensitivity_delta_pp"
        ),
        instrumented_additional_integrated_l3=extra.get("instrumented_additional_integrated_l3"),
        sealed_reproducible=extra.get("sealed_reproducible"),
    )
    # Allow observables file to override derived rates.
    for key in (
        "packet_automation_rate",
        "exact_environment_reproduction",
        "primary_category_agreement",
    ):
        if key in extra:
            observables[key] = extra[key]

    report = evaluate_section21_gates(
        protocol_id=bundle.protocol.protocol_id,
        data_lock_hash=str(extra.get("data_lock_hash") or analysis.data_lock_hash),
        observables=observables,
        dataset_sufficiency_for_routing=bool(extra.get("dataset_sufficiency_for_routing", False)),
        dataset_sufficiency_for_synthesis=bool(
            extra.get("dataset_sufficiency_for_synthesis", False)
        ),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return report


def authorization_from_report(report: Section21GateReport) -> dict[str, bool]:
    """Extract authorization flags for MILESTONE_STATUS / CI."""
    return {
        "shadow_pilot_passed": report.shadow_pilot_passed,
        "learned_routing_authorized": report.learned_routing_authorized,
        "synthesis_authorized": report.synthesis_authorized,
    }
