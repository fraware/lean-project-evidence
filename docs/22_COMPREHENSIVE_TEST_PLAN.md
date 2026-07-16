# Comprehensive test plan — Lean Project Evidence

**Status:** Week 4 executed (2026-07-16); audit gap closure in progress. Engineering test-complete criteria (§9.1) met for scaffold `0.1.x`; §9.2 research gates remain open. See `docs/23_TEST_EXECUTION_LOG.md`.  
**Baseline:** `pytest -q -m "not slow"` — **575 tests passed**, **1 skipped** (env-gated GH Check E2E), **1 deselected** (`@pytest.mark.slow`). Prior: **543**; audit **480**; **455**; Week 3 **342**.  
**Inputs:** `docs/21_TEST_BACKLOG.md`, `VALIDATION_REPORT.md`, `docs/ENGINEERING_SPEC.md` §15/§17/§20/§21, `docs/10_TESTING_AND_VALIDATION.md`, Phases 1–5 security remediation (AUDIT-001..032), `docs/26_SPEC_ROADMAP_AUDIT.md`.

---

## 1. Goals

### 1.1 Capability coverage

Prove that every **user-facing capability** (CLI + library modules) behaves correctly on happy paths, failure paths, and honesty boundaries:

- Contracts, candidates, evidence compile, gates, risk, execution (sandbox/worktree), Lean extraction, semantic providers, review, ledger, TPPR, GitHub Check, month-one gate, pilot instrumentation, M6/M7 scaffolds.
- **Fail-closed** semantics: UNKNOWN never silently becomes PASS; host exec, network isolation, and axiom closure claims are honest.

### 1.2 Longevity

Validate that the system remains correct as data and time scale:

- Schema minor bumps with historical packet reload.
- Ledger growth (10k / 100k events) without hash-chain or export regressions.
- Pinned Docker image rebuilds and Lean toolchain matrix drift.

### 1.3 Cost and efficiency

Measure and reduce operational cost without weakening security:

- Orchestration overhead vs Lean build time (§17 target: **&lt;10%**).
- Docker cold-start vs `--insecure-host-exec` tradeoffs (document when each is acceptable).
- Evidence packet size (§17: **&lt;1 MB** excluding logs).
- Pilot instrumentation overhead (§21: **&lt;10%** of expert time).

### 1.4 Non-goals (explicit)

- **§21 scientific release** (shadow pilot authorization, learned routing) — tracked as pilot/scientific layer, not blocking “engineering test-complete.”
- **Elaborator-complete Lean truth** on regex-stub path — tests assert honesty labels, not Mathlib-scale proof correctness.
- **M6 training / M7 model loops** — scaffold-only until science gates open.

---

## 2. Test pyramid

| Layer | Purpose | Target location | Approx. share | Current state |
| --- | --- | --- | --- | --- |
| **Unit** | Policy, models, pure logic, mocked I/O | `tests/unit/test_*.py` | ~65% | Strong (~201) |
| **Integration** | Real Git, subprocess, SQLite, CLI E2E, Docker optional | `tests/integration/` | ~20% | **Week 2:** git-candidate, Docker build, Lean toolchain JSON, worktree |
| **Adversarial / security** | Fuzz, injection, traversal, redaction corpus | `tests/security/` | ~5% | **Week 1:** REG suite present |
| **Property** | Hash chain, TPPR invariants, idempotent compile | `tests/property/` (new) | ~3% | Partial (`test_hashing`, `test_tppr`) |
| **Performance** | §17 budgets, benchmarks (soft 2× CI gate) | `tests/performance/` | ~3% | **Week 3:** soft budgets + `benchmarks/latest.json` |
| **Longevity** | Migrations, large ledger, historical packets | `tests/longevity/` | ~2% | **Week 4:** 10k + schema + historical; 100k `@pytest.mark.slow` |
| **Scientific (pilot)** | Frozen corpus dry-run, overhead measurement | `tests/pilot/` + `docs/pilot_dry_run.md` | ~2% | **Week 4:** dry-run only (not §21) |

**CI gating:** unit + integration smoke + security regression subset on every PR; performance/longevity on nightly or `workflow_dispatch`; Lean Docker matrix weekly.

---

## 3. Capability matrix

Priority key: **P0** = blocks engineering test-complete; **P1** = required before optional Lean repo / pilot dry-run; **P2** = cost/longevity; **P3** = nice-to-have / research-prep.

### 3.1 Contract (`lpe contract`, `src/lpe/contract/`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| `lpe contract validate` on `examples/minimal-project` | Exit 0; `"valid": true` in JSON | CLI only — `test_cli.py` | P0 |
| Negative fixtures: cyclic obligations, empty intent, missing review role, unknown downstream, unsupported schema | Each rejects with actionable error | `test_contract.py`, `test_obligations.py` | P0 |
| `lpe contract schema-check` | Exit 0 on example; exit 1 on unsupported version | `test_phase5_ops.py` | P0 |
| Migration dry-run `0.1.0` → next minor | `schema-check` documents bump path; golden contracts still load | **No integration drill** — `tests/integration/test_contract_migration.py` | P1 |
| Schema export drift | `make schemas` + `scripts/validate_examples.py` in CI | CI via `make check` | P0 |

**Target files:** `tests/integration/test_contract_cli.py`, `tests/integration/test_contract_migration.py`  
**Fixtures:** `tests/fixtures/contracts/*`, `examples/minimal-project/`

---

### 3.2 Candidate (`lpe candidate validate`, `src/lpe/git/candidate.py`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| JSON schema validation for all `examples/candidates/R*.json` | All parse; R3 matches obligation refs | `test_contract.py` partial | P0 |
| Git enrichment overrides self-declared risk | Enriched fields match `git diff` classifier | `test_phase1_trust.py` | P0 |
| Null / invalid `head_commit` rejected | `ValueError` / CLI exit 1 | `test_phase1_trust.py` | P0 |
| Path traversal in `changed_paths` / `patch_path` | Compile refuses before build | `test_phase5_ops.py` | P0 |
| Real temp-repo candidate from `git` CLI | Candidate built from actual commit range | **Week 2** — `tests/integration/test_git_candidate.py` | P1 |

**CLI:** `lpe candidate validate examples/candidates/R3-definition-change.json --project examples/minimal-project`

---

### 3.3 Evidence compile (`lpe evidence compile`, `src/lpe/evidence/compiler.py`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| Deterministic packet hash for fixed inputs (`--skip-build`) | Byte-identical JSON across two runs | `test_golden_packets.py` | P0 |
| Golden matrix: ACCEPT / REJECT / ESCALATE / skip_build honesty | Schema-valid; `hard_gate_passed` matches policy | `test_golden_packets.py` | P0 |
| Docker default; host requires `--insecure-host-exec` | Refused without flag; actionable error if no Docker | `test_phase1_trust.py` | P0 |
| `network_policy: deny` on host refused | Exit 1 with deny message | `test_phase1_trust.py`, `test_phase2_hardening.py` | P0 |
| Markdown + GitHub Check side outputs | Files written; check uses real `head_sha` | `test_reporting.py`, `test_github_check.py` | P1 |
| Full compile in Docker against mock `lake build` | Build log redacted; isolation PASS when network-none | **Week 2** — `tests/integration/test_evidence_docker_build.py` | P1 |
| Real Lean repo compile (Lake + Mathlib cache policy) | Exit 0; `lean.build` not UNKNOWN when toolchain complete | **Partial Week 2** — toolchain JSON fixture (`test_evidence_lean_repo.py`); full Lake still gap | P1 |
| Idempotent re-compile | Same packet digest | **Gap** — `tests/property/test_compile_idempotence.py` | P2 |

**CLI (smoke):**

```bash
lpe evidence compile \
  --project examples/minimal-project \
  --candidate examples/candidates/R3-definition-change.json \
  --output /tmp/packet.json \
  --skip-build \
  --markdown /tmp/packet.md
```

**Success:** exit 0; `/tmp/packet.json` validates against `schemas/evidence-packet-*.json`; size &lt; 1 MB.

---

### 3.4 Gates and risk (`src/lpe/evidence/gates.py`, `risk.py`, `router.py`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| R0–R4 risk classification matrix | Expected risk class per fixture diff | `test_risk.py`, `test_gates.py` | P0 |
| `hard_gate_passed` false when hard-relevant UNKNOWN | ESCALATE not ACCEPT | `test_phase3_kernel.py`, `test_golden_packets.py` | P0 |
| Review question priority order | Semantic before kernel when both unresolved | `test_gates.py`, `test_m6_m7_scaffold.py` | P1 |
| Placeholder / sorry / admit scan on `.lean` files | FAIL when sorry in changed file | `test_phase1_trust.py` | P0 |
| Prohibited axioms: FAIL if listed; UNKNOWN on regex-stub | Never PASS with empty `axioms_used` | `test_phase1_trust.py`, `test_phase3_kernel.py` | P0 |

---

### 3.5 Execution — sandbox, subprocess, worktree (`src/lpe/execution/`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| `build_command` allowlist (`lake`, `lean`, `elan` only) | Arbitrary shell rejected | `test_phase2_hardening.py` | P0 |
| Docker hardening flags present in invoke | `--cap-drop=ALL`, `--network=none` when deny | `test_sandbox.py` partial | P0 |
| Secret redaction in stdout/stderr | PAT/AWS/Bearer patterns `[REDACTED]` | `test_phase2_hardening.py` | P0 |
| Env denylist (`*_TOKEN`, `GITHUB_*`, `CI`, etc.) | Stripped even if allowlisted | `test_phase2_hardening.py` | P0 |
| Worktree create/cleanup; unknown commit rejected | Isolated worktree path used | **Week 2** — `test_worktree_isolation.py` (+ phase2 unit) | P1 |
| Timeout and output truncation | Deterministic failure | `test_phase2_hardening.py` | P1 |
| Docker optional skip in CI without daemon | `@pytest.mark.docker` skips cleanly | `tests/conftest.py` + `test_evidence_docker_build.py` | P1 |
| Subprocess never claims isolation PASS | `execution.isolation` = UNKNOWN | `test_sandbox.py` | P0 |

**Env knobs:** `LPE_DOCKER_IMAGE`, `LPE_DOCKER_READONLY`, `LPE_CODEOWNERS_PLACEHOLDERS_OK` (unrelated but documented).

---

### 3.6 Lean extraction (`src/lpe/lean/extractor.py`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| Impact cone direction (dependee → depender) | Hand-audited fixture membership | `test_lean_extractor.py`, `tests/fixtures/lean/impact_cone/` | P0 |
| Toolchain JSON ingest (`.lpe/lean-extraction.json`) | `complete=true` enables axiom PASS path | `test_phase3_kernel.py` | P1 |
| Regex-stub labeled; never `complete=true` | Extractor field honest | `test_lean_extractor.py` | P0 |
| Axiom fixtures Clean vs Prohibited | Correct PASS/FAIL/UNKNOWN | `tests/fixtures/lean/axioms/` | P0 |
| Large synthetic graph compile time/memory | Within budget or documented | **Gap** — `tests/performance/test_impact_cone_scale.py` | P2 |

---

### 3.7 Semantic providers (`src/lpe/providers/semantic.py`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| Missing structured fixtures → UNKNOWN not PASS | No silent pass on README-only | `test_semantic_providers.py` | P0 |
| `statement_diff`, `project_examples`, `counterexamples` | Structured fixture pass on example project | `test_semantic_providers.py` | P0 |
| `duplicate_retrieval` empty corpus → UNKNOWN | Closest-match reporting when duplicates | `test_semantic_providers.py` | P1 |
| `downstream.replacement_tests` with cone | Successor findings when cone known | `test_semantic_providers.py` | P1 |
| Provider timeout → UNKNOWN + escalate | Simulated slow provider | **Gap** — `tests/integration/test_provider_timeout.py` | P2 |

---

### 3.8 Review (`lpe review record`, `src/lpe/review/`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| Authority from `review.yaml` only | Self-declared roles ignored | `test_review.py` | P0 |
| R3/R4 ACCEPT refused via CLI (ADR 0003) | Exit 1 with policy message | `test_review.py` | P0 |
| Ledger append on successful record | Valid hash returned | `test_review.py` | P1 |
| ESCALATE / REJECT paths per risk | Correct event types | `test_review.py` | P1 |

**CLI:**

```bash
lpe review record \
  --project examples/minimal-project \
  --decision tests/fixtures/review/decision-escalate.json \
  --ledger /tmp/ledger.db \
  --risk-class R3
```

---

### 3.9 Ledger (`lpe ledger`, `src/lpe/ledger/store.py`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| init → append → verify chain | `lpe ledger verify` prints `valid` | `test_ledger.py` | P0 |
| Anonymous / empty `actor_id` rejected | CLI exit 1 | `test_phase5_ops.py` | P0 |
| `--project` enforces `project_id` match | Mismatch exit 1 | `test_phase5_ops.py` | P0 |
| Export JSONL with `previous_hash` / `event_hash`; `--verify` | Round-trip verify passes | `test_ledger.py` | P0 |
| Concurrent append (thread pool) | No chain corruption | `test_ledger.py` | P1 |
| Multi-writer crash / power-loss (WAL) | Chain intact after kill -9 mid-append | **Gap** — `tests/longevity/test_ledger_crash.py` | P2 |
| TPPR blocked when verify fails | Metric reporting refused | **Gap** — `tests/integration/test_ledger_tppr_gate.py` | P1 |

---

### 3.10 TPPR (`lpe tppr compute`, `src/lpe/metrics/tppr.py`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| Credit requires acceptance + persistence | Matrix in `test_tppr.py` | Covered | P0 |
| Rejected candidate removes credit | Numerator decreases | `test_tppr.py` | P0 |
| Expert hour categories and exclusions | Corrections recorded | `test_tppr.py` | P1 |
| End-to-end: compile → review → ledger → TPPR | Report matches fixture expectations | **Gap** — `tests/integration/test_tppr_e2e.py` | P1 |

---

### 3.11 GitHub Check (`src/lpe/github/check.py`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| Payload uses candidate `head_commit` as `head_sha` | Never `mock-sha` | `test_github_check.py` | P0 |
| ESCALATE → `failure` by default | Configurable `escalate_as` | `test_github_check.py` | P0 |
| Live API submission to throwaway repo | Check created; required-check fail-closed | Env-gated `tests/integration/test_github_check_e2e.py` + mocked `--post`; runbook `docs/github_check_e2e.md` | P2 |

---

### 3.12 Month-one gate (`lpe gate month-one`, `src/lpe/gate/month_one.py`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| All automated criteria pass on clean clone | Exit 0 in CI | `test_gate.py`, CI `lpe doctor` | P0 |
| Fails when example contract broken | Exit 1 lists criterion | **Gap** — `tests/integration/test_month_one_gate_fail.py` | P1 |
| Does **not** imply production / §21 clearance | Documented in test docstrings | `docs/month_one_gate.md` | P0 |

**CLI:** `lpe gate month-one --repo .` → exit 0 on main.

---

### 3.13 Pilot (`src/lpe/pilot/`)

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| In-memory scratch + durable warehouse; automation rate | `test_pilot.py`, `test_pilot_warehouse.py` | Covered | P1 |
| Overhead within 10% budget helper | `OverheadReport.within_budget` | `test_pilot.py` | P1 |
| Ledger-backed summary / CLI | `lpe pilot record|summary` | `test_pilot_warehouse.py` | P1 |
| Frozen corpus dry-run: warehouse → TPPR report | Reproducible report JSON+MD | `tests/pilot/test_frozen_corpus_dry_run.py` | P2 |
| Optional ledger snapshot with real `actor_id` | Events appended; verify passes | `test_phase5_ops.py` | P1 |

---

### 3.14 M6 routing / M7 synthesis scaffolds

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| Deterministic routing baseline ordering | `test_m6_m7_scaffold.py` | Covered | P2 |
| Synthesis harness `fixture_harness_ok` not science gate | No `gate_passed`; training blocked message | `test_m6_m7_scaffold.py` | P2 |
| No training loops invoked | Import/run does not touch model weights | **Gap** — static / smoke test | P3 |

---

### 3.15 CLI doctor and tooling

| What to test | Pass criteria | Coverage gap | Pri |
| --- | --- | --- | --- |
| `lpe doctor` | Exit 0; reports version | `test_cli.py`, CI | P0 |
| `scripts/verify_clean_clone.py` | Pass on fresh checkout | **Gap** — CI optional job | P2 |
| `scripts/check_codeowners_placeholders.py` | Warn with `LPE_CODEOWNERS_PLACEHOLDERS_OK=1` | CI step | P1 |

---

## 4. Security regression suite (AUDIT-001..032)

Legend: **P1–5** = covered by Phase 1–5 unit tests; **CI** = enforced in workflow; **REG** = needs ongoing regression test; **DOC** = process/documentation gate.

| ID | Topic | Phase coverage | Ongoing regression target |
| --- | --- | --- | --- |
| AUDIT-001 | Docker default; host exec opt-in | P1 `test_phase1_trust.py` | REG: `tests/security/test_execution_defaults.py` |
| AUDIT-002 | Review authority from `review.yaml` | P1 `test_review.py` | REG |
| AUDIT-003 | Axiom gate honesty (regex-stub) | P1/P3 `test_phase1_trust.py`, `test_phase3_kernel.py` | REG |
| AUDIT-004 | Git revision verification | P1 `test_phase1_trust.py` | REG |
| AUDIT-005 | `build_command` allowlist | P2 `test_phase2_hardening.py` | REG + fuzz `tests/security/test_build_command_fuzz.py` |
| AUDIT-006 | Docker sandbox hardening; isolation honesty | P2 `test_phase2_hardening.py`, `test_sandbox.py` | REG + Docker invoke inspection |
| AUDIT-007 | Secret redaction | P2 `test_phase2_hardening.py` | REG + expanded corpus `tests/security/test_redaction_corpus.py` |
| AUDIT-008 | Env denylist | P2 `test_phase2_hardening.py` | REG |
| AUDIT-009 | R3/R4 ACCEPT refused | P1 `test_review.py` | REG |
| AUDIT-010 | Semantic providers heuristic-complete | P3 `test_semantic_providers.py` | REG |
| AUDIT-011 | Lean extraction protocol / JSON ingest | P3 `test_lean_extractor.py` | REG + toolchain integration |
| AUDIT-012 | Impact cone direction | P3 `test_lean_extractor.py` | REG |
| AUDIT-013 | Month-one gate real validation | P5 `test_gate.py` | REG |
| AUDIT-014 | Worktree CLI wiring | P2 `test_phase2_hardening.py` | REG integration |
| AUDIT-015 | Git enrichment overrides metadata | P1 `test_phase1_trust.py` | REG |
| AUDIT-016 | Placeholder scan on `.lean` files | P1 `test_phase1_trust.py` | REG |
| AUDIT-017 | Ledger actor_id; export verify | P5 `test_ledger.py`, `test_phase5_ops.py` | REG + longevity |
| AUDIT-018 | GitHub Check `head_sha`; ESCALATE fail-closed | P1 `test_github_check.py` | REG |
| AUDIT-019 | `network_policy: deny` enforcement | P2 `test_phase2_hardening.py` | REG |
| AUDIT-020 | `hard_gate_passed` vs UNKNOWN | P3 `test_phase3_kernel.py`, `test_golden_packets.py` | REG |
| AUDIT-021 | Honest capability matrix in validation docs | DOC | REG: doc drift check in release checklist |
| AUDIT-022 | CODEOWNERS placeholder fail-closed | CI script (warn mode) | REG: flip to FAIL when owners land |
| AUDIT-023 | Pilot warehouse durable; legacy in-memory snapshot | `test_pilot_warehouse.py`, P5 `test_phase5_ops.py` | REG |
| AUDIT-024 | Pinned Actions SHAs | CI | REG: Dependabot + periodic SHA review |
| AUDIT-025 | Path traversal | P5 `test_phase5_ops.py` | REG + fuzz Unicode/NTFS `tests/security/test_path_traversal_fuzz.py` |
| AUDIT-026 | `contract schema-check` / migration | P5 `test_phase5_ops.py` | REG + migration drill |
| AUDIT-027 | Execution unit test bundle | P2 `test_phase2_hardening.py` | REG |
| AUDIT-028 | Supply-chain / dependency audit | CI `pip-audit` | REG: baseline review quarterly |
| AUDIT-029 | Golden packet matrix | `test_golden_packets.py` | REG on schema change |
| AUDIT-030 | Ledger export hash round-trip | `test_ledger.py` | REG + 10k/100k scale |
| AUDIT-031 | M6/M7 gate-blocked | `test_m6_m7_scaffold.py` | REG |
| AUDIT-032 | Validation report honesty | DOC | REG: update `VALIDATION_REPORT.md` each release |

**Security PR gate (Week 1):** run `tests/unit/test_phase{1,2,3,5}_*.py` + new `tests/security/` smoke on every PR (~60+ tests).

---

## 5. Performance and cost

### 5.1 Budgets (ENGINEERING_SPEC §17)

| Metric | Target | Measurement method | Test target |
| --- | --- | --- | --- |
| Contract validation | &lt; 1 s | `time lpe contract validate` | `tests/performance/test_contract_latency.py` |
| Diff classification | &lt; 5 s (normal PR) | Git enrich + classify on fixture repo | `tests/performance/test_diff_classification.py` |
| Orchestration overhead | &lt; 10% of Lean build | `(lpe_wall - lean_wall) / lean_wall` | `tests/performance/test_orchestration_overhead.py` |
| Evidence packet size | &lt; 1 MB (excl. logs) | `len(packet_json)` | `tests/performance/test_packet_size.py` |
| Ledger append | &lt; 100 ms | `LedgerStore.append` p95 | `tests/performance/test_ledger_append.py` |
| Review packet generation | &lt; 30 s after evidence | compile + markdown | `tests/performance/test_review_packet_latency.py` |

Record results in `benchmarks/results/` (JSON); fail nightly only on **&gt;2×** regression vs baseline commit.

### 5.2 Metrics to collect

- Wall time per CLI subcommand (doctor, validate, compile, ledger, tppr).
- Docker: image pull time, container create, bind-mount overhead, `--network=none` vs default.
- Packet: JSON bytes, finding count, log truncation bytes.
- Ledger: SQLite file size, append latency p50/p95, export wall time, verify wall time.
- Pilot: `OverheadReport.overhead_fraction` on scripted sessions.

### 5.3 Cost-reduction experiments

| Experiment | Hypothesis | Success threshold |
| --- | --- | --- |
| Skip Docker when `--skip-build` only | Zero container cost for policy-only runs | No isolation PASS claimed |
| Mathlib cache in Lean integration job | &gt;50% Lean wall-time reduction | Document in `VALIDATION_REPORT.md` |
| Lean extraction JSON cache (`.lpe/lean-extraction.json`) | Reuse across re-compiles | Second compile ≥30% faster orchestration |
| Ledger batch append API (if added) | Lower per-event SQLite fsync | p95 append &lt; 50 ms at 10k events |
| Truncate build logs earlier | Smaller packets | Stay &lt; 1 MB with 10× log volume fixture |

---

## 6. Longevity

| Drill | Procedure | Pass criteria | Target file |
| --- | --- | --- | --- |
| Schema migration | Bump minor in test fixture; run `lpe contract schema-check`; load historical golden packets from `schemas/` | All historical packets validate or documented migration | **Week 4** `tests/longevity/test_schema_migration.py` |
| Ledger 10k events | Append scripted events; verify + export --verify | Verify &lt; 30 s; chain valid | **Week 4** `tests/longevity/test_ledger_10k.py` |
| Ledger 100k events | Nightly only; sample verify every 10k | Export completes &lt; 5 min | **Week 4** `tests/longevity/test_ledger_100k.py` (`@pytest.mark.slow`) |
| Historical packet load | Save packet JSON; reload/validate after delay | Parse + schema validate | **Week 4** `tests/longevity/test_historical_packets.py` |
| Docker image pin rebuild | Rebuild `LPE_DOCKER_IMAGE` from pin file; run sandbox smoke | Same isolation flags; build succeeds | Deferred (optional) |
| Retention prototype | Export → verify → archive; never rewrite live chain | Documented in test; no chain break | Covered via 10k export path; dedicated retention deferred |

---

## 7. Environments

### 7.1 Local (developer)

- Python 3.12, `pip install -e ".[dev]"`, `make check`.
- Docker Desktop optional; tests marked `@pytest.mark.docker` skip if unavailable.
- Git required for worktree / enrichment integration tests.

### 7.2 CI (`.github/workflows/ci.yml`)

- Ubuntu latest; `make check`, `lpe doctor`, `pip-audit`, CODEOWNERS script (warn).
- **Add:** integration job (no Docker) + optional `docker` job matrix.

### 7.3 Lean Docker matrix (`.github/workflows/lean-integration-template.yml`)

- `workflow_dispatch` weekly + pre-release.
- `leanprover/lean-action` with `use-mathlib-cache: auto`.
- Steps: validate example contract → `lpe evidence compile` without `--skip-build` on pinned Mathlib-lite fixture (to be added under `tests/fixtures/lean/repos/`).

### 7.4 Optional real Lean repo fixture

- Submodule or cached tarball of a **small** pinned Lean project (not full Mathlib).
- Read-only mirror; no network in compile except Mathlib cache step in CI only.
- Success: `lean.build` PASS, extraction JSON `complete=true` when Lake plugin emits it.

---

## 8. Execution schedule (4 weeks)

### Week 1 — Smoke + security regression — **DONE 2026-07-16**

| Day | Work |
| --- | --- |
| 1–2 | Create `tests/integration/conftest.py` (temp git repo, ledger tmp paths). Port CLI smokes from backlog. |
| 3 | Add `tests/security/test_path_traversal_fuzz.py`, `test_redaction_corpus.py` (P0 fuzz cases). |
| 4 | Security regression job: phase1/2/3/5 + security; document AUDIT matrix in CI summary. |
| 5 | `lpe gate month-one` + full `pytest -q` green; update `VALIDATION_REPORT.md` test count. |

**Exit:** All P0 unit tests + security smoke green; integration directory exists with ≥5 tests. **Met** (303 passed; see `docs/23_TEST_EXECUTION_LOG.md`).

### Week 2 — Integration + Lean — **DONE 2026-07-16**

| Day | Work |
| --- | --- |
| 1–2 | `tests/integration/test_git_candidate.py`, worktree isolation under compile. |
| 3 | Docker-marked `test_evidence_docker_build.py` (ubuntu image + allowlisted `lean`). |
| 4–5 | Toolchain JSON fixture + `test_evidence_lean_repo.py`; Lean template workflow wired to fixture job. |

**Exit:** E2E git enrich path; Docker build smoke OR documented skip; Lean toolchain ingest without requiring Lake in default CI. **Met** (328 passed; see `docs/23_TEST_EXECUTION_LOG.md`).

### Week 3 — Performance + cost — **DONE 2026-07-16**

| Day | Work |
| --- | --- |
| 1–2 | `tests/performance/` harness + baseline JSON commit. |
| 3 | Orchestration overhead experiment (Docker vs skip-build). |
| 4 | Packet size + ledger append benchmarks. |
| 5 | Cost decision doc section in `VALIDATION_REPORT.md`. |

**Exit:** Baselines recorded; no §17 budget exceeds 2× on reference hardware. **Met** (342 passed; see `docs/23_TEST_EXECUTION_LOG.md`, `docs/benchmarks/week3_baseline.md`).

### Week 4 — Longevity + pilot dry-run — **DONE 2026-07-16**

| Day | Work |
| --- | --- |
| 1–2 | `tests/longevity/test_ledger_10k.py`, `test_schema_migration.py`. |
| 3 | Historical packet + streaming export/verify; optional 100k `@pytest.mark.slow`. |
| 4 | `tests/pilot/test_frozen_corpus_dry_run.py` + `docs/pilot_dry_run.md`. |
| 5 | Full suite + §9.1 engineering test-complete decision. |

**Exit:** Longevity smokes pass; pilot dry-run produces TPPR report artifact. **Met** (352 passed; see `docs/23_TEST_EXECUTION_LOG.md`, `docs/benchmarks/week4_longevity.md`). Docker pin rebuild / crash-WAL remain optional deferred drills.

---

## 9. Exit criteria

### 9.1 Engineering “test-complete” (version 0.1.x)

All must be true:

1. **≥250 automated tests** (unit + integration + security), `pytest -q` green in CI.
2. **P0 capability matrix** rows have explicit test coverage (no “Gap” without waived rationale).
3. **AUDIT-001..032** each mapped to a passing REG test or CI/DOC control.
4. **Integration path:** `evidence compile` → `review record` → `ledger verify` → `tppr compute` on fixture data.
5. **§17 performance baselines** recorded; no metric &gt;2× budget on reference runner.
6. **Longevity:** 10k ledger + schema migration drill pass.
7. **`VALIDATION_REPORT.md`** updated with honest “what works / does not work.”
8. **Month-one gate** exit 0 on clean clone CI.

### 9.2 Still research-gated (NOT implied by test-complete)

- §21 shadow pilot authorization (80% automation, 90% reproduction, reviewer comprehension).
- Elaborator-complete Lean evidence at Mathlib scale.
- M6 learned routing / M7 training loops.
- Production ACCEPT for R3/R4.
- WORM / tamper-evident ledger root of trust.
- Live GitHub Check on partner repos without throwaway credentials.

---

## 10. Open risks and blockers

| Risk | Impact | Mitigation in test plan |
| --- | --- | --- |
| **CODEOWNERS `REPLACE_WITH_*` placeholders** | Merge fail-closed blocked (AUDIT-022) | CI warn until owners land; test flip to FAIL |
| **No elaborator / regex-stub only** | Axiom and impact cones heuristic | Tests assert `toolchain_backed: false`; never claim PASS on incomplete extraction |
| **Docker absent on some dev/CI runners** | Lean build path untested | `pytest.mark.docker` skip + explicit gap in `VALIDATION_REPORT.md` |
| **No default Lean CI job** | Real `lake build` rarely exercised | Week 2 template workflow + optional fixture |
| **Ledger on local FS (not WORM)** | Host compromise undetected | Tabletop test documented; export-verify REG |
| **Partner pilot not run** | No human expert / protocol freeze | Warehouse ready; §21 still gated |
| **M6/M7 science gates** | Premature training claims | `fixture_harness_ok` naming; static no-training test |
| **GitHub live check** | API flake / secret handling | P2 throwaway repo; skip in default CI |
| **pytest-asyncio deprecation warning** | Future CI noise | Set `asyncio_default_fixture_loop_scope` in `pyproject.toml` when async tests land |

---

## Appendix A — Proposed directory layout (new tests)

```
tests/
  conftest.py                    # extend: docker marker, git repo, ledger_path
  integration/
    conftest.py
    test_contract_cli.py
    test_contract_migration.py
    test_git_candidate.py
    test_evidence_cli_e2e.py
    test_evidence_docker_build.py
    test_evidence_lean_repo.py
    test_ledger_tppr_gate.py
    test_tppr_e2e.py
    test_month_one_gate_fail.py
    test_provider_timeout.py
    test_github_check_live.py      # optional secrets
  security/
    test_path_traversal_fuzz.py
    test_build_command_fuzz.py
    test_redaction_corpus.py
    test_execution_defaults.py
  property/
    test_compile_idempotence.py
    test_hash_chain_properties.py
  performance/
    test_contract_latency.py
    test_ledger_append.py
    test_packet_size.py
    test_orchestration_overhead.py
  longevity/
    test_ledger_10k.py
    test_ledger_100k.py
    test_schema_migration.py
    test_historical_packets.py
    test_docker_image_rebuild.py
    test_ledger_retention.py
    test_ledger_crash.py
  pilot/
    test_frozen_corpus_dry_run.py
```

## Appendix B — Quick verification commands

```bash
# Current baseline
pytest -q

# Month-one + doctor
lpe gate month-one --repo .
lpe doctor

# Schema + examples
make schemas
python scripts/validate_examples.py

# Security subset (after Week 1)
pytest -q tests/unit/test_phase1_trust.py tests/unit/test_phase2_hardening.py \
  tests/unit/test_phase3_kernel.py tests/unit/test_phase5_ops.py
```

---

*See also:* [21_TEST_BACKLOG.md](21_TEST_BACKLOG.md) (remaining items fed into this plan), [10_TESTING_AND_VALIDATION.md](10_TESTING_AND_VALIDATION.md), [ENGINEERING_SPEC.md](ENGINEERING_SPEC.md) §17/§20/§21.
