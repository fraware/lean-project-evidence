"""Property-style ledger chain invariants."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lpe.ledger.store import LedgerIntegrityError, LedgerStore
from lpe.models import EventType, UtilityEvent


def _event(rng: random.Random, *, project_id: str, seq: int) -> UtilityEvent:
    return UtilityEvent(
        event_id=f"evt-{seq}-{rng.randint(0, 10**6)}",
        event_type=EventType.CANDIDATE_REGISTERED,
        project_id=project_id,
        artifact_id=f"artifact-{seq}",
        obligation_id="O-01",
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        actor_id=f"actor-{rng.randint(1, 5)}",
        payload={"seq": seq, "nonce": rng.randint(0, 10**9)},
    )


@pytest.mark.parametrize("seed", range(8))
def test_ledger_chain_verifies_after_random_appends(tmp_path: Path, seed: int) -> None:
    rng = random.Random(seed)
    path = tmp_path / f"ledger-{seed}.sqlite3"
    store = LedgerStore(path)
    store.initialize()
    n = rng.randint(3, 20)
    for i in range(n):
        store.append(_event(rng, project_id="proj-prop", seq=i))
    store.verify()
    exported = tmp_path / f"export-{seed}.jsonl"
    store.export_jsonl(exported)
    assert LedgerStore.verify_exported_jsonl(exported) == n


@pytest.mark.parametrize("seed", range(5))
def test_ledger_single_field_tamper_fails(tmp_path: Path, seed: int) -> None:
    rng = random.Random(seed + 50)
    path = tmp_path / f"tamper-{seed}.sqlite3"
    store = LedgerStore(path)
    store.initialize()
    for i in range(5):
        store.append(_event(rng, project_id="proj-tamper", seq=i))
    exported = tmp_path / f"tamper-export-{seed}.jsonl"
    store.export_jsonl(exported)
    lines = exported.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 2
    idx = rng.randint(0, len(lines) - 1)
    row = lines[idx]
    if "1" in row:
        flipped = row.replace("1", "0", 1)
    else:
        flipped = row[:-1] + ("0" if row[-1] != "0" else "1")
    lines[idx] = flipped
    exported.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(LedgerIntegrityError):
        LedgerStore.verify_exported_jsonl(exported)
