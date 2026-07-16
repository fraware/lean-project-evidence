# Pilot dry-run (instrumentation only)

**Status:** Engineering dry-run for durable pilot warehouse + Week 4 longevity path.  
**Not a study:** This document describes **dry-run instrumentation only**.

## Explicit non-claims

- **ENGINEERING_SPEC §21 is not passed.** Shadow-pilot authorization, causal utility, and science publication gates remain research-gated.
- No causal claims are made from dry-run TPPR, automation rate, or overhead numbers.
- No production ACCEPT authority for R3/R4 is implied (ADR 0003).
- Results are synthetic / fixture-based, not a prospective 30–50 candidate partner study.

## Durable warehouse model

Pilot records append to the **utility ledger** (ADR 0004) via `PilotWarehouse`:

| Action | EventType (existing) | Payload markers |
|--------|----------------------|-----------------|
| Register candidate + condition tag | `CANDIDATE_REGISTERED` | `source=pilot_warehouse`, `pilot_schema=pilot.warehouse.v1` |
| Packet automated | `EVIDENCE_COMPILED` | `kind=packet_automated` |
| Expert time | `EXPERT_TIME_RECORDED` | hours + minutes + `condition_tag` |
| Overhead snapshot | `EXPERT_TIME_RECORDED` | `category=overhead_snapshot` (excluded from TPPR denominator) |
| Outcome marker | `REVIEW_SUBMITTED` | `kind=pilot_outcome` (not ACCEPT authority) |

Anonymous `actor_id` values fail closed (ledger auth). A new `LedgerStore` instance on the same SQLite path sees prior events (process-restart durable).

In-memory `PilotInstrumentation` remains a unit-test scratch pad only.

## What the dry-run exercises

1. Frozen corpus of 10–20 synthetic candidates (`examples/candidates` + generated fixtures).
2. `lpe evidence compile --skip-build` for each candidate.
3. Review `REQUEST_REPAIR` (escalate/repair) path → ledger events.
4. Durable `PilotWarehouse` appends (candidates, automation, expert-time, outcomes, overhead).
5. `lpe pilot summary` / report JSON+Markdown separating **software metrics** from **causal claims**.
6. `lpe ledger verify` and `lpe tppr compute`.

Automated coverage: `tests/pilot/test_frozen_corpus_dry_run.py`, `tests/unit/test_pilot_warehouse.py`.

## CLI

```bash
# Partner working directory (instrumentation kit; not §21)
lpe pilot init-partner --dir ./partner-pilot --project-id PROJECT
lpe pilot init-partner --validate --dir ./partner-pilot

# Append durable pilot events
lpe pilot record --ledger path.sqlite3 --project-id PROJECT --actor OPERATOR \
  --kind candidate --candidate-id C1 --condition-tag instrumented --obligation-ids O-01

lpe pilot record --ledger path.sqlite3 --project-id PROJECT --actor OPERATOR \
  --kind expert-time --candidate-id C1 --condition-tag instrumented \
  --category review --minutes 12

# Field wall-clock overhead (separate from review minutes)
lpe pilot overhead --ledger path.sqlite3 --project-id PROJECT --actor OPERATOR \
  --baseline-minutes 60 --wall-minutes 65 --local-log ./partner-pilot/overhead/field.jsonl

# Aggregate from ledger (not in-memory dicts)
lpe pilot summary path.sqlite3 --project-id PROJECT --format both --output ./out

# Frozen corpus dry-run → durable events + reports
lpe pilot dry-run --project examples/example_project --work-dir /tmp/pilot-dry \
  --repository-root .
```

## How to run tests

```bash
pytest -q tests/pilot/ tests/unit/test_pilot_warehouse.py tests/unit/test_partner_scaffold.py
```

Dry-run report artifacts label **software_instrumentation** metrics separately from
**causal / §21** non-claims (`section_21_cleared: false`, `causal_claims: false`).

## Relation to the real protocol

The real shadow-pilot template remains `docs/pilot_study_protocol.md`. Partner
operational checklist: `docs/24_PARTNER_PILOT_READY.md`. Analysis plan stub:
`docs/pilot_analysis_plan_template.md` (UNFROZEN until partner signs). Do not
treat dry-run artifacts as pre-registration, held-out evaluation, or §21 clearance.
