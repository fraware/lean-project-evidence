"""Shared helpers for longevity drills."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lpe.ledger.store import LedgerStore
from lpe.models import EventType, UtilityEvent

# Soft ceilings from plan §6 (CI-friendly; fail only on egregious regressions).
LEDGER_10K_VERIFY_S = 30.0
LEDGER_10K_EXPORT_VERIFY_S = 60.0
LEDGER_100K_EXPORT_S = 300.0  # 5 minutes


def longevity_event(n: int, *, artifact_id: str = "longevity-artifact") -> UtilityEvent:
    return UtilityEvent(
        event_id=f"longevity-evt-{n:06d}",
        event_type=EventType.CANDIDATE_REGISTERED,
        project_id="longevity-project",
        artifact_id=artifact_id,
        obligation_id="O-01",
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        actor_id="longevity-tester",
        payload={"n": n, "suite": "longevity"},
    )


def append_n(store: LedgerStore, count: int, *, start: int = 0) -> None:
    for i in range(start, start + count):
        store.append(longevity_event(i))


@pytest.fixture
def longevity_ledger(tmp_path: Path) -> LedgerStore:
    store = LedgerStore(tmp_path / "longevity-ledger.sqlite3")
    store.initialize()
    return store
