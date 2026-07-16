# Validation report

## Release

Lean Project Evidence engineering scaffold `0.1.0` (post security-hardening Phases 1–5 + Weeks 1–4 + toolchain extraction + elaborator dependency IR schema 1.1 + E2E Lake compile path + optional `lpe-lean:4.14` Docker sandbox + audit gap closure fixture-excellence).

## Honesty preamble

This report describes **current automated validation**, not production acceptance readiness.
Clearing local/CI checks and the month-one scaffold gate does **not** authorize production
ACCEPT decisions, elaborator-complete Lean evidence for arbitrary Mathlib-scale repos, or §21 science claims.
Mirror audit non-claims in `docs/26_SPEC_ROADMAP_AUDIT.md` §9.

## Completed checks (current)

- **575 unit + integration + security + performance + longevity + pilot warehouse/dry-run + partner scaffold + durability/adapter + property tests** collected under default `pytest -q` (`-m "not slow"`; **575 passed**, 1 env-gated GitHub Check E2E skipped when unset, 1 slow deselected). Prior audit baseline was **480**. `@pytest.mark.lean` runs when Lake/Lean is installed; otherwise skips. `@pytest.mark.docker` retries `docker info` briefly before skipping when the daemon is down. Docker Lean E2E (`lpe-lean:4.14`) does not require host Lake for extract; prefers one combined sandbox invocation (`sandbox_invocations: 1`). See `docs/23_TEST_EXECUTION_LOG.md`.
- **R0/R1 ACCEPT E2E (Docker):** with `lpe-lean:4.14`, sandboxed build+extract yields toolchain-complete packets; R0 docs-only can gate-`ACCEPT`; R1 policy-`ESCALATE` then authorized human ACCEPT; ledger + TPPR sustained path. R3/R4 ACCEPT still refused (ADR 0003).
- **E2E Lean path (host):** real `lake build` without `--skip-build` on `tests/fixtures/lean_project/` via `--insecure-host-exec` produces toolchain-complete axiom/impact findings (schema 1.1). Default Docker image lacks Lean — isolation PASS under Docker does not imply typecheck.
- **E2E Lean path (Docker):** with local image `LPE_DOCKER_IMAGE=lpe-lean:4.14` (`docker/lpe-lean/`, built on this host), `network_policy: deny` yields sandboxed Lake build+extract in one container, isolation PASS, and toolchain-complete findings. Image absent → test skips via `docker image inspect` (pytest never rebuilds).
- **Multi-module fixture:** LibA→LibB→LibC→Cross (+ Consumer fan-in) hand-audited cones under `@pytest.mark.lean` (Docker when image present). No Mathlib.
- 11 JSON Schemas exported and validated as Draft 2020-12 schemas.
- Split example Project Contract loads; `lpe contract validate` and `lpe contract schema-check` pass.
- Obligation references, uniqueness, and cycle detection covered.
- Risk/gate matrix: R3 definition-change escalates; `hard_gate_passed` false on UNKNOWN hard checks.
- Unenforced network isolation and incomplete axiom extraction represented as `UNKNOWN`.
- Persistence uncredited until `PERSISTENCE_CONFIRMED`.
- Append-only SQLite mutation denial, hash-chain verify, and **export JSONL with previous_hash/event_hash** round-trip verify (streaming at 10k scale).
- Ledger append rejects anonymous `actor_id`; optional `--project` enforces `project_id` match.
- TPPR credit requires acceptance and persistence.
- Git change-classification and path-traversal rejection on candidate paths.
- Review authority from `review.yaml` only; R3/R4 ACCEPT refused via CLI (ADR 0003).
- Docker sandbox defaults (rw mount for Lake); host exec requires `--insecure-host-exec`.
- CLI doctor, contract validation, and month-one gate evaluator smoke paths.
- M3: regex-stub fail-closed **plus** optional Lake `lpe_extract` / committed toolchain JSON; M4 heuristic providers with `toolchain_backed` when complete; M5–M7 scaffolds only.
- CI: pinned Actions SHAs, `pip-audit`; CODEOWNERS placeholders replaced (`@fraware`); placeholder check **fail-closed** in CI (no `LPE_CODEOWNERS_PLACEHOLDERS_OK` escape).
- **Longevity:** 10k ledger verify ~1.7 s; schema migration refuse/load; historical packet reload (`docs/benchmarks/week4_longevity.md`).
- **Pilot warehouse:** durable ledger-backed instrumentation (`lpe pilot record` / `summary` / `dry-run`); software metrics only — **not §21**.
- **Pilot dry-run:** frozen corpus via warehouse (`docs/pilot_dry_run.md`) — **not §21**.
- **Partner readiness kit:** `docs/24_PARTNER_PILOT_READY.md`, `lpe pilot init-partner`, `lpe pilot overhead`, analysis-plan template (UNFROZEN) — ready to *instrument*, not *claim*.

## What works today

| Area | Status |
|------|--------|
| Contracts / schemas / IDs | Working for `schema_version` 0.1.0 |
| Evidence compile (skip_build) | Deterministic findings + fail-closed uncertainty |
| Evidence compile (Lean E2E) | Host-exec Lake → toolchain-complete; optional `lpe-lean:4.14` Docker → isolation PASS + typecheck; R0/R1 ACCEPT review path when image present |
| Docker sandbox path | Preferred when Docker available; rw mount default; isolation PASS only after sandboxed build; Lean image optional |
| Lean toolchain extraction | Committed JSON **or** `lake exe lpe_extract` (host or same Docker sandbox as build; preferred single combined `docker run`; schema 1.1) when Lean/Lake available; regex-stub otherwise |
| Review record + ledger | Authority-checked; hash-chained; ACCEPT may carry obligation_ids for TPPR |
| Git enrichment (real commits) | Week 2 integration: overrides self-declared risk; invalid revs fail closed; short names mapped to FQNs for cones when extraction available |
| Worktree isolation | Create/cleanup; dirty main tree excluded; post-build JSON captured before cleanup |
| GitHub Check adapter | Payload render; `lpe github submit-check` dry-run / optional `--post` via `gh api`; clear errors; optional CI job; runbook `docs/github_check_e2e.md` |
| Month-one gate CLI | Scaffold criteria only |
| M3–M7 modules | Fixture-excellence M3/M4 depth; M5 instrument; M6/M7 scaffolds only — not science-cleared |
| Pilot warehouse | Durable ledger append + `lpe pilot summary`; instrumentation only — not §21 |
| Partner pilot kit | Scaffold + field overhead CLI; ready to instrument — not ready to claim |
| Contract migrate dry-run | Plans rewrite; never mutates; unsupported target refused |

## What does not work / is not claimed

- No production ACCEPT authority for R3/R4.
- No elaborator-backed axiom closure on the **regex-stub** path (UNKNOWN, never PASS).
- Toolchain completeness requires Lean/Lake helper output or a committed complete JSON artifact — not claimed from lexical scan alone.
- No full Mathlib/Lake CI build in default workflow (optional `@pytest.mark.lean` + template job).
- No maintained official `leanprover/lean4` Docker Hub image; use local `lpe-lean:4.14` (`scripts/build_lean_docker_image.*`) or pin/verify community tags via `LPE_DOCKER_IMAGE`.
- No M6 learned routing or M7 model training (§21 gate-blocked).
- Ledger is **filesystem SQLite**, not a WORM / tamper-evident root of trust.
- §17 performance / cost baselines recorded for Week 3 (`docs/benchmarks/week3_baseline.md`); soft CI gate is 2× budget; orchestration vs Lean wall measured when Lake/`lpe-lean` available (`docs/benchmarks/`).
- Longevity 10k + schema migration recorded for Week 4 (`docs/benchmarks/week4_longevity.md`); optional 100k behind `@pytest.mark.slow`.
- Pilot dry-run / warehouse / partner kit are **instrumentation only** — ready to *instrument*, not ready to *claim*. Partner shadow pilot still requires human experts, signed protocol freeze, held-out evaluation, and §21 gates before causal claims.

## Cost and performance (Week 3)

| Guardrail | Status |
|-----------|--------|
| Contract validate &lt; 1 s | Met (~50 ms CLI on reference machine) |
| Diff classify &lt; 5 s | Met (~271 ms) |
| Packet &lt; 1 MB excl. logs | Met (~17 KB skip_build) |
| Ledger append &lt; 100 ms | Met (p95 ~6 ms @ N=1000) |
| Review packet &lt; 30 s | Met (~335 ms skip_build + markdown) |
| Orchestration &lt; 10% of Lean | Measured when Lake available; see `docs/benchmarks/` (do not invent ratio without measurement) |
| Docker cold-start | ~1.45 s trivial container vs ~1.06 s host trivial; prefer Docker for untrusted / `network_policy: deny` |

## Longevity (Week 4)

| Guardrail | Status |
|-----------|--------|
| Ledger verify 10k &lt; 30 s | Met (~1.7 s) |
| Schema unknown refused / supported loads | Met |
| Historical packet reload + schema validate | Met |
| Export JSONL + tamper detection at scale | Met |
| Ledger 100k | Optional (`pytest -m slow`); not default CI |
| Pilot frozen-corpus dry-run → TPPR | Met (instrumentation only; §21 not passed) |

## Engineering test-complete (§9.1)

Scaffold `0.1.x` meets the **engineering** exit criteria in `docs/22_COMPREHENSIVE_TEST_PLAN.md` §9.1 (automated coverage, longevity 10k, honest validation report). This does **not** imply §9.2 research clearance.

## Explicit non-claims (audit §9 mirror)

Canonical list: [`docs/28_NON_CLAIMS.md`](docs/28_NON_CLAIMS.md).

- No causal utility from dry-runs or warehouse metrics alone.
- No Mathlib-complete elaborator truth.
- No WORM / external root of trust for the utility ledger.
- No R3/R4 auto-ACCEPT.
- No opaque quality scalars (ADR 0002).
- Partner pilot / §21 remain deferred until humans and frozen protocol exist.
- M6/M7 training entrypoints do not exist (`lpe research status` / `lpe routing` exit non-zero).

## Execution boundary

- **Without Lean/Lake:** regex-stub extraction only; axiom/impact findings stay UNKNOWN.
- **With Lean/Lake (host):** `lpe evidence compile` without `--skip-build` using
  `--insecure-host-exec` + non-deny network policy (or a Lean-capable Docker image)
  can produce toolchain-complete packets; `@pytest.mark.lean` E2E covers
  `tests/fixtures/lean_project/` (build → extract → axiom/impact/replacement).
- **Docker without Lean image:** sandboxed build may FAIL; isolation can still PASS;
  never invents `complete: true`. Default `ubuntu:22.04` ≠ Lean — set
  `LPE_DOCKER_IMAGE=lpe-lean:4.14` for typecheck+extract.
- **Docker with `lpe-lean:4.14`:** sandboxed Lake build can PASS with isolation PASS
  and toolchain-complete findings (build scripts under `scripts/`; see
  `docker/lpe-lean/README.md`).
- CLI: `lpe lean extract --repo <path>` invokes the toolchain helper.

## Known deliberate limitations

- lexical Git classifier is conservative;
- regex-stub extraction is incomplete by design;
- semantic providers are heuristic (`toolchain_backed: true` only when toolchain JSON is complete);
- subprocess backend never claims network isolation PASS;
- no external model provider is enabled;
- elaborator IR (schema 1.1) uses `ConstantInfo.getUsedConstantsAsSet` for decl edges and
  ModuleData for import edges; tactic-erased consts and opaque bodies remain residual UNKNOWN/WARN.
