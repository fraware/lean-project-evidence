# Remaining formal acceptance items

**Package version:** `0.2.0`  
**Status source:** [`MILESTONE_STATUS.json`](MILESTONE_STATUS.json)  
**Acceptance checklist:** [`v1/lean_project_evidence_release_acceptance_v1.md`](v1/lean_project_evidence_release_acceptance_v1.md)

This file lists checklist items that are **not** yet honestly closable. Engineering
for Phases A–E is present on the tree; that does **not** authorize bumping to
`0.3.0` / `0.4.0` or cutting release tags until the items below are closed by
humans (and, where noted, by live partner / secrets).

Non-claims remain in force: [`docs/28_NON_CLAIMS.md`](../28_NON_CLAIMS.md).

---

## Honest engineering gap matrix (post-closure pass)

| Area | Status | Notes |
| --- | --- | --- |
| EvaluationWorkspace / ProviderContext / executor routing | **implemented** | CLOSURE-001–003 |
| Docker hardening + digest recording | **implemented** | CLOSURE-004; publish-by-digest still operator |
| Generic extract injector | **implemented; default-on when safe** | Auto-prefer when no `lpe_extract`; see [`EXTRACT_DEFAULTS.md`](EXTRACT_DEFAULTS.md) |
| Live paired elaborator extract | **opt-in (documented)** | Dry-run fingerprints default-on; live via `LPE_PAIRED_EXTRACT=1` / `--paired-extract` |
| RunManifest | **implemented** | Embedded on packets as `run_manifest` dump |
| EvidencePacket V2 fields | **partial → improved** | `run_manifest`, `coverage_summary`, `hard_gate`, `uncertainty_records`, finding `snapshot_fingerprint`; typed FindingPayload discriminated union; semantic/downstream/fixture providers + compiler emit typed variants (legacy bare-dict coercion retained) |
| ProvenanceV2 | **partial** | Additive optional fields on legacy `Provenance` |
| Ledger seal v2 | **implemented** | Sequence, prior hash, protocol freeze, tips, custody |
| Typed ledger / TPPR v2 / pilot CLI | **implemented** | Field drills remain human |
| §21 evaluator | **implemented** | Synthetic pass/fail golden fixtures in `tests/fixtures/section21/` + `test_section21_golden.py` |
| §19 PR CI Ubuntu 3.12/3.13 | **implemented** | |
| §19 macOS/Windows | **best-effort on every PR** | `continue-on-error: true` |
| §19 coverage 90/95/85 | **met** | Measured unit+security: lines **94.17%**, critical packages all ≥95% (policy 98.08, gate 97.56, review 97.27, ledger 95.81, TPPR 97.33, protocol 95.77); branch **85.22%**. CI hard: `scripts/check_coverage_gates.py --fail-under=90 --require-critical --require-branch` |
| §19 ruff/mypy full gate | **implemented** | Full `src/lpe` ruff + mypy merge-gated in CI |
| §19 wheel smoke + SBOM recipe | **implemented** | `scripts/verify_wheel.py`, `scripts/generate_sbom.py` |
| §19 scheduled Lean/Docker | **implemented (skip-clean)** | Replaced echo stub; image/Mathlib live validation still pending |
| Docker digest publish | **recipe strengthened** | `scripts/record_lean_docker_digest.{sh,ps1}` records local digest without registry login; push/pin still operator |
| Compatibility matrix | **partial** | Fixture supported; external SHAs `pending_live_validation` |
| Scale validation ≥500 / Mathlib 10k | **needs live extract** | Tests skip without pinned SHA / `LPE_SCALE_CLONE_ROOT` |
| CLOSURE-031 live Check E2E | **needs secrets** | |
| CLOSURE-033–036 | **needs partner** | |
| CLOSURE-037–038 | **blocked** | |

---

## Release 0.2.0 — Evidence Integrity (package current)

Engineering for CLOSURE-001–017 is present. Formal checklist still open:

| Checklist item | Why still open |
| --- | --- |
| CLOSURE-001–017 formally closed in tracker | Engineering done; human sign-off / issue close-out pending |
| One immutable candidate snapshot used by every finding | Covered by EvaluationWorkspace tests; formal attestation pending |
| No semantic provider invokes host Lake directly | AST/grep guards present; formal audit sign-off pending |
| Generic extraction without target `lpe_extract` | Implemented + default-on when safe; Mathlib-scale / multi-repo live validation pending |
| Base/candidate extractionsiff elaborator-backed | Dry-run default; live paired opt-in; scale validation pending |
| Evidence basis/coverage/provenance/artifact refs validate | Unit coverage present; formal packet audit pending |
| Docker read-only mount + image digest recorded | Hardening present; published digest / registry pin pending |
| Schema 0.2.0 migration from 0.1.0 | Migration code + tests present; release notes packaging pending |
| Full CI matrix (Python/OS, Docker/Lean, lint, typing, security, schemas) | Ubuntu 3.12/3.13 + OS best-effort + scheduled Lean/Docker/SBOM/longevity; coverage lines ≥90% + critical packages ≥95% + branch ≥85% hard; full `src/lpe` ruff/mypy merge-gated |
| README / version / changelog / validation report / tree / manifest agree | Drift scripts enforce version + inventory; keep green in CI |
| Explicit non-claims intact | `docs/28_NON_CLAIMS.md` present; preserve on every release |
| Compatibility / scale gates (§9.10–9.11) | Fixture done; external pins selected as candidates but `pending_live_validation` |

**Do not tag `0.2.0` until** the acceptance checklist boxes above are human-checked
and `formal_0_2_0_acceptance_checklist_complete` is set `true` in
`MILESTONE_STATUS.json`.

---

## Release 0.3.0 — Pilot Readiness (engineering present; package not bumped)

Phase D–E code for CLOSURE-018–032 is on the tree. Package stays `0.2.0`.

| Checklist item | Why still open |
| --- | --- |
| CLOSURE-018–032 formally closed | Most engineering done; CLOSURE-031 live E2E needs secrets |
| Typed utility events / lifecycle reducers | Implemented; formal review pending |
| R3/R4 auto-accept impossible; qualified human quorum works | Unit + CLI paths present; human protocol drill pending |
| Conflict, blinding, repair, adjudication enforced | Library + CLI present; field drill pending |
| TPPR v2 audit tables | Implemented; no live pilot numerator yet |
| Protocol freeze / assignment / comprehension / data lock / §21 fail-closed | Implemented; synthetic golden pass/fail fixtures present; live protocol not frozen |
| **Live GitHub Check E2E in dedicated test repo (CLOSURE-031)** | **Needs repo vars + token** — see [`docs/github_check_e2e.md`](../github_check_e2e.md). Job `github-check-e2e` skips cleanly when unset. |
| Pilot readiness = authorization to instrument, not causal utility | Documented; keep non-claims |

**Do not bump package or tag `0.3.0` until** the 0.3.0 acceptance checklist is
honestly closable (including live Check E2E) and
`formal_0_3_0_acceptance_checklist_complete` is `true`.

---

## Release 0.4.0 — Pilot Completion (needs partner)

| Item | Owner |
| --- | --- |
| CLOSURE-033 partner freeze | Research lead + partner |
| CLOSURE-034 30–50 episodes + quotas | Partner operators |
| CLOSURE-035 persistence follow-up | Partner + data owner |
| CLOSURE-036 lock / analyze / sealed report | Research lead |

Scaffolding only: [`PHASE_F_OPERATOR_STEPS.md`](PHASE_F_OPERATOR_STEPS.md),
[`PILOT_OPERATOR_RUNBOOK.md`](PILOT_OPERATOR_RUNBOOK.md). No sealed study claimed.

---

## Post-gate (blocked)

| Item | Status |
| --- | --- |
| CLOSURE-037 learned routing | BLOCKED — `learned_routing_authorized=false` |
| CLOSURE-038 synthesis training | BLOCKED — `synthesis_authorized=false` |

`lpe research train` / `lpe routing train` raise `ResearchGateBlocked`. Do not
implement training until a machine-readable `Section21GateReport` authorizes it.

---

## Engineering debt still open (optional; no partner/secrets/live Lake)

| Debt | Status |
| --- | --- |
| Overall coverage 90% / critical packages 95% / branch 85% | **Met** — lines **94.17%**, critical packages **≥95%**, branch **85.22%** (CI hard via `--require-critical --require-branch`). Residual line/branch hotspots (not gate-blocking): `compiler` ~84% lines, `cli` ~88% lines; paired extract / generic / pilot analysis remain below 100% branch |
| Full `src/lpe` ruff + mypy + format | **Green** — merge-gated lint/typecheck; `ruff format --check .` also green after format pass |
| Snapshot copy ignore (CAS / caches) | **Fixed** — `_copy_tree` keeps `.lpe/lean-extraction*.json` but skips `.lpe/artifacts` and tooling caches (prevents CAS re-ingest feedback loop on fixture projects) |
| Provider emission of typed FindingPayload | Semantic / downstream / fixture runners / compiler emit typed variants; synthesis already typed; legacy bare-dict coercion retained for golden packets |
| Docker registry publish-by-digest | Local digest recording + recipe done; actual push needs operator registry login |
| Compatibility / Mathlib / Check E2E / partner | Unchanged — need live extract, secrets, or partner |

### Human blockers (cannot close in-repo alone)

| Blocker | Blocks | What a human must do |
| --- | --- | --- |
| Formal checklist sign-off | Tag `0.2.0` / bump honesty flags | Close CLOSURE-001–017 in tracker; set `formal_0_2_0_acceptance_checklist_complete=true` |
| Live GitHub Check E2E secrets | Tag `0.3.0` / CLOSURE-031 | Configure `LPE_GH_CHECK_*` vars + token on dedicated throwaway repo |
| Live Lean/Mathlib scale extract | Compatibility matrix / §9.10–9.11 | Pin SHAs, run scale clones, flip `pending_live_validation` |
| Docker registry publish | Operator digest pin | Login + push image; record published digest |
| Partner pilot (CLOSURE-033–036) | Tag `0.4.0` | Partner freeze, 30–50 episodes, persistence, sealed report |
| §21 authorization | CLOSURE-037–038 / M6–M7 | Machine-readable `Section21GateReport` only — do not implement training early |

---

## Engineering vs formal

| Todo | Engineering standpoint |
| --- | --- |
| E (CLOSURE-025–032) | Complete except live secrets for CLOSURE-031 |
| F (CLOSURE-033–036) | Scaffolding complete; needs partner |
| G (CLOSURE-037–038) | Correctly blocked |

---

## Repository hygiene (pre-push)

Working-tree cleanup before human review/push (not a formal acceptance change):

- Removed local-only root dumps (coverage JSON/txt, `.coverage`, wheel copy, pytest last-run noise).
- Removed generate-only caches (`.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`, `*.egg-info/`, `artifacts/`).
- Removed accidental local CAS under `examples/**/.lpe` and fixture `.lpe/` trees.
- Expanded `.gitignore` so coverage climb/residual dumps, `.coverage.*`, wheels, caches, `.lpe/`, and `artifacts/` do not return.
- Root remains product/docs surface only (README, LICENSE, CHANGELOG, VALIDATION_REPORT, inventory, Makefile, pyproject, CONTRIBUTING, SECURITY, MAINTAINERS, TEAM_INSTRUCTIONS).
- Closure specs under `docs/closure/v1/` untouched; no source/test deletions; no invented pilot data; **not pushed**.
