from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from lpe.honesty.research_gates import ResearchGateBlocked, refuse_research_entrypoint

# Stable id for §21 held-out comparison against any future learned policy.
# No learning: this is a fixed-priority scaffold only (EPIC-039 blocked).
DETERMINISTIC_BASELINE_ID = "deterministic_baseline.v1"


class TrainingBlockedError(ResearchGateBlocked):
    """Alias: M6 training does not exist until §21."""


class RoutingStrategy(StrEnum):
    DETERMINISTIC_BASELINE = "deterministic_baseline"
    LEARNED = "learned"


@dataclass(frozen=True)
class RoutingDecision:
    strategy: RoutingStrategy
    baseline_id: str
    question_priority: list[str]
    rationale: str


class DeterministicRoutingBaseline:
    """Fixed priority routing baseline for M6 gate comparison.

    **Gate-blocked / no training (AUDIT-031 / EPIC-039):** deterministic scaffold
    only. Learned routing and model training are blocked until ENGINEERING_SPEC
    §21 utility gates pass. This class never loads or trains a model; there is
    no ``fit`` / ``train`` implementation that succeeds.
    """

    BASELINE_ID = DETERMINISTIC_BASELINE_ID
    PRIORITY: ClassVar[list[str]] = [
        "semantic",
        "repository",
        "downstream",
        "kernel",
        "persistence",
        "uncertainty",
    ]

    def route(self, *, unresolved_dimensions: list[str]) -> RoutingDecision:
        ordered = sorted(
            unresolved_dimensions,
            key=lambda dim: self.PRIORITY.index(dim) if dim in self.PRIORITY else 99,
        )
        return RoutingDecision(
            strategy=RoutingStrategy.DETERMINISTIC_BASELINE,
            baseline_id=self.BASELINE_ID,
            question_priority=ordered,
            rationale=(
                "Fixed dimension priority per ADR 0003 human authority constraints; "
                "not a learned policy; EPIC-039 blocked until §21; "
                f"baseline_id={self.BASELINE_ID}"
            ),
        )

    def train(self, *args: object, **kwargs: object) -> None:
        """Training entrypoint does not exist (EPIC-039 / §21)."""
        del args, kwargs
        refuse_research_entrypoint("routing.train")

    def load_learned_policy(self, *args: object, **kwargs: object) -> None:
        """Learned policy load is blocked until §21."""
        del args, kwargs
        refuse_research_entrypoint("routing.learned")

    @property
    def training_blocked_reason(self) -> str:
        return (
            "M6 / EPIC-039 learned routing blocked until ENGINEERING_SPEC §21 "
            "utility gates pass. No training entrypoint exists in lpe.routing."
        )
