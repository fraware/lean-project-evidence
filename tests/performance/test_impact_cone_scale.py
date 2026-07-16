"""Synthetic large impact-cone memory/time soft budgets (thousands of edges)."""

from __future__ import annotations

import tracemalloc

import pytest

from lpe.lean.extractor import impact_cone
from tests.performance.budgets import assert_within_soft_budget
from tests.performance.metrics import record, timed

# Graph size: deep chain + wide fan-out → thousands of edges, CI-friendly.
_CHAIN_LEN = 2_000
_FANOUT_ROOTS = 50
_FANOUT_WIDTH = 40  # 50 * 40 = 2_000 fan-out edges
# Total edges ≈ 1_999 (chain) + 2_000 (fan-out) ≈ 4_000


def _synthetic_large_graph() -> tuple[dict[str, list[str]], set[str], int]:
    """Build an adjacency list with thousands of downstream edges."""
    graph: dict[str, list[str]] = {}
    edge_count = 0

    # Long chain: n0 → n1 → … → n_{CHAIN_LEN-1}
    for i in range(_CHAIN_LEN - 1):
        src = f"chain.{i}"
        dst = f"chain.{i + 1}"
        graph.setdefault(src, []).append(dst)
        edge_count += 1

    # Fan-out forest: each root fans to WIDTH leaves.
    for r in range(_FANOUT_ROOTS):
        root = f"fan.root.{r}"
        leaves = [f"fan.leaf.{r}.{w}" for w in range(_FANOUT_WIDTH)]
        graph[root] = leaves
        edge_count += len(leaves)

    # Seeds: head of chain (reaches ~1999) + all fan roots (reach 2000 leaves).
    changed = {"chain.0"} | {f"fan.root.{r}" for r in range(_FANOUT_ROOTS)}
    return graph, changed, edge_count


@pytest.mark.performance
def test_large_synthetic_impact_cone_within_soft_budgets() -> None:
    """Invariant: cone walk on ~4k-edge graph stays within soft time/memory ceilings."""
    graph, changed, edge_count = _synthetic_large_graph()
    assert edge_count >= 3_000

    tracemalloc.start()
    try:
        with timed() as elapsed:
            cone = impact_cone(graph, changed=changed)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()

    elapsed_s = elapsed[0]
    peak_mib = peak / (1024 * 1024)

    # Chain reaches chain.1..chain.1999; fan leaves are all reached; roots are seeds
    # so they are not in the cone unless also dependents (they are not).
    assert len(cone) == (_CHAIN_LEN - 1) + (_FANOUT_ROOTS * _FANOUT_WIDTH)
    assert "chain.0" not in cone
    assert f"chain.{_CHAIN_LEN - 1}" in cone

    record(
        "impact_cone_synthetic_s",
        elapsed_s,
        unit="s",
        notes=f"edges={edge_count} cone={len(cone)}",
    )
    record(
        "impact_cone_synthetic_peak_mib",
        peak_mib,
        unit="MiB",
        notes=f"tracemalloc peak; edges={edge_count}",
    )
    assert_within_soft_budget("impact_cone_synthetic_s", elapsed_s)
    assert_within_soft_budget("impact_cone_synthetic_peak_mib", peak_mib)
