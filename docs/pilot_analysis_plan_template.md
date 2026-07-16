# Pilot analysis plan template (preregistration)

**Status: UNFROZEN**

> Mark **UNFROZEN** until the partner domain lead and research lead sign a dated
> freeze. Tooling scaffolds copy this template; they never auto-freeze or clear
> ENGINEERING_SPEC §21.

This template supports descriptive software metrics during instrumentation and
preregistered analysis **after** freeze. It does not authorize causal claims by
itself.

## Freeze metadata

| Field | Value |
| --- | --- |
| Partner / site | |
| Project id | |
| Domain lead | |
| Research lead | |
| Protocol version / commit | |
| Freeze date | _(empty while UNFROZEN)_ |
| Signature / acknowledgment | _(empty while UNFROZEN)_ |

After signing, change the banner to **Status: FROZEN**, archive a dated copy, and
record the commit hash of the frozen plan.

## Conditions

Every candidate receives exactly one `condition_tag`:

| Tag | Packet visible? | LPE runs? | Assignment rule |
| --- | --- | --- | --- |
| `control` | No | No | |
| `instrumented` | Yes | Yes | |
| `shadow` | No | Yes | |

- Sample size target (prospective): 30–50 candidates
- Blocking / randomization details:

## Gates (targets)

Record whether each gate is **in-scope** for this freeze. Meeting a software
target during dry-run does **not** pass §21.

| Gate | Target | In scope? | Measurement |
| --- | --- | --- | --- |
| Packet automation | ≥ 80% | | Warehouse `packet_automated` / candidates |
| Exact-environment reproduction | ≥ 90% selected | | Recorded reproduction flags |
| Instrumentation overhead | < 10% expert time | | `lpe pilot overhead` / `overhead_snapshot` |
| Reviewer comprehension | Qualitative pass | | Structured debrief |

## TPPR proxy

- **Primary descriptive metric:** TPPR from utility ledger export (`lpe tppr compute`)
- **Numerator rules:** accepted + sustained critical-path obligations only
- **Denominator categories:** `specification`, `review`, `repair`, `integration`
- **Inferential tests:** none until FROZEN and approved; list planned tests here after freeze:
  - _(empty while UNFROZEN)_

## Exclusions

Always exclude from causal / inferential claims while UNFROZEN:

- Fixture / dry-run corpora (`lpe pilot dry-run`)
- `overhead_snapshot` wall-clock events (not review minutes; excluded from TPPR denominator)
- Anonymous or missing `actor_id` attempts (fail closed)
- R3/R4 ACCEPT without human authority (ADR 0003)
- Any claim that automation rate implies TPPR improvement

Partner-specific exclusions:

-

## Held-out evaluation set

Required before freeze:

- Definition / selection rule:
- Size:
- Storage location (no secrets):
- Blinding plan (if any):

## Reporting

- Software metrics: [`pilot_report_template.md`](pilot_report_template.md)
- Operational checklist: [`24_PARTNER_PILOT_READY.md`](24_PARTNER_PILOT_READY.md)
- Honesty: [`pilot_dry_run.md`](pilot_dry_run.md)

## Explicit non-claims

- This file being present does **not** pass §21.
- UNFROZEN plans support instrumentation only.
- FROZEN plans enable preregistered analysis; they still require completed human
  expert review and held-out evaluation before science publication claims.
