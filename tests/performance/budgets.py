"""§17 soft budgets: CI fails only when a metric exceeds ``2x`` the target.

Hard targets come from ``docs/ENGINEERING_SPEC.md`` §17 / plan §5.1.
Nightly/reference hardware should stay within the hard target; PR CI uses the
regression ceiling so flaky hosts do not gate merges.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Hard targets (ENGINEERING_SPEC §17)
CONTRACT_VALIDATE_S = 1.0
DIFF_CLASSIFY_S = 5.0
PACKET_SIZE_EXCL_LOGS_BYTES = 1_000_000
LEDGER_APPEND_P95_S = 0.100
REVIEW_PACKET_S = 30.0
# Derived / Week-3 scoped (not named in §17 but needed for CI)
EVIDENCE_SKIP_BUILD_S = 5.0
LEDGER_VERIFY_1000_S = 5.0
TPPR_MODERATE_S = 2.0
MARKDOWN_RENDER_S = 2.0
ORCHESTRATION_SKIP_BUILD_S = 5.0
# Synthetic large impact-cone walk (thousands of edges; not named in §17)
IMPACT_CONE_SYNTHETIC_S = 2.0
IMPACT_CONE_SYNTHETIC_PEAK_MIB = 64.0

# Soft CI ceiling = 2x hard target (plan §5.1 / Week 3 exit)
REGRESSION_MULTIPLIER = 2.0


@dataclass(frozen=True)
class SoftBudget:
    name: str
    hard_target: float
    unit: str

    @property
    def soft_ceiling(self) -> float:
        return self.hard_target * REGRESSION_MULTIPLIER


BUDGETS: dict[str, SoftBudget] = {
    "contract_validate_s": SoftBudget("contract_validate_s", CONTRACT_VALIDATE_S, "s"),
    "diff_classify_s": SoftBudget("diff_classify_s", DIFF_CLASSIFY_S, "s"),
    "packet_size_excl_logs_bytes": SoftBudget(
        "packet_size_excl_logs_bytes", float(PACKET_SIZE_EXCL_LOGS_BYTES), "bytes"
    ),
    "ledger_append_p95_s": SoftBudget("ledger_append_p95_s", LEDGER_APPEND_P95_S, "s"),
    "review_packet_s": SoftBudget("review_packet_s", REVIEW_PACKET_S, "s"),
    "evidence_skip_build_s": SoftBudget("evidence_skip_build_s", EVIDENCE_SKIP_BUILD_S, "s"),
    "ledger_verify_1000_s": SoftBudget("ledger_verify_1000_s", LEDGER_VERIFY_1000_S, "s"),
    "tppr_moderate_s": SoftBudget("tppr_moderate_s", TPPR_MODERATE_S, "s"),
    "markdown_render_s": SoftBudget("markdown_render_s", MARKDOWN_RENDER_S, "s"),
    "orchestration_skip_build_s": SoftBudget(
        "orchestration_skip_build_s", ORCHESTRATION_SKIP_BUILD_S, "s"
    ),
    "impact_cone_synthetic_s": SoftBudget("impact_cone_synthetic_s", IMPACT_CONE_SYNTHETIC_S, "s"),
    "impact_cone_synthetic_peak_mib": SoftBudget(
        "impact_cone_synthetic_peak_mib", IMPACT_CONE_SYNTHETIC_PEAK_MIB, "MiB"
    ),
}


def assert_within_soft_budget(metric: str, observed: float) -> None:
    budget = BUDGETS[metric]
    assert observed <= budget.soft_ceiling, (
        f"{metric}={observed:.6g} {budget.unit} exceeds soft ceiling "
        f"{budget.soft_ceiling:.6g} (2x hard target {budget.hard_target:.6g})"
    )


def budget_snapshot() -> list[dict[str, Any]]:
    return [{**asdict(b), "soft_ceiling": b.soft_ceiling} for b in BUDGETS.values()]
