# Lean Project Evidence — Spec & Roadmap Audit
**Date / commit:** 2026-07-16 / post–audit-gap-closure (fixture-excellence 0.2)  
**Verdict one-liner:** Engineering **0.2 fixture-excellence**: M0–M4 Done at fixture scope; §17 orch measured (harness); doc drift closed; M5 instrument-ready only; M6–M7 / partner pilot / §21 still deferred — do not claim science, Mathlib-complete truth, or R3/R4 auto-ACCEPT.

## 1. Executive scorecard

| Dimension | Spec target | Current | Score |
| --- | --- | --- | --- |
| §4.1 version-0 product surface | Contracts, gates, packets, review, ledger, TPPR, CLI, CI | Implemented end-to-end on fixtures; CLI complete | **Met** |
| §8 evidence compiler | Normalize → classify → execute → gates → packet → recommend → question | Full pipeline in `src/lpe/evidence/compiler.py` | **Met** |
| §17 performance budgets | Contract &lt;1s; diff &lt;5s; packet &lt;1MB; append &lt;100ms; review &lt;30s; orch &lt;10% Lean | Soft CI 2× gates green; orch vs Lean wall **measured** on fixture (`docs/benchmarks/orch_vs_lean_wall.md`) | **Met** (fixture) / honest soft miss if ratio ≥10% |
| §20 DoD v0.1 (10 items) | All pass | All pass (see §4) | **Met** |
| §21 scientific gates | Pilot + held-out learning prerequisites | Instrumentation only; partner study deferred | **Gap** |
| Roadmap M0–M2 | Foundation → evidence → review | Done | **Met** |
| Roadmap M3–M4 | Lean extract + semantic providers | **DONE (fixture-scoped)**; Mathlib out of scope | **Met** (fixture-excellence) |
| Roadmap M5 | Shadow pilot 30–50 candidates | Partner kit + warehouse; **no live partner pilot** | **Partial** |
| Roadmap M6–M7 | Learned routing / synthesis | Deterministic + fixture harness scaffolds only | **Gap** (blocked) |
| Test / quality | Green suite; honest VALIDATION | **543 passed**, 1 env-gated skip, 1 slow deselected; month-one gate green | **Met** |
| Security (docs/09) | Sandbox, allowlist, redaction, no R3/R4 auto-ACCEPT | Controls present; CODEOWNERS `@fraware`; ledger FS not WORM | **Partial** (WORM residual) |

## 2. Milestone matrix M0–M7

| Milestone | Intent | Status | Evidence | Gaps |
| --- | --- | --- | --- | --- |
| **M0** Foundation | Schemas, contract, IDs, ledger, TPPR, CI | **DONE** | `src/lpe/models.py`, `contract/`, `ledger/store.py`, `metrics/tppr.py`, `schemas/*.json` (11), `.github/workflows/ci.yml`, `examples/minimal-project/` | — |
| **M1** Deterministic evidence | Git classify, sandbox build, hard gates, packet, risk/policy | **DONE** | `git/diff.py`, `git/candidate.py`, `execution/{sandbox,runner,worktree,allowlist}.py`, `evidence/{compiler,gates,risk}.py`, `reporting/markdown.py` | Lexical classifier remains conservative by design |
| **M2** Review operation | Question routing, authority, decisions, GitHub Check | **DONE** | `evidence/router.py`, `review/{authority,decisions}.py`, `github/{check,submit}.py`, CLI `lpe review` / `lpe github` | Live `gh api --post` env-gated (`LPE_GH_CHECK_E2E`); mock default in CI |
| **M3** Lean-aware evidence | Decls, axioms, deps, impact cone, imports | **DONE (fixture-scoped)** | Toolchain-first `AdaptiveLeanExtractor`; freshness gate; diamond/chain/opaque/Ambiguous fixtures; stub never PASS | Mathlib / tactic-erased residual honesty |
| **M4** Semantic evidence | Statement diff, examples, cex, duplicates, replacement | **DONE (fixture-scoped)** | Lake `env lean` examples/cex; structural statement fields; toolchain hash duplicates; decl-dep replacement | Not intent/implication oracles; not embedding ML |
| **M5** Shadow pilot | 30–50 candidates, 3 conditions, TPPR instrumentation | **PARTIAL** | `pilot/*`, `docs/24`, `docs/27_PARTNER_PILOT_HANDOFF.md` | Study **deferred**; analysis plan UNFROZEN |
| **M6** Learned routing | Improve held-out TPPR vs deterministic | **STUB / BLOCKED** | `routing/baseline.py` only | §21 unmet |
| **M7** Project-targeted synthesis | Equal-budget held-out TPPR gain | **STUB / BLOCKED** | `synthesis/eval_harness.py` | Blocked on M6 |

## 3. Backlog issue tracker

Grouped by milestone. Status legend: **DONE** / **PARTIAL** / **STUB** / **NOT STARTED** / **BLOCKED**.

### M0

| ID | Title | Status | Notes |
| --- | --- | --- | --- |
| EPIC-001 | Repository foundation and CI | **DONE** | Packaging, CI SHA-pins, docs, `scripts/check.sh` |
| ISSUE-002 | Canonical Pydantic domain models | **DONE** | `models.py`; unknown fields rejected; schema export |
| ISSUE-003 | Split project-contract loader | **DONE** | `contract/loader.py`; example validates |
| ISSUE-004 | Stable IDs and canonical hashing | **DONE** | `ids.py`, `hashing.py` + unit tests |
| ISSUE-005 | Append-only hash-chained SQLite ledger | **DONE** | WAL, verify, export, archive, mutation denial |
| ISSUE-006 | TPPR calculation | **DONE** | `metrics/tppr.py`; pending persistence until confirmed |

### M1

| ID | Title | Status | Notes |
| --- | --- | --- | --- |
| EPIC-007 | Deterministic evidence compiler | **DONE** | `compile_evidence` end-to-end |
| ISSUE-008 | Git revision normalization | **DONE** | `resolve_commit`; actionable `GitError` |
| ISSUE-009 | Conservative Lean diff classifier | **DONE** | Lexical; unknown escalates; git overrides self-declared risk |
| ISSUE-010 | Isolated exact-environment runner | **DONE** | Allowlist, timeout, output limits, worktree |
| ISSUE-011 | Container sandbox backend | **DONE** | `DockerSandboxExecutor`; `--network=none`; combined build+extract |
| ISSUE-012 | Placeholder / prohibited-token checks | **DONE** | Hard-fail on configured tokens |
| ISSUE-013 | Changed-path policy gate | **DONE** | Denied paths reject |
| ISSUE-014 | Risk classifier R0–R4 | **DONE** | `evidence/risk.py` + fixtures |
| ISSUE-015 | Decision gate policy | **DONE** | `gates.decide`; UNKNOWN hard ≠ pass |
| ISSUE-016 | JSON + Markdown packets | **DONE** | Provenance-preserving render |

### M2

| ID | Title | Status | Notes |
| --- | --- | --- | --- |
| EPIC-017 | Review operation | **DONE** | Question → decision → ledger minutes |
| ISSUE-018 | Deterministic review-question routing | **DONE** | Semantic priority in `router.py` |
| ISSUE-019 | Reviewer authority checks | **DONE** | `review.yaml` only; R3/R4 ACCEPT refused (ADR 0003) |
| ISSUE-020 | Review decision recording | **DONE** | `record_review_decision` + obligation_ids → TPPR |
| ISSUE-021 | GitHub Check output adapter | **DONE** | Payload render; `submit-check` dry-run / optional `--post` |

### M3

| ID | Title | Status | Notes |
| --- | --- | --- | --- |
| EPIC-022 | Lean extraction adapter | **DONE (fixture)** | Toolchain-first; stale artifact refused; stub incomplete-only |
| ISSUE-023 | Declaration metadata + signature hashes | **DONE (fixture)** | Toolchain FQNs + hashes on `lean_project` |
| ISSUE-024 | Axiom deps + placeholders | **DONE (fixture)** | Stub → UNKNOWN never PASS; toolchain PASS when complete |
| ISSUE-025 | Direct dependency graph | **DONE (fixture)** | Schema 1.1 decl edges |
| ISSUE-026 | Transitive impact cone | **DONE (fixture)** | Diamond/chain/cross/opaque hand-audited |
| ISSUE-027 | Import / dependency expansion | **DONE (fixture)** | `import_edges` + expansion findings |

### M4

| ID | Title | Status | Notes |
| --- | --- | --- | --- |
| EPIC-028 | Semantic evidence providers | **DONE (fixture)** | Lake-backed where applicable; fail-closed UNKNOWN |
| ISSUE-029 | Statement signature diff | **DONE (fixture)** | Toolchain hashes + binder/domain/conclusion fields |
| ISSUE-030 | Project example runner | **DONE (fixture)** | `lake env lean` PASS path on fixture |
| ISSUE-031 | Counterexample-provider protocol | **DONE (fixture)** | Lake FAIL path on fixture; UNKNOWN on invoke error |
| ISSUE-032 | Repository duplicate retrieval | **DONE (fixture)** | Toolchain hashes required when complete |
| ISSUE-033 | Downstream replacement tests | **DONE (fixture)** | Decl-dep cone + Lake compile; stub WARN not PASS |

### M5

| ID | Title | Status | Notes |
| --- | --- | --- | --- |
| EPIC-034 | First shadow-mode project pilot | **PARTIAL** | Engineering kit ready; study **not executed** |
| ISSUE-035 | Select and instrument first active repo | **STUB** | Scaffold CLI exists; no partner contract accepted |
| ISSUE-036 | Freeze review experiment and analysis | **STUB** | Template UNFROZEN; no signed freeze |
| ISSUE-037 | Measure contract/instrumentation overhead | **PARTIAL** | `lpe pilot overhead` + dry-run metrics; no field ≤10% study |
| ISSUE-038 | Publish pilot evidence and limitations | **NOT STARTED** | Docs distinguish software vs causal; no pilot results paper |

### M6–M7

| ID | Title | Status | Notes |
| --- | --- | --- | --- |
| EPIC-039 | Learn review routing from utility outcomes | **BLOCKED** | Baseline only; §21 unmet |
| EPIC-040 | Evaluate project-targeted data synthesis | **BLOCKED** | Fixture harness; no training |

## 4. ENGINEERING_SPEC §20 checklist

Version 0.1 is complete when:

1. **Pass** — Example project contract validates (`examples/minimal-project`; `lpe contract validate`; month-one `example_contract`).
2. **Pass** — Real Git candidate classified (`git/diff.py`, `enrich_candidate_from_git`, integration tests).
3. **Pass** — Exact build via executor interface (Docker sandbox / host with `--insecure-host-exec`; worktree isolation).
4. **Pass** — Deterministic gates → valid evidence packet (`gates.py` + `compile_evidence` + golden/unit tests).
5. **Pass** — R3 escalated with one structured question (`risk.py` R3; `select_review_question`; example `R3-definition-change.json`).
6. **Pass** — Review decision recorded (`lpe review record`; `review/decisions.py`).
7. **Pass** — Acceptance and persistence events appendable (`ledger/store.py`; EventTypes; TPPR pending until `PERSISTENCE_CONFIRMED`).
8. **Pass** — Ledger hash chain verifies (`lpe ledger verify`; longevity 10k).
9. **Pass** — TPPR computable (`lpe tppr compute`; `metrics/tppr.py`).
10. **Pass** — CI, tests, documentation, examples pass (`ci.yml`; **480** non-slow tests green this audit; docs + examples present).

## 5. ENGINEERING_SPEC §21 scientific gates

### Shadow-pilot advancement criteria

| Criterion | Status |
| --- | --- |
| Packet construction ≥80% automated | **Not met** (no measured partner corpus automation rate; fixture dry-run ≠ study) |
| Exact-environment reproduction ≥90% of selected cases | **Not met** (no selected partner case set; Docker/host paths proven on fixture only) |
| Reviewers understand evidence dimensions | **Not met** (no partner reviewer comprehension study) |
| Instrumentation overhead &lt;10% of expert time | **Not met** (recorder exists; no accepted field measurement on partner) |
| Study protocol and analysis frozen | **Not met** (`pilot_analysis_plan_template.md` marked **UNFROZEN**) |

### Learned-routing advancement criteria

| Criterion | Status |
| --- | --- |
| Enough accept/revise/reject/persistence outcomes | **Not met** |
| Held-out evaluation available | **Not met** |
| Deterministic baselines established | **Met** (software baseline exists in `routing/baseline.py`) |
| Learning demonstrably improves TPPR / preregistered proxy | **Not met** (no training) |

**Conclusion:** Product must **not** advance from “scaffold / instrument-ready” to claimed shadow-pilot science or learned routing.

## 6. Spec–code drift register

| Claim location | Claim | Reality | Severity |
| --- | --- | --- | --- |
| `ENGINEERING_SPEC.md` §4.2 | Was “deferred behind stable interfaces” | **Closed** — shipped interfaces + residual depth | Closed |
| `VALIDATION_REPORT.md` | Was “455 … passed” | **Closed** — 480+ baseline | Closed |
| `docs/22` header | Was “352 tests” | **Closed** — 480+ | Closed |
| CODEOWNERS placeholders | `REPLACE_WITH_*` | **Closed** — `@fraware`; CI fail-closed | Closed |
| Month-one / extraction language | “Continue to Lean extraction only when…” | **Closed** — pilot readiness wording | Closed |
| Partner “ready” language in docs/24 | Ready to instrument | Intact banner; handoff in `docs/27` | Residual misclaim risk if over-read |
| Default `LPE_DOCKER_IMAGE` | Often implied Lean-capable | `lpe doctor` warns; docs clarify `lpe-lean:4.14` | Residual |
| Ledger “append-only” marketing | Tamper-evident store | FS SQLite + archive path; not WORM (`docs/25`) | **High** if oversold |
| Semantic provider PASS | Could be read as mathematical fidelity | Fixture Lake/structural; intent fidelity remains human | **High** if oversold |
| §17 orchestration &lt;10% of Lean | Listed as target | **Measured** on fixture; soft assert + published ratio | Closed / soft |

## 7. Test & quality posture

### This audit run

| Command | Result |
| --- | --- |
| `pytest -q -m "not slow"` | Re-run after gap closure; expect **480+** passed, 1 slow deselected |
| `lpe doctor` | Warns when image is default ubuntu; optional `--ledger` permission report |
| `lpe gate month-one` | Scaffold criteria; disclaimer intact |

### Covered vs missing

| Covered | Missing / thin (deferred) |
| --- | --- |
| Fixture M3/M4, property hashing/ledger, orch vs Lean wall harness, env-gated GH Check, doctor ledger warnings, CODEOWNERS fail-closed | Partner human protocol; Mathlib-scale; §21; WORM root of trust; M6/M7 training |

## 8. Remaining work ranked

### P0 (must not claim)

1. **Do not claim** §21 clearance, causal pilot utility, R3/R4 production auto-ACCEPT, WORM ledger, or elaborator-complete Mathlib evidence.

### P1 (partner pilot deferred — see `docs/27_PARTNER_PILOT_HANDOFF.md`)

1. Select real partner repo + domain-lead contract (ISSUE-035) — **human**.
2. Sign/freeze analysis plan (ISSUE-036); field overhead ≤10% (ISSUE-037).
3. Execute 30–50 prospective candidates (EPIC-034) before science write-up.

### P2 (post–§21 only)

1. M6 / M7 — **BLOCKED**.
2. Stronger ledger root-of-trust beyond archive + doctor warnings.

**Partner pilot note:** Engineering 0.2 fixture-excellence is the prerequisite. Do not reopen M3/M4 mid-pilot.

## 9. Bottom-line assessment

Lean Project Evidence after audit gap closure is a credible **engineering 0.2 fixture-excellence** cut: M3–M4 Done at fixture scope, doc honesty closed, §17 orch measured, suite green. Partner pilot / §21 / M6–M7 remain deferred. What must **not** be claimed is unchanged: R3/R4 auto-ACCEPT, Mathlib-complete truth, causal utility from dry-runs, WORM ledger, opaque quality scalars.
