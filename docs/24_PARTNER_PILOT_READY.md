# Partner shadow-pilot readiness (engineering)

**Verdict:** Ready to **instrument** a partner shadow pilot. **Not** ready to **claim** causal utility, clear ENGINEERING_SPEC §21, or grant R3/R4 production ACCEPT (ADR 0003).

This checklist is the operational package a partner needs to run a **shadow pilot** without running the scientific study. Completing it does not pass §21.

## 1. Contract + obligations with domain lead

- [ ] Domain lead authors / freezes the project contract (intent, obligations, risk classes).
- [ ] Every pilot candidate binds to at least one predeclared obligation id.
- [ ] Review authority (`review.yaml`) names human actors who may ACCEPT within policy.
- [ ] High-risk (R3/R4) ACCEPT remains human-only — no auto-accept (ADR 0003).

## 2. `lpe-lean` image

- [ ] Build or obtain `lpe-lean:4.14` (`scripts/build_lean_docker_image.ps1` / `.sh`, `docker/lpe-lean/`).
- [ ] Set `LPE_DOCKER_IMAGE=lpe-lean:4.14` for sandboxed Lake builds under `network_policy: deny`.
- [ ] Confirm `docker image inspect lpe-lean:4.14` succeeds on operator machines.
- [ ] Host Lake is optional for Docker extract; do not vendor Mathlib.

## 3. Ledger path

- [ ] Create a partner working dir: `lpe pilot init-partner --dir ./partner-pilot --project-id YOUR_ID`.
- [ ] Initialize SQLite: `lpe ledger init ./partner-pilot/ledger/partner-pilot.sqlite3`.
- [ ] Use a non-anonymous `--actor` on every append (anonymous fails closed).
- [ ] Verify chain periodically: `lpe ledger verify <ledger>`.

## 4. Three review conditions

Tag every candidate with exactly one `condition_tag` from `condition_tags.json`:

| Tag | Reviewer sees LPE packet? | LPE runs? |
| --- | --- | --- |
| `control` | No | No |
| `instrumented` | Yes | Yes |
| `shadow` | No | Yes (overhead / shadow compile) |

- [ ] Assignment rule agreed with domain lead (e.g. sequential, blocked, or randomized).
- [ ] Tags recorded at candidate registration (`lpe pilot record --kind candidate`).

## 5. Expert-time recording

Record **review / repair / specification / integration** minutes via warehouse expert-time events (TPPR denominator categories):

```bash
lpe pilot record --ledger LEDGER --project-id PROJECT --actor OPERATOR \
  --kind expert-time --candidate-id C1 --condition-tag instrumented \
  --category review --minutes 20
```

- [ ] Categories limited to the TPPR set (do not stuff wall-clock into `review`).
- [ ] One actor identity per operator; no anonymous ids.

## 6. Overhead protocol (wall-clock, separate)

Instrumentation wall-clock is **not** expert review minutes. Use the field recorder:

```bash
lpe pilot overhead --ledger LEDGER --project-id PROJECT --actor OPERATOR \
  --baseline-minutes 60 --wall-minutes 65 \
  --candidate-id C1 --condition-tag shadow \
  --local-log ./partner-pilot/overhead/field.jsonl
```

- [ ] Baseline = wall time without LPE instrumentation for the same task shape.
- [ ] Wall = wall time with compile/packet/UI instrumentation.
- [ ] Events land as `category=overhead_snapshot` (excluded from TPPR denominator).
- [ ] Target: overhead fraction ≤ 10% (software metric only — not a causal claim).

## 7. Frozen analysis plan pointer

- [ ] Copy / edit `analysis_plan.md` in the partner dir (starts **UNFROZEN**).
- [ ] Canonical template: [`pilot_analysis_plan_template.md`](pilot_analysis_plan_template.md).
- [ ] Partner + research lead sign a dated freeze before inferential claims.
- [ ] Until freeze: descriptive software metrics only (`lpe pilot summary`).

## 8. What LPE measures vs what humans must supply

| LPE measures (software) | Humans must supply |
| --- | --- |
| Packet automation markers | Domain contract + obligations |
| Exact-environment reproduction flags (when recorded) | Condition assignment honesty |
| Expert-time events (as entered) | Actual review / repair minutes |
| Wall-clock overhead snapshots | Baseline vs instrumented timing protocol |
| Ledger hash chain + TPPR export | Interpretation; no causal attribution without freeze |
| Dry-run fixtures | Prospective candidates + held-out set |

## 9. Explicit non-claims

- **§21 is not passed.** Do not cite this checklist as scientific clearance.
- **No causal TPPR improvement** from automation rate, overhead, or descriptive TPPR alone.
- **No R3/R4 auto-ACCEPT.** ADR 0003 stands.
- **Scaffold ≠ study.** `lpe pilot dry-run` and warehouse unit tests are instrumentation drills.
- **Ready to instrument ≠ ready to claim.**

## 10. Operator commands (smoke)

```bash
lpe pilot init-partner --dir ./partner-pilot --project-id partner-project
lpe pilot init-partner --validate --dir ./partner-pilot
lpe pilot dry-run --project examples/example_project --work-dir /tmp/pilot-dry --repository-root .
lpe pilot summary LEDGER --project-id PROJECT --format both --output ./out
```

## Related docs

- [`pilot_study_protocol.md`](pilot_study_protocol.md) — study design template
- [`pilot_dry_run.md`](pilot_dry_run.md) — engineering dry-run honesty
- [`pilot_report_template.md`](pilot_report_template.md) — software vs causal split
- [`pilot_analysis_plan_template.md`](pilot_analysis_plan_template.md) — preregistration fields
- [`23_TEST_EXECUTION_LOG.md`](23_TEST_EXECUTION_LOG.md) — residual partner blockers
- [`../VALIDATION_REPORT.md`](../VALIDATION_REPORT.md) — engineering validation only
