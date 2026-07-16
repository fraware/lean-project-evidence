"""Learned routing baseline (M6 scaffold only).

Gate-blocked: no model training. Deterministic priority only until
ENGINEERING_SPEC §21 utility gates pass (AUDIT-031).
"""

from lpe.routing.baseline import DeterministicRoutingBaseline, RoutingDecision, RoutingStrategy

__all__ = ["DeterministicRoutingBaseline", "RoutingDecision", "RoutingStrategy"]
