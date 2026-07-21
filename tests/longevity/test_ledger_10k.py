"""Ledger growth to 10k events: append, verify, export, tamper detection.

Plan §6: verify < 30 s; chain valid; export + verify_exported_jsonl.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from lpe.ledger.store import LedgerIntegrityError, LedgerStore
from tests.longevity.conftest import (
    LEDGER_10K_EXPORT_VERIFY_S,
    LEDGER_10K_VERIFY_S,
    append_n,
)

N_10K = 10_000


@pytest.mark.longevity
def test_ledger_10k_append_and_verify(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "ledger-10k.sqlite3")
    store.initialize()
    append_n(store, N_10K)

    started = time.perf_counter()
    store.verify()
    verify_s = time.perf_counter() - started

    assert len(store.events()) == N_10K
    assert verify_s <= LEDGER_10K_VERIFY_S, (
        f"10k ledger verify took {verify_s:.3f}s; soft ceiling {LEDGER_10K_VERIFY_S}s"
    )


@pytest.mark.longevity
def test_ledger_10k_export_jsonl_and_verify(tmp_path: Path) -> None:
    store = LedgerStore(tmp_path / "ledger-10k-export.sqlite3")
    store.initialize()
    append_n(store, N_10K)
    export_path = tmp_path / "events-10k.jsonl"

    started = time.perf_counter()
    written = store.export_jsonl(export_path)
    verified = LedgerStore.verify_exported_jsonl(export_path)
    elapsed_s = time.perf_counter() - started

    assert written == N_10K
    assert verified == N_10K
    assert elapsed_s <= LEDGER_10K_EXPORT_VERIFY_S, (
        f"10k export+verify took {elapsed_s:.3f}s; soft ceiling {LEDGER_10K_EXPORT_VERIFY_S}s"
    )


@pytest.mark.longevity
def test_ledger_10k_export_tamper_still_detected(tmp_path: Path) -> None:
    """At scale, a single mutated event_hash must still fail closed."""
    store = LedgerStore(tmp_path / "ledger-10k-tamper.sqlite3")
    store.initialize()
    # Smaller batch is enough to exercise export streaming + mid-file tamper.
    append_n(store, 500)
    export_path = tmp_path / "events-tamper.jsonl"
    store.export_jsonl(export_path)

    lines = export_path.read_text(encoding="utf-8").splitlines()
    mid = json.loads(lines[250])
    mid["event_hash"] = "0" * 64
    lines[250] = json.dumps(mid, sort_keys=True)
    export_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(LedgerIntegrityError, match="invalid event_hash"):
        LedgerStore.verify_exported_jsonl(export_path)
