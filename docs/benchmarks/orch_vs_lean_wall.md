# §17 orchestration vs Lean wall

**Date:** 2026-07-16  
**Fixture:** `tests/fixtures/lean_project/`  
**Command:** `pytest -q -m "lean and performance" tests/performance/test_orchestration_lean_wall.py`

## Method

1. Measure `lake build` wall time on the fixture (`lean_wall_s`).
2. Measure LPE orchestration slice (`orch_vs_lean_wall_s`) — toolchain
   `extract_lean_repository` (or skip-build compile when a contract is present).
3. Ratio = `orch / lean_wall`. ENGINEERING_SPEC §17 target: **&lt;10%**.

## Honesty

Do **not** invent a ratio. When Lake is unavailable, the performance test
skips. Soft assert: ratio &lt; 10% preferred; ratios ≥10% are recorded and only
hard-fail above 2× Lean wall (absurd orchestration dominance).

## Snapshot

Latest machine results are emitted via `tests/performance/metrics.py` into
`benchmarks/latest.json` when `LPE_RECORD_BENCHMARKS=1`. Keys:

- `lean_wall_s`
- `orch_vs_lean_wall_s`
- `orchestration_ratio`

Re-run after fixture or extractor changes; refresh this note with observed %.

## Operator note

Default Docker image `ubuntu:22.04` is not Lean-capable. Use host Lake or
`LPE_DOCKER_IMAGE=lpe-lean:4.14` for typecheck+extract paths.
