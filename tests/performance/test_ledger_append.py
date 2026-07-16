"""Ledger append throughput and verify time at N=100 and N=1000."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lpe.ledger.store import LedgerStore
from lpe.models import EventType, UtilityEvent
from tests.performance.budgets import assert_within_soft_budget
from tests.performance.metrics import record, summarize_latencies, timed


def _event(n: int) -> UtilityEvent:
    return UtilityEvent(
        event_id=f"perf-evt-{n}",
        event_type=EventType.CANDIDATE_REGISTERED,
        project_id="project",
        artifact_id="artifact-perf",
        obligation_id="O-01",
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        actor_id="perf-tester",
        payload={"n": n},
    )


def _append_batch(store: LedgerStore, count: int) -> list[float]:
    samples: list[float] = []
    for i in range(count):
        with timed() as elapsed:
            store.append(_event(i))
        samples.append(elapsed[0])
    return samples


@pytest.mark.performance
@pytest.mark.parametrize("n", [100, 1000])
def test_ledger_append_and_verify_at_n(tmp_path: Path, n: int) -> None:
    store = LedgerStore(tmp_path / f"ledger-{n}.sqlite3")
    store.initialize()

    samples = _append_batch(store, n)
    stats = summarize_latencies(samples)
    record(
        f"ledger_append_p95_s_n{n}",
        stats["p95_s"],
        unit="s",
        notes=f"p95 of {n} sequential appends after initialize()",
    )
    record(
        f"ledger_append_mean_s_n{n}",
        stats["mean_s"],
        unit="s",
        notes=f"mean of {n} sequential appends",
    )
    # Soft budget is the §17 per-append p95 (2x). Same ceiling at N=100 and N=1000.
    assert_within_soft_budget("ledger_append_p95_s", stats["p95_s"])

    with timed() as elapsed:
        store.verify()
    verify_s = elapsed[0]
    record(
        f"ledger_verify_s_n{n}",
        verify_s,
        unit="s",
        notes=f"full hash-chain verify over {n} events",
    )
    if n == 1000:
        assert_within_soft_budget("ledger_verify_1000_s", verify_s)

    assert len(store.events()) == n
