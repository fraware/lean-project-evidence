# Week 3 performance baseline

**Machine:** Windows 10 (local reference), 2026-07-16  
**Commit context:** Week 3 performance harness (`tests/performance/`)  
**Raw JSON:** [`benchmarks/latest.json`](../../benchmarks/latest.json)  
**Command:** `LPE_RECORD_BENCHMARKS=1 pytest -q tests/performance/`

## Methodology

- Wall times measured with `time.perf_counter` inside the process (not shell `time`).
- Soft CI assertions fail only when a metric exceeds **2×** the ENGINEERING_SPEC §17 hard target (see `tests/performance/budgets.py`).
- Ledger scale for Week 3 is **N=100 and N=1000** only (100k is Week 4 longevity).
- Packet size is measured on JSON with `stdout`/`stderr` bodies cleared (§17: under 1 MB excluding logs).
- Docker cold-start uses `@pytest.mark.docker` and skips when the daemon is unavailable.

## Key numbers (this machine)

| Metric | Observed | §17 hard target | Soft ceiling (2×) |
| --- | ---: | ---: | ---: |
| Contract load (steady) | 25 ms | 1 s | 2 s |
| `lpe contract validate` CLI | 50 ms | 1 s | 2 s |
| Diff classification (1-file Lean PR) | 271 ms | 5 s | 10 s |
| Evidence compile `--skip-build` | 355 ms | 5 s (suite) | 10 s |
| Packet JSON excl. logs | ~17 KB | 1 MB | 2 MB |
| Ledger append p95 @ N=100 | 5.2 ms | 100 ms | 200 ms |
| Ledger append p95 @ N=1000 | 5.8 ms | 100 ms | 200 ms |
| Ledger verify @ N=1000 | 85 ms | 5 s (suite) | 10 s |
| TPPR compute (~839 events) | 0.8 ms | 2 s (suite) | 4 s |
| Review packet (compile + markdown) | 335 ms | 30 s | 60 s |
| Markdown render alone | 0.3 ms | 2 s (suite) | 4 s |
| Orchestration skip-build | 365 ms | 5 s (suite) | 10 s |
| Docker cold-start (`ubuntu:22.04 lean --version`) | 1.45 s | n/a (doc) | 60 s sanity |
| Host trivial (`python -c print`) | 1.06 s | n/a (doc) | 10 s sanity |

No §17 budget exceeded 2× on this reference hardware.

## Cost-reduction notes

1. **Ledger `initialize()` once per store instance** — previously re-ran `SCHEMA` on every append; now cached. Improves append throughput without changing hash-chain semantics.
2. **Optional `contract=` on `compile_evidence`** — callers that already loaded the contract skip a redundant YAML re-read.
3. **Markdown omits raw `stdout`/`stderr`** — review packets keep hashes/scalars; full logs stay in evidence JSON / side files. Truncation caps (`max_output_bytes`) remain enforced on executors.
4. **`--skip-build` path** — zero container cost; `execution.isolation` stays `NOT_APPLICABLE` / non-PASS (honest).
5. **Combined Docker build+extract** — preferred path uses **one** container start (`sandbox_invocations: 1`) instead of sequential build then extract (2 starts). Metric `docker_combined_build_extract_invocations` documents the model; disable with `LPE_DOCKER_COMBINED_BUILD_EXTRACT=0`.

### Combined vs sequential container starts (recorded model)

| Mode | Env | Container starts per evidence compile (build+extract) |
| --- | --- | ---: |
| Combined (preferred) | default | **1** (`sandbox_invocations: 1`) |
| Sequential fallback | `LPE_DOCKER_COMBINED_BUILD_EXTRACT=0` or custom extract cmd | **2** |

Cold-start tax scales roughly linearly with starts: ~1.45 s × N for a trivial
`ubuntu:22.04` probe on the reference machine (see table above). Prefer combined
whenever the image can run both `lake build` and `lake exe lpe_extract`.

## Docker cold-start vs `--insecure-host-exec`

| Path | When acceptable | Cost signal (this run) |
| --- | --- | --- |
| Docker `--network=none` (default) | Untrusted repos; `network_policy: deny` | ~1.5 s container create+run for a trivial command (before Lean work) |
| Docker combined build+extract | Lean-capable image; toolchain path | **1** container start (vs 2 sequential) |
| `--insecure-host-exec` | Trusted local only; refused under `network_policy: deny` | ~1.0 s for a trivial host subprocess here; **does not** claim network isolation PASS |

True orchestration overhead vs Lean build (§17 &lt;10%) requires a real Lake/Lean wall clock and is out of scope for skip-build CI. Week 2 Docker smoke remains the isolation correctness gate; this Week 3 measurement documents container start tax only.

## Re-recording

```bash
# PowerShell
$env:LPE_RECORD_BENCHMARKS='1'; pytest -q tests/performance/
```

Commit updated `benchmarks/latest.json` and this document when reference hardware or methodology changes materially.
