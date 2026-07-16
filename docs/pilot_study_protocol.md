# Shadow pilot study protocol (template)

This template supports EPIC-034–038. It distinguishes **software utility claims** from **causal research claims**.

## Study design

- **Design:** Prospective shadow pilot; evidence system runs alongside normal review.
- **Unit of analysis:** Candidate artifact bound to a predeclared obligation.
- **Conditions:** Tag each candidate with `condition_tag` (`control`, `instrumented`, etc.).
- **Sample size target:** 30–50 prospective candidates (ISSUE-037).

## Primary outcomes

1. **Automation rate** — fraction of candidates with fully automated packet construction (target ≥80%).
2. **Reproduction rate** — fraction with exact-environment reproduction on selected cases (target ≥90%).
3. **Expert-time overhead** — instrumentation overhead vs baseline (target <10% expert time).
4. **Reviewer comprehension** — qualitative: reviewers can explain evidence dimensions.

## Instrumentation

Prefer **`lpe.pilot.warehouse.PilotWarehouse`**: every candidate registration, expert-time row, packet-automation marker, overhead snapshot, and outcome marker **appends to the utility ledger** (existing `EventType` values + `pilot.warehouse.v1` payloads). Summaries are read back with `lpe pilot summary` / `summarize_pilot` — not from process-local dicts.

- Register candidates with obligation IDs and condition tags.
- Record expert-time events by category (`specification`, `review`, `repair`, `integration`).
- Mark when packet construction was fully automated.
- Record overhead snapshots (`category=overhead_snapshot`; excluded from TPPR denominator).

CLI: `lpe pilot record`, `lpe pilot summary`, `lpe pilot dry-run`, `lpe pilot init-partner`, `lpe pilot overhead`. See `docs/pilot_dry_run.md` and `docs/24_PARTNER_PILOT_READY.md`.

**In-memory helper:** `PilotInstrumentation` remains for ephemeral unit tests only. Legacy `append_snapshot_to_ledger` is a one-shot dump (`durable: false`); prefer the warehouse for partner pilots.

**Auth:** anonymous / empty `actor_id` fails closed (ledger AUDIT-017).

**Partner kit:** `lpe pilot init-partner --dir ./partner-pilot` scaffolds ledger path, three condition tags (`control` / `instrumented` / `shadow`), report templates, and an UNFROZEN analysis-plan stub. Validate with `--validate`. Field wall-clock overhead: `lpe pilot overhead` (not review minutes).

## Analysis plan

- Report descriptive statistics only unless pre-registered inferential tests are approved.
- Separate **software performance** (latency, automation, errors) from **causal utility** (TPPR improvement attributable to the system).
- Publish limitations explicitly (see `docs/pilot_report_template.md`).
- Preregistration fields: `docs/pilot_analysis_plan_template.md` (starts UNFROZEN).

## Pre-registration gates (ENGINEERING_SPEC §21)

Do not claim causal utility until:

- Study protocol frozen (this document versioned and dated).
- Held-out evaluation set defined.
- Baseline deterministic routing documented.

**Engineering dry-run:** `docs/pilot_dry_run.md` and `tests/pilot/` exercise instrumentation plumbing only. They do **not** satisfy these gates.

**Partner readiness (instrumentation):** `docs/24_PARTNER_PILOT_READY.md` — ready to instrument, not ready to claim.

## Ethics and data handling

- No secrets in packets, logs, or ledger exports ([09_SECURITY_AND_PRIVACY.md](09_SECURITY_AND_PRIVACY.md)).
- Expert-time data stored in append-only ledger events only.
