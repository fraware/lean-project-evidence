# Test execution log

## 2026-07-16 — Audit gap closure (fixture-excellence 0.2)

**Command:** `pytest -q -m "not slow"`  
**Result:** **543** collected under filter — **543 passed**, **1 skipped** (`LPE_GH_CHECK_E2E` unset), 1 deselected (slow). Prior baseline: **480**.

### What changed

| Item | Detail |
| --- | --- |
| Phase 0 honesty | VALIDATION/CHANGELOG/§4.2/month-one; CODEOWNERS `@fraware`; CI fail-closed |
| M3 fixture-excellence | Toolchain-first; stale artifact gate; Ambiguous FQN warnings; diamond/chain/opaque cones |
| M4 Lake semantics | `lake env lean` examples PASS + cex FAIL; statement structure fields |
| §17 orch vs Lean | `tests/performance/test_orchestration_lean_wall.py` + `docs/benchmarks/orch_vs_lean_wall.md` |
| Ops / trust | Env-gated GH Check E2E; property tests; `lpe doctor --ledger`; `migrate --write` |
| Handoff | `docs/27_PARTNER_PILOT_HANDOFF.md` — partner pilot still deferred |

### Residual deferred

- Partner pilot / §21 / M6–M7 / Mathlib-scale
- Live GH Check POST (needs `LPE_GH_CHECK_E2E=1` + throwaway repo)
- WORM ledger root of trust

---

## 2026-07-16 — Redaction / ledger archive / impact-cone scale / threat model

**Command:** `pytest -q -m "not slow"`  
**Result:** **480** collected — **480 passed**, 0 skipped, 1 deselected (slow). Prior baseline: **455**.

### What changed

| Item | Detail |
| --- | --- |
| Secret redaction | Expanded corpus: Slack/GitLab/npm/Stripe/OpenAI/Anthropic/HF, JWT, PEM/OpenSSH; Lean-log non-over-redact tests |
| Ledger archive | `lpe ledger archive` verify→export→verify JSONL; live SQLite untouched; fresh-ledger runbook in `docs/06` |
| Impact cone scale | Synthetic ~4k-edge graph soft time/memory budgets (`tests/performance/test_impact_cone_scale.py`) |
| Threat model | `docs/25_LEDGER_THREAT_MODEL.md` tabletop (host FS vs export verify) |
| Dependabot / SHA | Documented pin + weekly Dependabot drift review in `docs/09` / `SECURITY.md` (Actions already SHA-pinned) |

### Residual engineering gaps

- Live GitHub Check POST to a throwaway repo (needs user secrets — document/skip only)
- CODEOWNERS fail-closed after real owners land
- Partner pilot / §21 / Mathlib-scale / ML still deferred

### Explicitly not claimed

- §21 / causal pilot / partner study execution
- WORM / transparency-log root of trust
- In-place ledger compaction or DELETE-based retention

---

## 2026-07-16 — Engineering durability / adapters / path fuzz

**Command:** `pytest -q -m "not slow"`  
**Result:** **455** collected — **455 passed**, 0 skipped, 1 deselected (slow). Prior baseline: **400**.

### What changed

| Item | Detail |
| --- | --- |
| Ledger WAL | Per-connection WAL + sync + busy_timeout; checkpoint; crash/recovery + multiprocess writer tests |
| Path safety | Reject NUL, `%2e/%2f/%5c`, NTFS `:` streams, Unicode lookalike dots; symlink escape tests |
| GitHub Check | `lpe github submit-check` payload→`gh api` plan; dry-run default; `--post` mocked |
| Migrate dry-run | `lpe contract migrate-dry-run` — refuse/no-op/would-rewrite, never mutates |
| Opaque IR | `OpaqueLimits.lean` + synthetic axiom limitation unit tests |
| CI template | Optional `lpe-lean-docker-optional` job (cached image only; not default CI) |
| Cost note | Combined vs sequential container starts recorded in `docs/benchmarks/week3_baseline.md` |

### Residual engineering gaps

- Live GitHub Check POST to a throwaway repo (secrets / required-check E2E)
- Secret-redaction corpus expansion; Dependabot SHA drift review
- Retention/compaction prototype; large synthetic impact-cone memory budgets
- Ledger threat-model tabletop (host FS vs export verify) — document only
- Mathlib-scale / §21 still out of scope (partner human protocol deferred)

### Explicitly not claimed

- §21 / causal pilot / partner study execution
- R3/R4 production ACCEPT (ADR 0003)
- Automatic contract file rewrite migrator
- Live `gh api` network submission in default CI

---

## 2026-07-16 — Partner shadow-pilot readiness kit

**Command:** `pytest -q -m "not slow"`  
**Result:** **400** collected — **400 passed**, 0 skipped, 1 deselected (slow). Prior baseline: **394**.

### What changed

| Item | Detail |
| --- | --- |
| Partner checklist | `docs/24_PARTNER_PILOT_READY.md` — instrument, not claim |
| Analysis plan stub | `docs/pilot_analysis_plan_template.md` marked **UNFROZEN** |
| Scaffold CLI | `lpe pilot init-partner` (+ `scripts/init_partner_pilot.py`) |
| Field overhead | `lpe pilot overhead` — wall-clock vs review minutes |
| Conditions | `control` / `instrumented` / `shadow` sample tags |
| Honesty | Explicitly **not §21**; ready to *instrument* only |

### Residual gaps (partner-pilot blockers only)

- Real partner human experts + signed protocol freeze + held-out set
- Production ACCEPT authority for R3/R4 unchanged (ADR 0003)
- Mathlib-scale / §21 still out of scope

### Explicitly not claimed

- §21 / causal pilot
- Ready-to-claim / science publication
- R3/R4 production ACCEPT

---

## 2026-07-16 — R0/R1 ACCEPT E2E + Docker flake harden

**Command:** `pytest -q -m "not slow"`  
**Result:** **394** collected — **394 passed**, 0 skipped, 1 deselected (slow). Prior baseline: **390** (389 passed + 1 docker skip).

### What changed

| Item | Detail |
| --- | --- |
| R0 ACCEPT E2E | Sandboxed `lpe-lean:4.14` docs-only → toolchain-complete → gate `ACCEPT` → authorized review ACCEPT → ledger + TPPR sustained credit |
| R1 ACCEPT E2E | Private body-only → hard gates PASS + policy `ESCALATE` → authorized `lean-engineer` ACCEPT; R3 ACCEPT still refused |
| Soft findings | `repository.api_fit` / `downstream.declared_use` → `NOT_APPLICABLE` without public decls |
| Review→TPPR | `--obligation-ids` + fidelity flags on ACCEPT events |
| Docker marker | `docker info` retry/backoff before skip |
| Pilot reports | Dry-run MD separates software metrics vs causal / §21 |

### Residual gaps (partner-pilot blockers only)

- Real partner shadow pilot (human experts, protocol freeze, held-out set)
- Production ACCEPT authority for R3/R4 unchanged (ADR 0003)
- Mathlib-scale / §21 still out of scope

### Explicitly not claimed

- §21 / causal pilot
- R3/R4 production ACCEPT
- Mathlib-scale elaborator completeness

---

## 2026-07-16 — Durable pilot warehouse (ledger-backed)

**Command:** `pytest -q` (default excludes `@pytest.mark.slow`)  
**Result:** **390** collected under `-m "not slow"` — **389 passed**, 1 skipped (Docker daemon), 1 deselected (slow). Prior baseline: **383**.

### What changed

| Item | Detail |
| --- | --- |
| Warehouse | `PilotWarehouse` appends to utility ledger (`CANDIDATE_REGISTERED`, `EVIDENCE_COMPILED`, `EXPERT_TIME_RECORDED`, `REVIEW_SUBMITTED` markers) |
| CLI | `lpe pilot record` / `summary` / `dry-run` |
| Durability | New `LedgerStore` instance reloads prior pilot events; anonymous actors fail closed |
| Reports | JSON + Markdown separate software metrics from causal / §21 claims |
| Honesty | Explicitly **not §21**; no causal utility claims |

### Residual gaps

- Real partner shadow pilot (human experts, protocol freeze, held-out set)
- Production ACCEPT authority for R3/R4 unchanged (ADR 0003)
- Mathlib-scale / §21 still out of scope

### Explicitly not claimed

- §21 / causal pilot
- Partner shadow-pilot authorization
- Causal TPPR improvement

---

## 2026-07-16 — Combined Docker build+extract + multi-module cone stress

**Command:** `pytest -q` (default excludes `@pytest.mark.slow`)  
**Lean host:** optional (Docker Lean E2E / combined multi-module scrub host `_lake_bin`).  
**Docker:** `ubuntu:22.04` (no Lean) + local **`lpe-lean:4.14`**.  
**Result:** **383** collected under `-m "not slow"` (+1 slow deselected). Full runs on this host: **380–382 passed** with intermittent `@docker` skips when `docker info` flakes; combined Lean E2E (`sandbox_invocations==1`) re-verified green when the daemon and `lpe-lean:4.14` are up. Baseline prior cut: **377**.

### What changed

| Item | Detail |
| --- | --- |
| Invocation model | Docker prefers one `docker run` via `verify_build_and_extract` (`combined_build_extract`, `sandbox_invocations: 1`) |
| Fail closed | Build-phase fail → no toolchain-complete claim; extract-phase fail → incomplete / UNKNOWN; no host Lake fallback on Docker |
| Fallback | `LPE_DOCKER_COMBINED_BUILD_EXTRACT=0` or custom `LPE_LEAN_EXTRACT_CMD` → sequential (up to 2 container starts) |
| Fixture | `LibA`→`LibB`→`LibC`→`Cross` (+ Consumer fan-in); `expectations_multi_module.json` |
| Cost note | Benchmarks record `docker_combined_build_extract_invocations: 1` (preferred cold path) |

### E2E paths

| Path | When | Assertions |
| --- | --- | --- |
| **Host-exec** | Lean on PATH | Build PASS; toolchain-complete; isolation **UNKNOWN** |
| **Docker ubuntu** | Daemon up | Build FAIL (no Lake); isolation PASS; axioms never fake-PASS; combined still one container |
| **Docker `lpe-lean:4.14`** | Image present | Combined build+extract; `sandbox_invocations==1`; isolation **PASS**; toolchain-complete **without host Lake** |
| **Multi-module cones** | `@lean` / Docker image | Hand-audited LibA / usesCore cones across modules |

### Residual gaps

- Mathlib-scale / §21 still out of scope (fixture has no Mathlib; still a small closed package)
- True partner shadow pilot / production ACCEPT authority unchanged

### Explicitly not claimed

- §21 / causal pilot
- Isolation PASS under host-exec
- Official maintained Lean Docker Hub image
- Mathlib-scale elaborator completeness

---

## 2026-07-16 — Sandboxed `lake exe lpe_extract` (same Docker as build)

**Command:** `pytest -q` (default excludes `@pytest.mark.slow`)  
**Lean host:** optional (Docker Lean E2E scrubbs host `_lake_bin`).  
**Docker:** `ubuntu:22.04` (no Lean) + local **`lpe-lean:4.14`**.  
**Result:** **377 passed**, **1 deselected** (100k ledger). Baseline prior cut: **372**.

### What changed

| Item | Detail |
| --- | --- |
| Extract path | After sandboxed `lake build`, compiler invokes `lake exe lpe_extract` via the same `DockerSandboxExecutor` |
| Provenance | JSON notes + finding `extract_executor: docker-sandbox` |
| Fail closed | Sandboxed extract errors → incomplete extract / UNKNOWN axioms; no host Lake fallback |
| Host-exec | Unchanged; still tested under `@pytest.mark.lean` |

### E2E paths

| Path | When | Assertions |
| --- | --- | --- |
| **Host-exec** | Lean on PATH | Build PASS; toolchain-complete; isolation **UNKNOWN**; `extract_executor=SubprocessLeanExecutor` |
| **Docker ubuntu** | Daemon up | Build FAIL (no Lake); isolation PASS; axioms never fake-PASS |
| **Docker `lpe-lean:4.14`** | Image present | Build + extract under `--network=none`; isolation **PASS**; toolchain-complete **without host Lake** |

### Residual gaps

- Mathlib-scale / §21 still out of scope

### Explicitly not claimed

- §21 / causal pilot
- Isolation PASS under host-exec
- Official maintained Lean Docker Hub image

---

## 2026-07-16 — Sandboxed Lake via `lpe-lean:4.14`

**Command:** `pytest -q` (default excludes `@pytest.mark.slow`)  
**Lean host:** Lean 4.14.0 + Lake available (lean-marked tests **ran**).  
**Docker:** `ubuntu:22.04` (no Lean) + local **`lpe-lean:4.14`** (elan + Lean 4.14.0) built on host.  
**Result:** **372 passed**, **1 deselected** (100k ledger). Baseline prior cut: **368**.

### Image approach

| Item | Detail |
| --- | --- |
| Dockerfile | `docker/lpe-lean/Dockerfile` — `ubuntu:22.04` + elan + pin `leanprover/lean4:v4.14.0` |
| Tag | `lpe-lean:4.14` (`LPE_DOCKER_IMAGE` / `DEFAULT_LEAN_DOCKER_IMAGE`) |
| Build | `scripts/build_lean_docker_image.ps1` / `.sh` (heavy first build; pytest only `docker image inspect`) |
| Windows PATH | Docker executor rewrites Windows host `PATH`/`HOME` to Linux + `/root/.elan/bin` |

### E2E paths

| Path | When | Assertions |
| --- | --- | --- |
| **Host-exec** | Lean on PATH | Build PASS; toolchain-complete; isolation **UNKNOWN** |
| **Docker ubuntu** | Daemon up | Build FAIL (no Lake); isolation PASS; axioms never fake-PASS |
| **Docker `lpe-lean:4.14`** | Image present | Build PASS under `--network=none`; isolation **PASS**; toolchain-complete + FQN cone |

### Also fixed

- Git enrichment short names → module FQNs for impact cones when extraction is available (`resolve_changed_names_for_cone`)

### Residual gaps (superseded by sandboxed extract cut above)

- ~~Post-build `lake exe lpe_extract` still runs on the **host** after a Docker build~~ **fixed**
- Mathlib-scale / §21 still out of scope

### Explicitly not claimed

- §21 / causal pilot
- Isolation PASS under host-exec
- Official maintained Lean Docker Hub image

---

## 2026-07-16 — E2E Lake build → toolchain-complete packet

**Command:** `pytest -q` (default excludes `@pytest.mark.slow`)  
**Lean host:** Lean 4.14.0 + Lake 5.0.0 available (lean-marked tests **ran**).  
**Docker:** available; default image `ubuntu:22.04` has **no** Lean — E2E toolchain path uses host-exec.  
**Result:** **368 passed**, **1 deselected** (100k ledger). Baseline prior cut: **364**.

### E2E path

| Path | When | Assertions |
| --- | --- | --- |
| **Host-exec** (`--insecure-host-exec`, `network_policy: allow`) | Lean/Lake on PATH; no Lean Docker image | `lake build` PASS; extractor `lean.toolchain` + `complete=true`; axiom/impact PASS (schema 1.1); isolation **UNKNOWN** (honest); replacement PASS (hash + `lake env`) |
| **Git worktree** | Same host-exec | Worktree cleaned; `.lpe/lean-extraction.json` persisted to primary repo |
| **Docker** (`network_policy: deny`, `ubuntu:22.04`) | Docker daemon up | Build FAIL without Lake in image; isolation PASS; axioms never fake-PASS when extract suppressed |

### Added / changed

| Package | Files | Focus |
| --- | --- | --- |
| `tests/integration/` | `test_evidence_lean_e2e.py` | Real compile without `--skip-build` |
| `src/lpe/providers/semantic.py` | DownstreamReplacementProvider 0.3 | Hash + Lake dependent compile; fail-closed UNKNOWN |
| `src/lpe/lean/toolchain.py` | `persist_toolchain_artifact` | Copy JSON out of worktree |
| `src/lpe/cli.py` | `lpe lean extract --repo` | Toolchain helper wrapper |

### Residual gaps

- No maintained Lean Docker Hub image → sandboxed Lake E2E needs a pinned Lean-capable `LPE_DOCKER_IMAGE`
- Git enrichment uses short decl names → FQN cone membership tests omit `head_commit`
- Mathlib-scale / §21 still out of scope

### Explicitly not claimed

- §21 / causal pilot
- Isolation PASS under host-exec
- Official maintained Lean Docker image

---

## 2026-07-16 — Elaborator dependency IR (schema 1.1)


**Command:** `pytest -q` (default excludes `@pytest.mark.slow`)  
**Lean host:** Lean 4.14.0 + Lake 5.0.0 available (lean-marked tests **ran**).  
**Result:** **364 passed**, **1 deselected** (100k ledger). Baseline prior cut: **360**.

### Added

| Package | Files | Focus |
| --- | --- | --- |
| `tests/fixtures/lean_project/` | `LpeExtract.lean`, `Diamond.lean`, `Chain.lean` | Environment `getUsedConstantsAsSet` decl edges; module `import_edges`; schema 1.1 |
| `src/lpe/lean/extractor.py` | schema fields + `effective_declaration_edges` | Prefer decl-deps for impact cones; import expansion semantics |
| `tests/integration/` | `test_lean_toolchain_extract.py` | Diamond/chain cone membership; import-edge assertions |
| `tests/unit/` | `test_lean_extractor.py` | Schema 1.0 load + 1.1 round-trip |

### Residual limitations documented

- Tactic-erased intermediate constants
- Opaque/axiom body visibility bounds
- Import edges are module→module (not per-decl provenance)
- No Mathlib-scale CI; no §21 claims

### Explicitly not claimed

- §21 / causal pilot
- Full elaborator dependency completeness under heavy tactics
- Official maintained Lean Docker Hub image

---

## 2026-07-16 — Toolchain extraction path

**Command:** `pytest -q` (default excludes `@pytest.mark.slow`)  
**Lean host:** Lean 4.14.0 + Lake 5.0.0 available (lean-marked tests **ran and passed**).  
**Result:** **360 passed**, **1 deselected** (100k ledger). Baseline Week 4: **352**.

### Added

| Package | Files | Focus |
| --- | --- | --- |
| `src/lpe/lean/` | `toolchain.py`, evolved `extractor.py` | Lake `lpe_extract` invoke; adaptive prefer toolchain JSON; fail-closed regex-stub |
| `tests/fixtures/lean_project/` | Lake package + `LpeExtract.lean` | Real elaborator dump when Lean installed |
| `tests/integration/` | `test_lean_toolchain_extract.py` (`@pytest.mark.lean`) | Produce/complete toolchain JSON; impact cone from Lake extract |
| `tests/integration/` | docker rw / readonly mount probes | Lake needs writable `.lake/`; readonly fails closed |
| `src/lpe/evidence/compiler.py` | post-build extract | Capture JSON before worktree cleanup |
| `src/lpe/providers/semantic.py` | statement_diff / duplicate_retrieval | Prefer toolchain signature hashes; `toolchain_backed` |

### Bugs found and fixed

1. **`lake exe lpe_extract -- path` wrote to a file named `--`** — bare `--` was treated as the out path. Fixed: pass path without `--`; Lean filters `--` if present.
2. **Docker scrubbed PATH** — `/bin/true` and `/bin/cat` required for sandbox probes.

### Explicitly not claimed

- §21 / causal pilot
- Mathlib-scale elaborator CI in default workflow
- Official maintained Lean Docker Hub image

---

## 2026-07-16 — Week 4 complete

**Command:** `pytest -q` (default excludes `@pytest.mark.slow`)  
**Result:** **352 passed**, **1 deselected** (100k ledger). Baseline Week 3: **342**. Wall ~5.8 min on reference machine.

### Added this week

| Package | Files | Focus |
| --- | --- | --- |
| `tests/longevity/` | `test_ledger_10k.py`, `test_ledger_100k.py` (`@pytest.mark.slow`), `test_schema_migration.py`, `test_historical_packets.py`, `conftest.py` | 10k append/verify/export; optional 100k; unknown schema refused; historical packet reload |
| `tests/pilot/` | `test_frozen_corpus_dry_run.py` | Frozen corpus (18) compile→review→ledger→TPPR + overhead helper; **not §21** |
| `docs/pilot_dry_run.md` | honesty doc | Dry-run instrumentation only; §21 not passed |

### Longevity numbers (this machine)

| Metric | Observed | Soft ceiling |
| --- | ---: | ---: |
| Ledger append 10k | ~96 s | (no hard CI gate; verify is gated) |
| Ledger verify 10k | ~1.7 s | 30 s |
| Export JSONL 10k | ~3.8 s | (with verify ≤ 60 s) |
| `verify_exported_jsonl` 10k | ~4.5 s | (with export ≤ 60 s) |
| Tamper mid-export | detected | fail-closed |

Optional 100k: `pytest -q -m slow tests/longevity/test_ledger_100k.py` (excluded from default CI).

### Pilot dry-run outcomes

- Corpus: **18** candidates (6 `examples/candidates` + 12 synthetic).
- Path: `compile --skip-build` → `REQUEST_REPAIR` review → ledger verify → TPPR.
- Automation rate (instrumentation): **1.0** (all packets marked automated).
- TPPR: expert hours &gt; 0; weighted sustained accept **0** (escalate/repair only).
- Overhead helper: compile wall vs review minutes within 10% proxy budget.
- **§21 not passed; no causal claims.**

### Optimizations / fixes

1. **Streaming ledger export/verify** — `export_jsonl` streams SQLite rows; `verify_exported_jsonl` streams lines (memory-bounded for large ledgers).

### Markers

- `@pytest.mark.longevity` — scale/migration drills (10k runs in default CI).
- `@pytest.mark.slow` — 100k ledger; default `addopts` includes `-m "not slow"`.

### Week 4 exit vs plan §9.1 (engineering test-complete)

| # | Criterion | Status |
| --- | --- | --- |
| 1 | ≥250 automated tests, `pytest -q` green | **Met** (352) |
| 2 | P0 matrix coverage / waived gaps | **Met** (Weeks 1–3 + longevity P2 drills) |
| 3 | AUDIT-001..032 REG/CI/DOC map | **Met** (prior weeks) |
| 4 | compile → review → ledger → TPPR | **Met** (+ pilot dry-run corpus) |
| 5 | §17 baselines; no &gt;2× | **Met** (Week 3) |
| 6 | Longevity: 10k + schema migration | **Met** |
| 7 | Honest `VALIDATION_REPORT.md` | **Met** (updated) |
| 8 | Month-one gate on clean clone | **Met** (existing CI/tests) |

### Still research-gated (§9.2 — not implied)

- §21 shadow pilot authorization / causal utility
- Elaborator-complete Lean at Mathlib scale
- M6/M7 training loops; R3/R4 production ACCEPT
- WORM ledger root of trust; live partner GitHub Checks

### Explicitly not claimed

- §21 scientific gate
- 100k run in default CI (optional `-m slow`)
- Real prospective pilot with human experts
- Docker pin rebuild / crash-WAL drills (optional plan rows; deferred)

---

## 2026-07-16 — Week 3 complete

**Command:** `pytest -q`  
**Result:** **342 passed** (baseline Week 2: **328**). Performance suite ~14 s alone; full suite ~86 s. Soft budgets fail only on **&gt;2×** §17 regressions.

### Added this week

| Package | Files | Focus |
| --- | --- | --- |
| `tests/performance/` | `budgets.py`, `metrics.py`, `test_contract_latency.py`, `test_diff_classification.py`, `test_packet_size.py`, `test_ledger_append.py`, `test_tppr_compute.py`, `test_review_packet_latency.py`, `test_truncation_caps.py`, `test_orchestration_overhead.py`, `test_contract_reuse.py` | §17 soft budgets; N=100/1000 ledger; TPPR moderate; markdown size; Docker cold-start (`@pytest.mark.docker`) |
| `benchmarks/latest.json` | machine metrics | Recorded with `LPE_RECORD_BENCHMARKS=1` |
| `docs/benchmarks/week3_baseline.md` | methodology + table | Docker vs host insecure cost notes |

### Optimizations (safe)

1. **Ledger init cache** — `LedgerStore.initialize()` runs schema setup once per instance (was every append).
2. **Contract reuse** — `compile_evidence(..., contract=)` skips redundant YAML load when caller already validated.
3. **Markdown log omit** — `render_packet` replaces raw `stdout`/`stderr` with size placeholders; hashes retained. Truncation caps still enforced on executors.

### Key baselines (this machine)

| Metric | Observed | Soft ceiling |
| --- | ---: | ---: |
| Contract validate CLI | ~50 ms | 2 s |
| Diff classify | ~271 ms | 10 s |
| skip_build compile | ~355 ms | 10 s |
| Packet excl. logs | ~17 KB | 2 MB |
| Ledger append p95 @ 1000 | ~6 ms | 200 ms |
| Ledger verify @ 1000 | ~85 ms | 10 s |
| Docker cold-start | ~1.45 s | 60 s sanity |
| Host trivial subprocess | ~1.06 s | (doc only) |

No §17 metric exceeded 2×. True Lean orchestration ratio (&lt;10%) needs a real Lake build wall clock (not claimed here).

### Explicitly not claimed

- §21 scientific gate / shadow pilot authorization
- Elaborator-complete Lean truth
- Ledger 100k longevity (Week 4)
- Orchestration overhead &lt;10% of Lean build (requires non-skip-build Lean timing)

### Week 4 readiness (longevity + pilot dry-run)

- Ledger verify at 1k is &lt;100 ms → 10k/100k drills are feasible.
- Schema migration + historical packet load still open (`tests/longevity/`).
- Pilot frozen-corpus dry-run + overhead helper still scaffold-only.

### Remaining Week 4+ (from plan §8)

- Longevity: ledger 10k/100k, schema migration, historical packets, Docker pin rebuild
- Pilot frozen-corpus dry-run (no §21 claims)

---

## 2026-07-16 — Week 2 complete

**Command:** `pytest -q`  
**Result:** **328 passed** (baseline Week 1: **303**). Docker-marked tests run when daemon available; otherwise skip via `@pytest.mark.docker`.

### Added this week

| Package | Files | Focus |
| --- | --- | --- |
| `tests/integration/` | `test_git_candidate.py` | Real git commits → `build_candidate_from_commits` / enrich overrides; invalid + null OID fail actionably; CLI exit 1 |
| `tests/integration/` | `test_evidence_docker_build.py` | `@pytest.mark.docker`: `--network=none` + hardening flags; isolation PASS only after sandboxed build; skip_build → NOT_APPLICABLE; allowlist before Docker |
| `tests/integration/` | `test_evidence_lean_repo.py` | Committed `.lpe/lean-extraction.json` toolchain path; regex-stub honesty; incomplete `complete=false` never PASS; prohibited FAIL; impact expectations |
| `tests/integration/` | `test_worktree_isolation.py` | Dirty-tree exclusion; unknown commit reject; compile uses worktree path; cleanup on build exception |
| `tests/fixtures/lean/` | `toolchain_project/`, `impact_cone/GrandConsumer.lean`, `expectations.json` | Deterministic toolchain ingest + expanded hand-audited cone |

### Bugs found and fixed

1. **Worktree leak on build exception** — `compile_evidence` cleaned worktrees only on the success path. Fixed: `try`/`finally` always calls `WorktreeSession.cleanup()`.
2. **Toolchain incomplete still PASS axioms** — `lean.toolchain` with `complete=false` could reach axiom PASS. Fixed: `_check_axioms` requires `_is_toolchain_complete` (extractor + `complete=true` + no errors) before PASS.

### Explicitly not claimed

- §21 scientific gate / shadow pilot authorization
- Elaborator-complete Lean truth beyond labeled toolchain JSON
- Real 30-candidate pilot
- Full Mathlib/Lake CI build (template wired to toolchain fixture; Lake job documents gap)

### Week 3 readiness (perf/cost)

- **Done** — see Week 3 section above. Baselines in `docs/benchmarks/week3_baseline.md`.

---

## 2026-07-16 — Week 1 complete

**Command:** `pytest -q`  
**Result:** **303 passed** (baseline was **201**). Wall time ~46–63s.

### Added this week

| Package | Files | Focus |
| --- | --- | --- |
| `tests/security/` | `test_execution_defaults.py`, `test_build_command_fuzz.py`, `test_redaction_corpus.py`, `test_path_traversal_fuzz.py`, `test_review_authority.py`, `test_candidate_trust.py`, `test_axiom_honesty.py` | AUDIT-001..009, 015–016, 019–020, 025 REG smokes (~88 collected including parametrized) |
| `tests/integration/` | `conftest.py`, `test_contract_cli.py`, `test_tppr_e2e.py`, `test_ledger_tppr_gate.py`, `test_month_one_gate.py` | CLI contract/candidate; compile→review→ledger→TPPR; export/tamper; month-one + doctor (~13) |
| Root `tests/conftest.py` | docker marker auto-skip | `@pytest.mark.docker` |

### Bugs found and fixed

1. **Review expert-time vs TPPR unit mismatch** — `record_review_decision` wrote `minutes` only; `compute_tppr` required `hours` (`KeyError` on E2E path). Fixed: emit `hours` (+ keep `minutes`); TPPR accepts either.

### Explicitly not claimed

- §21 scientific gate / shadow pilot authorization
- Elaborator-complete Lean truth
- Real 30-candidate pilot
- Docker/Lean build integration (Week 2)

### Remaining Week 2+ (from plan §8)

- `tests/integration/test_git_candidate.py` (real temp-repo candidate)
- `test_evidence_docker_build.py` (`@pytest.mark.docker`)
- `test_evidence_lean_repo.py` / Lean workflow wiring
- Deeper ledger–TPPR gate integration if needed beyond Week 1 smoke
- Week 3 performance; Week 4 longevity + pilot dry-run

### P0 matrix notes (Week 1)

Feasible without Lean Docker: closed or regression-covered via `tests/security/` + `tests/integration/` + existing `tests/unit/test_phase*_*.py`. Remaining P0 rows that need Docker/Lean stay Week 2.
