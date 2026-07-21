# Changelog

## Unreleased — toward 0.3.0 (pilot readiness engineering)

Phase D–E engineering for CLOSURE-018–032 is present on the tree. **Package
version remains `0.2.0`** until formal release-acceptance checklists close
(see `docs/closure/REMAINING_ACCEPTANCE.md`). This section is **not** a `0.3.0`
tag claim: no partner study, causal TPPR improvement, or §21 clearance.

### Added

- **TPPR v2 (CLOSURE-025):** `src/lpe/metrics/tppr_v2.py` + `schemas/tppr-report-v2.schema.json`; credit-once lifecycle; numerator/denominator audit tables; anti-gaming fail-closed; `lpe tppr compute-v2`.
- **Pilot protocol bundle (CLOSURE-026):** `src/lpe/pilot/protocol.py`; freeze refuses blanks; `lpe pilot protocol-init` / `freeze-protocol`.
- **Assignment (CLOSURE-027):** blocked 2:2:1 HMAC-SHA256 shuffle; `lpe pilot assign`.
- **Comprehension (CLOSURE-028):** five-case calibration scoring with one retry / primary exclusion.
- **Data lock (CLOSURE-029):** `lpe pilot lock` verifies protocol, ledger, off-host seal, held-out, assignment, analysis image digest.
- **Analysis + §21 gates (CLOSURE-030):** `lpe pilot analyze`; `lpe research evaluate-gates` writes `Section21GateReport`; fail-closed on missing observables; M6/M7 authorization flags default false; **synthetic sealed pass/fail golden fixtures** (`tests/fixtures/section21/`, `tests/unit/test_section21_golden.py`) — not live pilot data.
- **GitHub Check productization (CLOSURE-031):** fail-closed ESCALATE; clear missing-auth errors; CI job `github-check-e2e` always visible and skips cleanly without secrets; `docs/github_check_e2e.md`.
- **Docs/version/inventory sync (CLOSURE-032):** `scripts/check_version_sync.py`, `scripts/sync_repository_inventory.py` (REPOSITORY_TREE + MANIFEST drift), `scripts/check_milestone_status.py`.
- **Repair / adjudication CLI (CLOSURE-024):** `lpe review repair-lineage` / `repair-request` / `repair-complete` / `adjudicate`.
- **Phase F scaffolding (CLOSURE-033–036):** `docs/closure/PHASE_F_OPERATOR_STEPS.md` + `PILOT_OPERATOR_RUNBOOK.md` — operator workflows only; no sealed live pilot dataset claimed.
- **Phase G blocked (CLOSURE-037–038):** documented in `MILESTONE_STATUS.json`; training entrypoints remain `ResearchGateBlocked`.
- **Remaining acceptance tracker:** `docs/closure/REMAINING_ACCEPTANCE.md` with honest gap matrix.
- **§19 engineering closure:** `scripts/verify_wheel.py`, `scripts/generate_sbom.py`, `scripts/validate_compatibility_matrix.py`, `scripts/check_doc_links.py`; scheduled Lean/Docker workflow replaced echo stub with skip-clean real jobs; macOS/Windows best-effort on every PR (`continue-on-error`); CI coverage gate hard via `scripts/check_coverage_gates.py` (lines ≥90%, critical packages ≥95%, branch ≥85%).
- **Extract defaults doc:** `docs/closure/EXTRACT_DEFAULTS.md`; generic extract auto-on when safe; CLI `--paired-extract` / `--prefer-generic-extract`.
- **EvidencePacket V2 additive fields:** `run_manifest`, `coverage_summary`, `hard_gate`, `uncertainty_records`; finding `snapshot_fingerprint`.

### Changed

- Semantic / downstream / fixture providers emit stable finding IDs (`finding_<check>_<subject>_<version>`).
- `docs/closure/MILESTONE_STATUS.json` keeps `current_release: 0.2.0`; downgrades thin IDs (006/008/009/017/004) to documented partials; `0.4.0 = needs_partner`; M6/M7 `authorized: false`.
- Lexical risk fallback floors at R1 (never R0 auto-accept).
- CI: version/docs sync, repository inventory drift, dedicated-repo Check E2E path, wheel smoke, SBOM recipe, compatibility matrix validate; §19 coverage/typing gates merge-gated.
- Compatibility matrix: fixture supported; external projects recorded as selected candidates with `pending_live_validation` SHAs (not claimed complete).
- Repository hygiene: root coverage dumps, wheels, caches, and local `.lpe/` CAS pollution removed from the working tree; `.gitignore` expanded so they do not return.

## 0.2.0 — Evidence integrity (engineering)

Engineering release for Phase A–C closure work (CLOSURE-001–017). This is **not** a claim that the formal release-acceptance checklist or production readiness is complete; non-claims remain in force. Formal open items: `docs/closure/REMAINING_ACCEPTANCE.md`.

### Added

- **Evidence basis and coverage (CLOSURE-010):** `EvidenceBasis`, `EvidenceCoverage`, `subject_refs`, typed `payload`, and ProvenanceV2 enrichment on findings; PASS with weaker-than-required basis or incomplete coverage is refused.
- **Fixture suite manifests (CLOSURE-013):** `schemas/fixture-suite.schema.json`; examples/counterexamples require YAML suites; unrelated Lean failure → UNKNOWN; expected diagnostics must match.
- **Downstream successor suites (CLOSURE-014):** `src/lpe/providers/downstream.py` + successor-suite schema; paired base/candidate runs with enabled/regressed/unchanged reporting.
- **Synthesis registry (CLOSURE-015):** `src/lpe/evidence/synthesis.py` versioned rules for `repository.api_fit`, `downstream.declared_use`, `semantic.intent_support`; recommendation policy id joins synthesis version; R3/R4 intent satisfaction requires `HUMAN_ATTESTED`.
- **Schema 0.2.0 migration (CLOSURE-016):** writers emit `0.2.0`; `0.1.0` remains readable; golden packet migration marks `LEGACY_UNRESOLVED` and never invents acceptance/persistence.
- **CI expansion (CLOSURE-017):** Python 3.12+3.13 Ubuntu matrix; schema drift `--check`; macOS/Windows best-effort on every PR; scheduled Lean/Docker/Mathlib/SBOM/longevity jobs (skip-clean when tooling absent); coverage gate evolved to hard lines ≥90% / critical ≥95% / branch ≥85% (see Unreleased); wheel smoke + SBOM recipe scripts.

### Changed

- Semantic statement diff prefers elaborated base/head types when available.
- Duplicate retrieval separates exact type-hash matches from heuristic token similarity bases.
- Package version `0.2.0` (no git tag until formal acceptance).

## Historical notes (pre-0.2.0 engineering)

### Changed

- **Validation baseline:** `pytest -q -m "not slow"` — counts refreshed in `VALIDATION_REPORT.md`.
- **Seal custody workflow:** `lpe ledger seal --seal` / `verify-seal --seal` write and verify from
  alternate (off-host / read-only) paths; CLI reports `colocated` + `storage_recommendation`;
  `lpe doctor --ledger` warns on missing seal **and** co-located default seals.
- **Packet provenance:** evidence packets carry `evidence_fingerprint`; optional
  `ledger_seal_tip`; markdown / warehouse / review-record cross-link the fingerprint
  (and tip after append) for audit trails.
- **Deterministic routing baseline id:** `select_review_question` uses
  `DeterministicRoutingBaseline` and records `baseline_id=deterministic_baseline.v1`
  on every review question (scaffold for future §21 held-out comparison; no learning).
- **CI:** explicit honesty/seal CLI smoke step
  (`tests/integration/test_honesty_seal_cli_smoke.py`).
- **Anti-oversell + M6/M7 blocking:** canonical `docs/28_NON_CLAIMS.md`; mandatory
  `NON_CLAIMS` on `lpe pilot summary` / `dry-run`; refuse oversell CLI flags;
  `lpe research status` gate matrix; `lpe routing` / `research train` exit
  non-zero until §21; `lpe lean status` + doctor extractor mode / ADR 0003
  active check; regex-stub packet markdown banner; M6/M7 `.train()` raises
  `ResearchGateBlocked` (training entrypoints do not exist).
- **Live GitHub Check path (operator-ready):** `submit_check_run` / CLI clear
  errors for missing `gh`, auth failures, and sentinel `head_sha` (`mock-sha`,
  `unavailable-sha`); dry-run emits exact `argv` + `command_preview` + payload;
  ESCALATE remains fail-closed (`conclusion=failure`). Optional CI job
  gated by dedicated-repo vars (skips cleanly if unset); default `python` job
  never requires secrets. Expanded runbook `docs/github_check_e2e.md`.
- **Audit gap closure (honesty):** `VALIDATION_REPORT.md` baseline aligned;
  `docs/22` header refreshed; `ENGINEERING_SPEC` §4.2
  describes shipped M3–M4 interfaces with residual depth (not “fully deferred”);
  `docs/17` month-one language clarifies pilot readiness vs extraction tooling;
  CODEOWNERS/`MAINTAINERS` use `@fraware`; CI CODEOWNERS check is fail-closed
  (removed `LPE_CODEOWNERS_PLACEHOLDERS_OK` escape).
- **M3 fixture-excellence:** toolchain-first for declared `lpe_extract` /
  schema≥1.1 artifacts; stale complete JSON refused or re-extracted; regex-stub
  never PASS for axioms/impact; FQN ambiguity warnings; diamond/chain/opaque
  cone expectations; AmbiguousA/B short-name fixture.
- **M4 Lake-backed semantics (fixture depth):** statement-diff structural
  binder/domain/conclusion fields; examples/cex via `lake env lean` when
  present; duplicate retrieval requires toolchain hashes when complete;
  replacement keeps decl-dep cones + Lake compile.
- **§17 orch vs Lean wall:** measurement harness +
  `docs/benchmarks/orch_vs_lean_wall.md` (honest ratio; no invented budget).
- **Trust productization:** `lpe doctor --ledger` permission warnings; Docker
  default-image Lean honesty hint; `lpe contract migrate --write`; audit
  scorecard refresh; partner handoff `docs/27_PARTNER_PILOT_HANDOFF.md`.

### Added

- **Crash/recovery + seal interaction tests:** mid-txn crash preserves prior seal;
  append after seal fails closed until reseal.
- **Ledger external seal:** `lpe ledger seal` / `lpe ledger verify-seal` write and
  check a snapshot manifest (default `<ledger_dir>/.lpe/ledger.seal.json`) with
  tip hashes, event count, export content hash, timestamp, and tool version.
  Optional HMAC via `LPE_LEDGER_SEAL_KEY`; without it, content-hash-only custody
  with explicit “not cryptographic custody / not WORM” wording. Doctor warns
  when a configured ledger has no seal. Docs: `docs/09`, `docs/25`, `docs/06`.
- **GitHub Check E2E (env-gated):** `LPE_GH_CHECK_E2E=1` + runbook
  `docs/github_check_e2e.md` (mock remains default CI).
- **Property tests:** hashing + ledger chain invariants under `tests/property/`.
- **Lean example/cex fixtures** under
  `tests/fixtures/lean_project/.lean-project-contract/tests/`.
- **Secret-redaction corpus expansion:** Slack (`xox*` / `xapp-`), GitLab `glpat-`,
  npm, Stripe, OpenAI/Anthropic `sk-`, Hugging Face `hf_`, JWT triples, and
  multiline PEM/OpenSSH private-key blocks; adversarial Lean/Lake log
  non-over-redact tests (`tests/security/test_redaction_corpus.py`).
- **Ledger retention prototype:** `lpe ledger archive` verifies the live chain,
  writes a verified JSONL archive, and leaves the SQLite file untouched;
  runbook for optional fresh `lpe ledger init` in `docs/06_UTILITY_LEDGER_SPEC.md`.
- **Large synthetic impact-cone budgets:** ~4k-edge graph soft time/memory
  ceilings (`tests/performance/test_impact_cone_scale.py`).
- **Ledger threat-model tabletop:** `docs/25_LEDGER_THREAT_MODEL.md` (host FS vs
  export verify residual risk).
- **Dependabot / Actions SHA drift note:** documented in `docs/09` and
  `SECURITY.md` (CI already SHA-pins Actions; weekly Dependabot for pip +
  github-actions).
- **Ledger WAL durability:** every connection sets `journal_mode=WAL`,
  `synchronous=NORMAL`, and `busy_timeout`; `journal_mode()` / `checkpoint()`
  helpers; crash mid-transaction + multi-process writer recovery tests
  (`tests/unit/test_ledger_wal_durability.py`).
- **GitHub Check `gh api` adapter:** `lpe github submit-check` plans
  `gh api repos/{owner}/{repo}/check-runs` from a rendered packet payload;
  default **dry-run** (no network); explicit `--post` executes (mocked in
  tests). Refuses `mock-sha`. See `src/lpe/github/submit.py`.
- **Contract migrate dry-run:** `lpe contract migrate-dry-run [--to VERSION]`
  plans `schema_version` rewrites without mutating YAML (`would_refuse` /
  `no_op` / `would_rewrite`). Documents bump path in
  `docs/18_CONTRACT_MIGRATION.md`.
- **Path adversarial fuzz:** NUL / percent-encoded separators / NTFS ADS
  colons / Unicode lookalike dots / symlink escape coverage
  (`tests/security/test_path_adversarial_fuzz.py`); `assert_safe_repo_relative`
  fail-closed for those classes.
- **Opaque elaborator IR fixture:** `LpeFixture.OpaqueLimits` + unit tests
  documenting opaque body-visibility cone honesty (no fixture axioms — those
  would trip `lean.prohibited_axioms` on E2E ACCEPT).
- **Optional CI job:** `lpe-lean-docker-optional` in
  `.github/workflows/lean-integration-template.yml` (gated by
  `vars.LPE_LEAN_DOCKER_JOB=1`); requires pre-built `lpe-lean:4.14`, never
  `docker build`s in CI. Default `ci.yml` unchanged.
- **Partner shadow-pilot readiness kit:** `docs/24_PARTNER_PILOT_READY.md`
  checklist (contract, `lpe-lean` image, ledger, three conditions, expert-time,
  overhead protocol, analysis-plan pointer, LPE-vs-human split, non-claims);
  `docs/pilot_analysis_plan_template.md` (UNFROZEN until partner signs);
  `lpe pilot init-partner` / `scripts/init_partner_pilot.py` scaffold + validate;
  `lpe pilot overhead` field wall-clock recorder (separate from review minutes;
  `overhead_snapshot` excluded from TPPR). Ready to *instrument*, not *claim*
  §21. See `docs/pilot_dry_run.md`.
- **R0/R1 ACCEPT E2E (Docker):** when `lpe-lean:4.14` is present,
  `tests/integration/test_r0_r1_accept_e2e.py` runs sandboxed build+extract →
  toolchain-complete packet → R0 gate `ACCEPT` (or R1 honest policy `ESCALATE`) →
  authorized `lpe review record` ACCEPT → ledger + TPPR (with sustained credit).
  R3/R4 ACCEPT remains refused (ADR 0003).
- **Review → TPPR bridge:** `lpe review record --obligation-ids` and
  `record_review_decision(..., obligation_ids=...)` attach `obligation_id` plus
  `semantic_fidelity` / `repository_accepted` on ACCEPT events so TPPR can credit.
- **Durable pilot warehouse:** `PilotWarehouse` appends candidate / expert-time /
  packet-automation / overhead / outcome records to the utility ledger (existing
  `EventType`s + `pilot.warehouse.v1` payloads). CLI: `lpe pilot record`,
  `lpe pilot summary`, `lpe pilot dry-run`. Process-restart durable via SQLite;
  anonymous actors fail closed. Reports separate software metrics from causal /
  §21 claims (**not §21**). See `docs/pilot_dry_run.md`.
- **Single Docker sandbox invocation:** `DockerSandboxExecutor.verify_build_and_extract`
  runs allowlisted `lake build` then `lake exe lpe_extract` in one `docker run`
  (fixed shell script; argv never interpolated). Provenance:
  `combined_build_extract: true`, `sandbox_invocations: 1`. Fail closed: build
  phase fail → no toolchain-complete claim; extract phase fail → incomplete /
  UNKNOWN. Sequential fallback via `LPE_DOCKER_COMBINED_BUILD_EXTRACT=0` or
  custom `LPE_LEAN_EXTRACT_CMD`.
- **Multi-module Lean stress fixture:** `LibA`→`LibB`→`LibC`→`Cross` (+ Consumer
  fan-in) with hand-audited `expectations_multi_module.json`. `@pytest.mark.lean`
  (+ Docker when `lpe-lean:4.14` present) asserts cone correctness. No Mathlib.
- **Sandboxed toolchain extract:** after Docker `lake build`, `lake exe lpe_extract`
  runs via the same `DockerSandboxExecutor` (same image, `--network=none`, rw mount).
  Provenance notes / `extract_executor: docker-sandbox` on isolation + axiom/impact
  findings. Docker Lean E2E no longer requires host Lake (host `_lake_bin` scrubbed
  in test). Fail closed on sandboxed extract errors (UNKNOWN axioms, no host fallback).
- **Lean Docker sandbox image:** `docker/lpe-lean/` Dockerfile installs elan +
  Lean `v4.14.0` (tag `lpe-lean:4.14`). Build via
  `scripts/build_lean_docker_image.ps1` / `.sh`. Set `LPE_DOCKER_IMAGE=lpe-lean:4.14`
  for sandboxed Lake builds under `network_policy: deny`. Pytest only
  `docker image inspect`s — never rebuilds.
- **Docker Lean E2E:** `@pytest.mark.docker`
  `test_e2e_docker_lean_image_isolation_and_toolchain` asserts isolation PASS
  **and** toolchain-complete when the image is present (sandboxed extract); ubuntu:22.04
  path still proves FAIL build without fake axiom PASS.
- **E2E Lean evidence path:** `@pytest.mark.lean` integration
  (`tests/integration/test_evidence_lean_e2e.py`) runs real `lake build` (no
  `--skip-build`) on `tests/fixtures/lean_project/` via
  `--insecure-host-exec` + `network_policy: allow`, asserting toolchain-complete
  axiom/impact findings (schema 1.1), honest host isolation UNKNOWN, worktree
  cleanup + persisted `.lpe/lean-extraction.json`, and Docker-without-Lean
  isolation honesty (`@pytest.mark.docker`).
- **CLI:** `lpe lean extract --repo` wraps Lake `lpe_extract` / adaptive extract.
- **Elaborator dependency IR (schema 1.1):** `LpeExtract.lean` emits Environment-based
  `declaration_dependency_edges` via `ConstantInfo.getUsedConstantsAsSet` (dependee→depender)
  and separate module→module `import_edges` from `ModuleData`. Field
  `extraction_schema_version` versions the protocol; `dependency_edges` remains
  backward-compatible (toolchain mirrors decl edges).
- **Diamond/chain fixture modules** (`LpeFixture.Diamond`, `LpeFixture.Chain`) for
  hand-audited transitive impact-cone membership under `@pytest.mark.lean`.
- **Lean toolchain extraction path:** `src/lpe/lean/toolchain.py` invokes `lake exe lpe_extract` when a project declares that target; fills signature hashes; documented export protocol for partner Lean repos.
- **Lean 4 fixture** (`tests/fixtures/lean_project/`): minimal Lake package + `LpeExtract.lean` elaborator dump to `.lpe/lean-extraction.json`. `@pytest.mark.lean` integration tests skip cleanly without Lean/Lake.
- **Compiler post-build rediscovery:** after a build, prefer toolchain JSON from the build worktree before cleanup; axiom/impact PASS only when toolchain-complete.
- **Semantic providers:** `statement_diff` / `duplicate_retrieval` mark `toolchain_backed` and prefer toolchain signature hashes when extraction is complete.
- **Docker honesty:** rw-mount probe tests; `LPE_DOCKER_IMAGE` docs clarify no maintained official `leanprover/lean4` image and stale community tags; readonly mount fails closed with hint.

### Changed

- **Soft findings honesty:** `repository.api_fit` and `downstream.declared_use` are
  `NOT_APPLICABLE` when no public declaration changes (enables real R0 ACCEPT when
  hard gates pass); remain `UNKNOWN` for public-surface candidates.
- **Docker marker flake reduction:** `@pytest.mark.docker` probes `docker info` with
  short retry/backoff before skipping (still skips if the daemon is down).
- **Pilot dry-run reports:** Markdown explicitly separates software metrics from
  causal / §21 non-claims.
- **Git FQN resolution:** `resolve_changed_names_for_cone` maps git short names
  to module FQNs for impact cones when extraction is available.
- **Docker Windows PATH:** sandbox executor rewrites Windows host `PATH`/`HOME`
  to Linux container defaults including `/root/.elan/bin`.
- **Downstream replacement:** toolchain cones attempt successor signature-hash
  integrity plus optional `lake env lean` on dependent modules (fail-closed
  UNKNOWN when Lake cannot run); regex-stub remains WARN inventory-only.
- **Worktree extract persist:** complete toolchain JSON is copied to the primary
  repo before worktree cleanup so semantic providers re-read toolchain truth.
- **Python extractor / impact cone:** prefers `declaration_dependency_edges` for
  downstream cones; `import_edges` feed import-expansion findings only (no coarse
  module fan-out into toolchain cones). Import expansion semantics documented
  (added = after\\before, removed = before\\after).

### Testing

- Suite baseline: **400 → 455** collected under `-m "not slow"` (**455 passed**,
  0 skipped on this host, +1 slow deselected). WAL durability, path adversarial
  fuzz, GitHub submit dry-run/`--post` mocks, migrate-dry-run, opaque IR honesty.
  Log: `docs/23_TEST_EXECUTION_LOG.md`.
- Prior cut: **390 → 394** collected under `-m "not slow"` (**394 passed**,
  0 docker skips on this host, +1 slow deselected). R0/R1 sandboxed ACCEPT E2E,
  api_fit N/A unit coverage, review→TPPR flags, Docker info retry. Log:
  `docs/23_TEST_EXECUTION_LOG.md`.
- Prior cut: **383 → 390** collected under `-m "not slow"` (**389 passed**,
  1 docker skip, +1 slow deselected). Pilot warehouse durability / summary / CLI
  + durable dry-run. Combined Docker build+extract + multi-module cone stress
  unchanged. Log: `docs/23_TEST_EXECUTION_LOG.md`.
- Prior cut: **377 → 383** collected under `-m "not slow"` (+1 slow
  deselected). Combined Docker build+extract + multi-module cone stress.
  `@docker` may skip if `docker info` flakes; combined Lean E2E verified when
  the daemon and `lpe-lean:4.14` are present. Log: `docs/23_TEST_EXECUTION_LOG.md`.
- Prior cut: **372 → 377** (sandboxed extract). Prior: **368 → 372** (Lean Docker image E2E).

### Testing (Week 4)


- **Longevity suite** (`tests/longevity/`): 10k ledger append/verify/export + tamper; schema migration refuse/load + bump-path docs; historical packet reload against JSON Schema; optional 100k behind `@pytest.mark.slow` (default `addopts`: `-m "not slow"`).
- **Pilot dry-run** (`tests/pilot/`, `docs/pilot_dry_run.md`): frozen corpus (18) compile→review→ledger→TPPR + overhead helper; explicit **not §21** / no causal claims.
- Baselines: `docs/benchmarks/week4_longevity.md`. Suite: **342 → 352** passed (+1 slow deselected). Log: `docs/23_TEST_EXECUTION_LOG.md`.
- Engineering §9.1 test-complete claimed for scaffold `0.1.x`; §9.2 research gates unchanged.

### Fixed

- **Ledger export/verify scale:** `export_jsonl` streams SQLite rows; `verify_exported_jsonl` streams JSONL lines (avoids full in-memory materialization at 10k+).

### Testing (Week 3)

- **Performance suite** (`tests/performance/`): soft §17 budgets (fail only on &gt;2×), contract/diff/packet/ledger(N=100,1000)/TPPR/markdown/truncation/orchestration; `@pytest.mark.performance`; optional `LPE_RECORD_BENCHMARKS=1` → `benchmarks/latest.json`.
- Baselines: `docs/benchmarks/week3_baseline.md` (Docker cold-start vs host insecure documented).
- Suite baseline: **328 → 342** tests. Execution log: `docs/23_TEST_EXECUTION_LOG.md`.

### Changed

- **Ledger append throughput:** `LedgerStore.initialize()` is idempotent per instance (no schema re-exec on every append).
- **Contract reuse:** `compile_evidence(..., contract=)` avoids redundant contract re-reads.
- **Markdown cost:** `render_packet` omits raw build `stdout`/`stderr` bodies (keeps hashes / size placeholders).

### Testing (Week 2)

- **Git-candidate E2E** (`tests/integration/test_git_candidate.py`): real commit-range `build_candidate_from_commits` / enrich overrides; invalid and null OIDs fail actionably; CLI `evidence compile` exit 1 on bad rev.
- **Docker evidence builds** (`tests/integration/test_evidence_docker_build.py`, `@pytest.mark.docker`): `--network=none` + hardening flags; `execution.isolation` PASS only after a sandboxed build ran; skip_build → NOT_APPLICABLE; allowlist enforced before Docker.
- **Lean toolchain ingest** (`tests/fixtures/lean/toolchain_project/`, `test_evidence_lean_repo.py`): committed `.lpe/lean-extraction.json` treated as `lean.toolchain` + complete; regex-stub honesty without JSON; incomplete `complete=false` never axiom PASS.
- **Worktree isolation** (`test_worktree_isolation.py`): dirty main tree excluded; unknown commit rejected; compile uses worktree path; cleanup on build exception.
- **Impact cone fixtures:** transitive `GrandConsumer.lean` + hand-audited `expectations.json`.
- Lean integration workflow template: weekly/dispatch job for toolchain fixture pytest (no Lake required).
- Suite baseline: **303 → 328** tests. Execution log: `docs/23_TEST_EXECUTION_LOG.md`.

### Fixed

- **Worktree leak:** `compile_evidence` always cleans isolated worktrees via `try`/`finally` (including mid-build exceptions).
- **Incomplete toolchain axiom PASS:** `lean.prohibited_axioms` requires `_is_toolchain_complete` (`complete=true`, no errors) before PASS.

### Testing (Week 1)

- **Security regression suite** under `tests/security/`: host exec opt-in, build_command allowlist fuzz, review authority / R3 ACCEPT refusal, null OID + git risk override, path traversal, secret redaction corpus, env denylist, axiom UNKNOWN-never-PASS on regex-stub, placeholder sorry → REJECT, `network_policy: deny` host refusal.
- **Integration-lite** under `tests/integration/`: contract/candidate CLI smoke, evidence compile (`--skip-build`) → review record → ledger verify → TPPR, ledger export/`verify_exported_jsonl` round-trip + tamper detection, TPPR blocked on broken chain, month-one gate + doctor.
- **pytest `@pytest.mark.docker`** marker registered; Docker-marked tests skip cleanly when the daemon is unavailable.
- Suite baseline: **201 → 303** tests (`pytest -q` green). Execution log: `docs/23_TEST_EXECUTION_LOG.md`.

### Fixed

- **Review expert time → TPPR:** `expert_time_event` now stores `hours` (minutes/60) alongside `minutes`, matching pilot snapshot semantics. `compute_tppr` accepts `hours` or legacy `minutes`-only payloads instead of raising `KeyError`.

### Documentation

- **docs:** comprehensive test plan (`docs/22_COMPREHENSIVE_TEST_PLAN.md`) — capability matrix, AUDIT regression map, performance/longevity schedule, and exit criteria; `docs/21_TEST_BACKLOG.md` links to it.
- **docs:** Week 1 execution log (`docs/23_TEST_EXECUTION_LOG.md`).

### Security

- **AUDIT-001:** Default evidence builds prefer Docker sandbox; host subprocess builds require explicit `--insecure-host-exec` (refused with an actionable error when Docker is unavailable).
- **AUDIT-002 / AUDIT-009:** Review authority uses only `review.yaml` roles for `reviewer_id`; self-declared decision JSON roles are ignored. `lpe review record` enforces `can_record_acceptance()` (R3/R4 ACCEPT refused in v0 per ADR 0003).
- **AUDIT-004 / AUDIT-015:** `lpe evidence compile` verifies git revisions and forces git enrichment for toplevel repos / candidates with `head_commit`, overriding self-declared risk metadata; null OIDs rejected.
- **AUDIT-016:** Placeholder/`sorry`/`admit` scan covers changed `.lean` files and patch sources, not only `patch_text`.
- **AUDIT-003:** `lean.prohibited_axioms` never PASS on incomplete `regex-stub` extraction; empty `axioms_used` → UNKNOWN (escalate). Explicit prohibited axioms still FAIL. Toolchain PASS only when `extractor: "lean.toolchain"` with `complete=true`.
- **AUDIT-011:** Lean extraction adapter protocol (`LeanExtractionResult.to_dict` / JSON ingest). Prefers `.lpe/lean-extraction.json` from Lean/Lake when present; otherwise improved AST-lite labeled `extractor: "regex-stub"` (never claims toolchain completeness). Signature hashes, axioms/placeholders, decl-use edges, import expansion.
- **AUDIT-012:** Dependency edges are `dependee → depender`; impact cone is downstream dependents. Hand-audited fixture tests assert cone membership.
- **AUDIT-020:** `hard_gate_passed` is false when hard-relevant checks are UNKNOWN (e.g. axiom closure); gate reasons distinguish hard failures vs unresolved hard-relevant checks.
- **AUDIT-010:** Semantic providers are heuristic-complete (not elaborator-backed): `statement_diff` structural signature compare; `project_examples` / `counterexamples` structured fixture scan with attempt provenance (never silent PASS on missing README-only suites); `duplicate_retrieval` local lexical Jaccard + signature-hash proximity over `.lean` corpus (empty corpus → UNKNOWN); `downstream.replacement_tests` emits structured successor findings from impact cone (empty/UNKNOWN cone → UNKNOWN). CHANGELOG/details mark `toolchain_backed: false` unless toolchain extraction is complete.
- **AUDIT-018:** GitHub Check adapter uses candidate `head_commit` as `head_sha` (never `mock-sha`); ESCALATE maps to `failure` by default (fail-closed for required checks), configurable via `escalate_as`.
- **AUDIT-029:** Golden packet coverage expanded for ACCEPT (gate-level + schema-valid packet; documents forced-escalate dimensions under `skip_build`/regex-stub), REJECT (placeholder FAIL), ESCALATE, build-skipped honesty, and JSON Schema validation.
- **AUDIT-013:** Month-one gate runs real `load_contract` validation for the example project and requires importable sandbox + allowlist (not file existence alone). Gate clearance explicitly does **not** mean production-ready.
- **AUDIT-005:** `build_command` executables restricted to allowlisted tools (`lake`, `lean`, `elan`); arbitrary/shell commands rejected with actionable errors.
- **AUDIT-006:** Docker sandbox hardening (`--cap-drop=ALL`, `no-new-privileges`, memory/pids limits, writable mount by default, `LPE_DOCKER_IMAGE` / `LPE_DOCKER_READONLY`); `execution.isolation` PASS only when a network-isolated sandboxed build actually ran (`skip_build` → `NOT_APPLICABLE`).
- **AUDIT-007:** Secret redaction applied to build stdout/stderr before evidence embedding (PATs, AWS keys, Bearer, common assignment shapes).
- **AUDIT-008:** Environment denylist for `*_TOKEN` / `*_SECRET` / `*_PASSWORD` / `GITHUB_*` / `AWS_*` / `CI`; `CI` removed from default allowlist.
- **AUDIT-014:** CLI `--worktree/--no-worktree` (default on) wires isolated git worktree execution.
- **AUDIT-019:** `network_policy: deny` requires Docker `--network=none`; host subprocess refused under deny; subprocess never claims network isolation PASS.
- **AUDIT-027:** Execution unit tests for allowlist, timeout, truncation, redaction, env denylist, worktree, and isolation honesty (Docker optional/skippable).

### Phase 5 — Ops / maturity (AUDIT-017–032 subset)

- **AUDIT-017:** Ledger append rejects anonymous/empty `actor_id`; `lpe ledger append --project` enforces `project_id` match; export JSONL includes `previous_hash` / `event_hash`; `verify_exported_jsonl` + `lpe ledger export --verify`; filesystem trust boundary documented (not WORM).
- **AUDIT-021 / AUDIT-032:** `VALIDATION_REPORT.md` aligned to ~187 tests and honest capability matrix; CHANGELOG clarifies M3 regex/toolchain JSON, M4 heuristic, M5–M7 scaffold.
- **AUDIT-022:** CODEOWNERS placeholder FAIL checklist in `MAINTAINERS.md` / `docs/20_LAUNCH_CHECKLIST.md`; `scripts/check_codeowners_placeholders.py` (CI warn until launch via `LPE_CODEOWNERS_PLACEHOLDERS_OK`).
- **AUDIT-024:** GitHub Actions pinned to full commit SHAs in `ci.yml` and `lean-integration-template.yml`.
- **AUDIT-025 / AUDIT-028 / AUDIT-030:** `pip-audit` in CI; path-traversal tests; ledger export hash round-trip; `docs/21_TEST_BACKLOG.md`.
- **AUDIT-026:** `lpe contract schema-check` + `src/lpe/contract/migration.py`; `SUPPORTED_SCHEMA_VERSIONS` unchanged at `0.1.0`.
- **AUDIT-023 / AUDIT-031:** Pilot state non-durable + optional ledger snapshot; M6/M7 gate-blocked docstrings; `gate_passed` renamed to `fixture_harness_ok` in synthesis harness.

### Added

- **M1 deterministic evidence:** golden packet matrix (R0–R4 candidates), improved Git declaration classifier with public-path and signature-change detection, Docker network-none sandbox backend, isolated git worktree runner, gate decision matrix tests, complete JSON/Markdown reporting with provenance fields.
- **M2 review operation:** reviewer authority validation (ADR 0003), `lpe review record` CLI for ledger-backed review decisions and expert-time events, GitHub Check output adapter with mock payload rendering, review question routing priority tests.
- **Month-one gate:** `docs/month_one_gate.md` checklist, `lpe gate month-one` evaluator from repository state.
- **M3 Lean-aware evidence (honest):** adaptive extractor with `regex-stub` default and optional toolchain JSON ingest; dependency graph + downstream impact cone; import expansion findings. Regex path does not claim elaborator axiom/impact truth.
- **M4 semantic evidence (heuristic):** statement-diff, project-examples, counterexamples, duplicate-retrieval, and downstream-replacement providers emit real structural findings with fail-closed UNKNOWN when evidence is missing; none claim Lean elaborator or intent-fidelity truth.
- **M5 shadow pilot scaffold:** `PilotInstrumentation` (in-memory; optional ledger snapshot), overhead helper, study protocol and pilot report templates.
- **M6/M7 conditional scaffolds (gate-blocked, no training):** deterministic routing baseline; synthesis eval harness with fixture data and `fixture_harness_ok` (not §21 science clearance).
- expanded `.github/CODEOWNERS` with schema, execution, ledger, ADR, and workflow ownership (`MAINTAINERS.md`);
- GitHub launch helpers: `scripts/github_launch.py` (labels, milestones, backlog import);
- clean-clone verification script: `scripts/verify_clean_clone.py`;
- launch governance docs: `docs/19_GITHUB_LABELS.md`, `docs/20_LAUNCH_CHECKLIST.md`;
- canonical label and milestone lists under `backlog/`;
- CI hardening: concurrency limits, job timeout, and `lpe doctor` step;
- M0 foundation: schema compat tests, negative contract fixtures, obligation cycle detection, hash property tests, ledger concurrency/correction events, TPPR fixture matrix, contract migration protocol doc.

## 0.1.0 — Initial scaffold

- complete standalone engineering specification;
- modular repository structure;
- typed project contracts and candidates;
- versioned JSON Schema export;
- deterministic evidence compiler scaffold;
- risk and decision policy;
- structured review question;
- append-only hash-chained SQLite ledger;
- TPPR computation;
- CLI;
- examples;
- CI;
- issue backlog and launch instructions.
