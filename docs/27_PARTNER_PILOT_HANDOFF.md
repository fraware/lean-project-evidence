# Deferred partner pilot — handoff note

**Status:** Engineering **0.2 fixture-excellence** prerequisite complete.
Partner pilot / §21 execution remains **deferred**.

## What engineering already shipped

- M3–M4 Done at **fixture-excellence** scope (`tests/fixtures/lean_project/`,
  no Mathlib vendoring).
- Doc honesty aligned (`VALIDATION_REPORT`, ENGINEERING_SPEC §4.2, CODEOWNERS
  `@fraware`, fail-closed placeholder CI).
- §17 orch vs Lean wall measurement harness + `docs/benchmarks/orch_vs_lean_wall.md`.
- GitHub Check live POST path documented (`docs/github_check_e2e.md`, env-gated).
- Ledger doctor permission warnings; contract `migrate --write` productization.

## Do not reopen mid-pilot

When starting the partner shadow pilot, execute **EPIC-034** per
`docs/24_PARTNER_PILOT_READY.md` using Phases 0–4 as the engineering
prerequisite. Do **not** re-open M3/M4 scope (Mathlib, elaborator oracles,
R3/R4 auto-ACCEPT) mid-pilot.

## Still blocked until humans + frozen protocol

| Item | Gate |
| --- | --- |
| Partner pilot execution (ISSUE-035–038) | Human experts + signed protocol |
| §21 scientific clearance | Frozen analysis plan + field data |
| M6 / M7 training | Blocked on §21 |
| Mathlib-scale CI | Explicitly out of fixture-excellence |

## First steps when reopening

1. Nominate pilot Lean repo + domain lead.
2. Freeze `docs/pilot_analysis_plan_template.md` with partner signature.
3. `lpe pilot init-partner` and confirm `LPE_DOCKER_IMAGE=lpe-lean:4.14`.
4. Run shadow conditions only; no causal claims until §21 checklist clears.
