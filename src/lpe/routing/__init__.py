"""Learned routing baseline (M6 scaffold only).

**EPIC-039 blocked until ENGINEERING_SPEC §21.** No model training entrypoint
exists in this package. ``DeterministicRoutingBaseline`` is a fixed-priority
comparison scaffold only (AUDIT-031). Calling ``train`` / learned strategies
raises ``ResearchGateBlocked``.
"""

from lpe.routing.baseline import (
    DeterministicRoutingBaseline,
    RoutingDecision,
    RoutingStrategy,
    TrainingBlockedError,
)

__all__ = [
    "DeterministicRoutingBaseline",
    "RoutingDecision",
    "RoutingStrategy",
    "TrainingBlockedError",
]
