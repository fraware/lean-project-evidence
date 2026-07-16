# Week 4 longevity baseline

Reference machine timings for ledger scale drills (2026-07-16). Soft ceilings from `docs/22_COMPREHENSIVE_TEST_PLAN.md` §6.

## How to run

```bash
# Default CI (includes 10k; excludes 100k)
pytest -q tests/longevity/

# Optional 100k
pytest -q -m slow tests/longevity/test_ledger_100k.py
```

## Observed (10k)

| Metric | Observed | Soft ceiling |
| --- | ---: | ---: |
| Append 10k sequential | ~96 s | (informational) |
| `LedgerStore.verify` | ~1.7 s | 30 s |
| `export_jsonl` | ~3.8 s | 60 s with verify |
| `verify_exported_jsonl` | ~4.5 s | 60 s with export |

Verify scales roughly linearly from Week 3 (~85 ms @ 1k → ~1.7 s @ 10k).

## Notes

- Export/verify stream from SQLite / JSONL (memory-bounded).
- Tamper of a mid-file `event_hash` still fails `verify_exported_jsonl`.
- 100k is optional nightly/`-m slow` only; not claimed in default CI.
