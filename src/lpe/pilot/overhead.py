from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OverheadReport:
    baseline_minutes: float
    instrumented_minutes: float
    overhead_fraction: float
    within_budget: bool

    @classmethod
    def compute(
        cls,
        *,
        baseline_minutes: float,
        instrumented_minutes: float,
        budget_fraction: float = 0.10,
    ) -> "OverheadReport":
        if baseline_minutes <= 0:
            overhead = 0.0
        else:
            overhead = (instrumented_minutes - baseline_minutes) / baseline_minutes
        return cls(
            baseline_minutes=baseline_minutes,
            instrumented_minutes=instrumented_minutes,
            overhead_fraction=overhead,
            within_budget=overhead <= budget_fraction,
        )
