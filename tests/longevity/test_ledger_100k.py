"""Optional 100k ledger longevity drill (excluded from default CI).

Run explicitly::

    pytest -q -m slow tests/longevity/test_ledger_100k.py

Plan §6: sample verify every 10k; export completes < 5 min.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from lpe.ledger.store import LedgerStore
from tests.longevity.conftest import LEDGER_100K_EXPORT_S, append_n

N_100K = 100_000
SAMPLE_EVERY = 10_000


@pytest.mark.longevity
@pytest.mark.slow
def test_ledger_100k_append_sample_verify_and_export(tmp_path: Path) -> None:
    """Nightly / manual scale drill; not part of default ``pytest -q``."""
    store = LedgerStore(tmp_path / "ledger-100k.sqlite3")
    store.initialize()

    for checkpoint in range(SAMPLE_EVERY, N_100K + 1, SAMPLE_EVERY):
        append_n(store, SAMPLE_EVERY, start=checkpoint - SAMPLE_EVERY)
        store.verify()

    export_path = tmp_path / "events-100k.jsonl"
    started = time.perf_counter()
    written = store.export_jsonl(export_path)
    verified = LedgerStore.verify_exported_jsonl(export_path)
    elapsed_s = time.perf_counter() - started

    assert written == N_100K
    assert verified == N_100K
    assert elapsed_s <= LEDGER_100K_EXPORT_S, (
        f"100k export+verify took {elapsed_s:.3f}s; "
        f"soft ceiling {LEDGER_100K_EXPORT_S}s"
    )
