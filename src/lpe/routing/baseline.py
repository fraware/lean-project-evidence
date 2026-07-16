from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RoutingStrategy(StrEnum):
    DETERMINISTIC_BASELINE = "deterministic_baseline"
    LEARNED = "learned"


@dataclass(frozen=True)
class RoutingDecision:
    strategy: RoutingStrategy
    question_priority: list[str]
    rationale: str


class DeterministicRoutingBaseline:
    """Fixed priority routing baseline for M6 gate comparison.

    **Gate-blocked / no training (AUDIT-031):** deterministic scaffold only.
    Learned routing and model training are blocked until ENGINEERING_SPEC §21
    utility gates pass. This class never loads or trains a model.
    """

    PRIORITY = ["semantic", "repository", "downstream", "kernel", "persistence", "uncertainty"]

    def route(self, *, unresolved_dimensions: list[str]) -> RoutingDecision:
        ordered = sorted(
            unresolved_dimensions,
            key=lambda dim: self.PRIORITY.index(dim) if dim in self.PRIORITY else 99,
        )
        return RoutingDecision(
            strategy=RoutingStrategy.DETERMINISTIC_BASELINE,
            question_priority=ordered,
            rationale=(
                "Fixed dimension priority per ADR 0003 human authority constraints; "
                "not a learned policy"
            ),
        )
