# Lean Project Evidence — Spec & Roadmap Audit
**Date / commit:** 2026-07-16 / `91d85cf` (`main` @ `origin` https://github.com/fraware/lean-project-evidence.git)  
**Verdict one-liner:** Engineering scaffold `0.1.0` meets ENGINEERING_SPEC §20 and plan §9.1; M0–M2 done, M3–M4 fixture-complete with heuristic residual, M5 instrument-ready only, M6–M7 gate-blocked — do not claim §21 science, production ACCEPT, or Mathlib-scale elaborator truth.

## 1. Executive scorecard

| Dimension | Spec target | Current | Score |
| --- | --- | --- | --- |
| §4.1 version-0 product surface | Contracts, gates, packets, review, ledger, TPPR, CLI, CI | Implemented end-to-end on fixtures; CLI complete | **Met** |
| §8 evidence compiler | Normalize → classify → execute → gates → packet → recommend → question | Full pipeline in `src/lpe/evidence/compiler.py` | **Met** |
| §17 performance budgets | Contract &lt;1s; diff &lt;5s; packet &lt;1MB; append &lt;100ms; review &lt;30s; orch &lt;10% Lean | Soft CI 2× gates green; orch vs Lean wall **not measured** | **Partial** |
| §20 DoD v0.1 (10 items) | All pass | All pass (see §4) | **Met** |
| §21 scientific gates | Pilot + held-out learning prerequisites | Instrumentation only; no partner study / freeze / held-out | **Gap** |
| Roadmap M0–M2 | Foundation → evidence → review | Done | **Met** |
| Roadmap M3–M4 | Lean extract + semantic providers | Toolchain path on fixture; regex-stub + heuristics otherwise | **Partial** |
| Roadmap M5 | Shadow pilot 30–50 candidates | Partner kit + warehouse; **no live partner pilot** | **Partial** |
| Roadmap M6–M7 | Learned routing / synthesis | Deterministic + fixture harness scaffolds only | **Gap** (blocked) |
| Test / quality | Green suite; honest VALIDATION | **480 passed**, 1 slow deselected; month-one gate green | **Met** |
| Security (docs/09) | Sandbox, allowlist, redaction, no R3/R4 auto-ACCEPT | Controls present; CODEOWNERS placeholders; ledger FS not WORM | **Partial** |

## 2. Milestone matrix M0–M7

| Milestone | Intent | Status | Evidence | Gaps |
| --- | --- | --- | --- | --- |
| **M0** Foundation | Schemas, contract, IDs, ledger, TPPR, CI | **DONE** | `src/lpe/models.py`, `contract/`, `ledger/store.py`, `metrics/tppr.py`, `schemas/*.json` (11), `.github/workflows/ci.yml`, `examples/minimal-project/` | CODEOWNERS still `REPLACE_WITH_*` |
| **M1** Deterministic evidence | Git classify, sandbox build, hard gates, packet, risk/policy | **DONE** | `git/diff.py`, `git/candidate.py`, `execution/{sandbox,runner,worktree,allowlist}.py`, `evidence/{compiler,gates,risk}.py`, `reporting/markdown.py` | Lexical classifier remains conservative by design |
| **M2** Review operation | Question routing, authority, decisions, GitHub Check | **DONE** | `evidence/router.py`, `review/{authority,decisions}.py`, `github/{check,submit}.py`, CLI `lpe review` / `lpe github` | Live `gh api --post` to real repo not in default CI |
| **M3** Lean-aware evidence | Decls, axioms, deps, impact cone, imports | **PARTIAL** | `lean/extractor.py`, `lean/toolchain.py`, `LpeExtract.lean`, `tests/fixtures/lean_project/`, `@pytest.mark.lean` E2E, Docker `lpe-lean:4.14` | Regex-stub path incomplete; no Mathlib; opaque/tactic residual honesty |
| **M4** Semantic evidence | Statement diff, examples, cex, duplicates, replacement | **PARTIAL** | `providers/semantic.py` (heuristic + `toolchain_backed`); replacement via cone + optional `lake env lean` | Not elaborator/intent oracles; examples/cex not executed in Lean |
| **M5** Shadow pilot | 30–50 candidates, 3 conditions, TPPR instrumentation | **PARTIAL** | `pilot/*`, `docs/24_PARTNER_PILOT_READY.md`, `lpe pilot {init-partner,record,summary,dry-run,overhead}`, frozen-corpus dry-run tests | No partner repo selected/signed; no 30–50 prospective study; analysis plan UNFROZEN |
| **M6** Learned routing | Improve held-out TPPR vs deterministic | **STUB / BLOCKED** | `routing/baseline.py` (`DeterministicRoutingBaseline` only; no training) | §21 learning gates unmet |
| **M7** Project-targeted synthesis | Equal-budget held-out TPPR gain | **STUB / BLOCKED** | `synthesis/eval_harness.py` fixture compare only | Blocked on M6; no model training |

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
| EPIC-022 | Lean extraction adapter | **PARTIAL** | Toolchain JSON / `lake exe lpe_extract` when available; else regex-stub |
| ISSUE-023 | Declaration metadata + signature hashes | **PARTIAL** | Complete under toolchain; stub lexical otherwise |
| ISSUE-024 | Axiom deps + placeholders | **PARTIAL** | Toolchain PASS only when complete; stub → UNKNOWN |
| ISSUE-025 | Direct dependency graph | **PARTIAL** | Schema 1.1 decl edges; stub mixed/heuristic |
| ISSUE-026 | Transitive impact cone | **PARTIAL** | Hand-audited fixture cones; not Mathlib-scale truth |
| ISSUE-027 | Import / dependency expansion | **PARTIAL** | `import_edges` / expansion findings documented |

### M4

| ID | Title | Status | Notes |
| --- | --- | --- | --- |
| EPIC-028 | Semantic evidence providers | **PARTIAL** | Independent findings with provenance; heuristic honesty |
| ISSUE-029 | Statement signature diff | **PARTIAL** | Structural/toolchain hash compare; not implication oracle |
| ISSUE-030 | Project example runner | **PARTIAL** | Structural fixture check; Lean not executed |
| ISSUE-031 | Counterexample-provider protocol | **PARTIAL** | Fail-closed UNKNOWN; not elaborator-backed |
| ISSUE-032 | Repository duplicate retrieval | **PARTIAL** | Jaccard / hash proximity; not embedding ML |
| ISSUE-033 | Downstream replacement tests | **PARTIAL** | Cone + optional Lake; stub inventory WARN/UNKNOWN |

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
| `ENGINEERING_SPEC.md` §4.2 | Lean extraction, impact cone, semantic checks “deferred behind stable interfaces” | M3–M4 partially implemented; interfaces + fixture toolchain path exist | **Medium** — spec text stale vs roadmap progress |
| `VALIDATION_REPORT.md` | “455 … passed” under `-m "not slow"` | This audit: **480 passed**, 1 deselected; `docs/23` already logs 480 | **Low** — report lag |
| `docs/22_COMPREHENSIVE_TEST_PLAN.md` header | Baseline “352 tests passed” | Suite grown to 480 non-slow; §9.1 still met | **Low** |
| `CHANGELOG.md` Unreleased | Documents 455 baseline in places | Latest execution log 480 | **Low** |
| Month-one gate / TEAM stop conditions | “Continue to Lean extraction only when…” | Extraction already present; gate still used as scaffold readiness | **Medium** — process text vs reality |
| Partner “ready” language in docs/24 | Ready to instrument | Correct if read carefully; easy to over-read as pilot authorization | **Medium** (misclaim risk) |
| Default `LPE_DOCKER_IMAGE` | Often implied Lean-capable in casual docs | Doctor shows `ubuntu:22.04` default; Lean needs `lpe-lean:4.14` | **Medium** |
| Ledger “append-only” marketing | Tamper-evident store | FS SQLite + triggers; not WORM (`docs/09`, `docs/25`) | **High** if oversold externally |
| Semantic provider PASS | Could be read as mathematical fidelity | Heuristic/structural; intent fidelity remains human (ADR 0003) | **High** if oversold |
| §17 orchestration &lt;10% of Lean | Listed as target | Explicitly **not measured** vs real Lean wall in week3 baseline | **Medium** |

## 7. Test & quality posture

### This audit run

| Command | Result |
| --- | --- |
| `pytest -q -m "not slow"` | **480 passed**, 1 deselected (`slow`), ~402 s |
| `pytest --collect-only -q -m "not slow"` | 480/481 collected |
| `lpe doctor` | `lpe_version` 0.1.0; git/lake/lean/docker present; `docker_sandbox_available: true`; image `ubuntu:22.04` |
| `lpe gate month-one` | **`all_passed`: true** (scaffold disclaimer intact) |

### Inventory

- **~58** Python modules under `src/lpe/` (~9k LOC).
- **11** JSON Schemas under `schemas/`.
- **~70** `test_*.py` files across unit / integration / security / performance / longevity / pilot.
- Markers: `@pytest.mark.slow` (100k ledger), `@pytest.mark.lean` (Lake/Lean), `@pytest.mark.docker` (daemon/image).
- Docker: `docker/lpe-lean/` + build scripts; optional CI job template (not default `ci.yml`).
- CLI surface: `doctor`, `contract`, `candidate`, `evidence`, `ledger`, `tppr`, `review`, `gate`, `lean`, `github`, `pilot`.

### Covered vs missing

| Covered | Missing / thin |
| --- | --- |
| Contracts, ledger chain, TPPR, gates, risk matrix, sandbox honesty, path fuzz, redaction corpus, R0/R1 Docker ACCEPT E2E (when image present), Lean fixture E2E, longevity 10k, pilot warehouse dry-run | Live GitHub Check POST; Mathlib-scale; partner human protocol; property-test directory sparse; orchestration % of Lean; CODEOWNERS fail-closed with real owners |

## 8. Remaining work ranked

### P0 (must not claim / must fix before external science claims)

1. **Do not claim** §21 clearance, causal pilot utility, R3/R4 production auto-ACCEPT, WORM ledger, or elaborator-complete Mathlib evidence.
2. Refresh `VALIDATION_REPORT.md` counts to **480** (and align CHANGELOG / plan header baselines) to stop understating suite growth and overstating older cuts.
3. Replace `.github/CODEOWNERS` `REPLACE_WITH_*` placeholders before treating merge governance as fail-closed (AUDIT residual; TEAM_INSTRUCTIONS stop-condition adjacent).

### P1 (partner pilot deferred — instrument only)

1. Select real partner repo + domain-lead contract acceptance (ISSUE-035) — **human**, not software.
2. Build/pin `LPE_DOCKER_IMAGE=lpe-lean:4.14` on operator machines; keep default image honesty.
3. Sign/freeze analysis plan (ISSUE-036); run overhead protocol to ≤10% or narrow protocol (ISSUE-037).
4. Execute 30–50 prospective candidates with three conditions (EPIC-034) before any science write-up (ISSUE-038).
5. Measure §17 orchestration overhead against real Lean wall clocks.
6. Optional: live throwaway-repo GitHub Check `--post` once (secrets-gated).

### P2 (post–§21 only)

1. M6 learned routing vs deterministic baseline on held-out TPPR proxy (EPIC-039) — **BLOCKED**.
2. M7 synthesis equal-budget eval (EPIC-040) — **BLOCKED**.
3. Stronger ledger root-of-trust / retention productization beyond archive prototype.
4. Update ENGINEERING_SPEC §4.2 to reflect shipped M3–M4 interfaces vs remaining research depth.

**Partner pilot note:** Engineering is **ready to instrument** per `docs/24_PARTNER_PILOT_READY.md`. Partner shadow pilot *execution and claims* remain deferred until humans, freeze, and §21 metrics exist.

## 9. Bottom-line assessment

Lean Project Evidence at `91d85cf` is a credible **version 0.1 engineering scaffold**: modular monolith, provenance-complete evidence packets, fail-closed uncertainty, Docker-first isolation, append-only utility ledger, TPPR computation, and a review authority loop that refuses high-risk automatic ACCEPT. ENGINEERING_SPEC **§20** is met; the comprehensive test plan’s **§9.1 engineering test-complete** bar is met on measured automated evidence (480 non-slow tests green; month-one gate green). That is the honest meaning of “done” for the current cut.

Roadmap maturity is **asymmetric**. M0–M2 are finished. M3–M4 deliver a real Lake/elaborator extraction path and semantic provider surface on a controlled fixture (and optional `lpe-lean` image), but residual regex-stub / heuristic paths remain deliberately incomplete — correct engineering honesty, not science clearance. M5 has durable instrumentation and a partner kit; it does **not** have a completed shadow study. M6–M7 correctly refuse training behind §21.

What must **not** be claimed: production acceptance authority for R3/R4; elaborator-complete evidence for arbitrary Mathlib-scale repositories; causal utility from pilot dry-runs or warehouse summaries; learned routing or synthesis improvements; or a tamper-evident ledger root of trust beyond filesystem SQLite hash-chain verify. Stop conditions in `TEAM_INSTRUCTIONS.md` (opaque quality scalars, R3/R4 auto-decision, secret leakage, schema meaning changes without major version, features without a TPPR path) remain binding and are largely respected by the current design.
