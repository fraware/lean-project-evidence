# Pilot protocol and partner instrumentation

This guide covers **operator-facing** pilot instrumentation and study design.
It does **not** clear ENGINEERING_SPEC §21 or authorize causal claims.
Canonical non-claims: [`NON_CLAIMS.md`](NON_CLAIMS.md).

Live partner execution steps: [`closure/PILOT_OPERATOR_RUNBOOK.md`](closure/PILOT_OPERATOR_RUNBOOK.md).

## Verdict

Ready to **instrument** a partner shadow pilot. **Not** ready to **claim** causal
utility, clear §21, or grant R3/R4 production ACCEPT (ADR 0003).

## Study design (template)

- **Design:** Prospective shadow pilot; evidence system runs alongside normal review.
- **Unit of analysis:** Candidate artifact bound to a predeclared obligation.
- **Conditions:** Tag each candidate with `condition_tag` (`control`, `instrumented`, `shadow`).
- **Sample size target:** 30–50 prospective candidates.

### Primary outcomes (software metrics)

1. **Automation rate** — fraction of candidates with fully automated packet construction (target ≥80%).
2. **Reproduction rate** — fraction with exact-environment reproduction on selected cases (target ≥90%).
3. **Expert-time overhead** — instrumentation overhead vs baseline (target <10% expert time).
4. **Reviewer comprehension** — qualitative: reviewers can explain evidence dimensions.

### Pre-registration gates (§21)

Do not claim causal utility until:

- Study protocol frozen (versioned and dated).
- Held-out evaluation set defined.
- Baseline deterministic routing documented.

Dry-run and warehouse tests exercise instrumentation plumbing only. They do
**not** satisfy these gates.

## Partner readiness checklist

### 1. Contract + obligations

- Domain lead authors / freezes the project contract (intent, obligations, risk classes).
- Every pilot candidate binds to at least one predeclared obligation id.
- Review authority (`review.yaml`) names human actors who may ACCEPT within policy.
- High-risk (R3/R4) ACCEPT remains human-only — no auto-accept (ADR 0003).

### 2. `lpe-lean` image

- Build or obtain `lpe-lean:4.14` (`scripts/build_lean_docker_image.ps1` / `.sh`, `docker/lpe-lean/`).
- Set `LPE_DOCKER_IMAGE=lpe-lean:4.14` for sandboxed Lake builds under `network_policy: deny`.

### 3. Ledger path

```bash
lpe pilot init-partner --dir ./partner-pilot --project-id YOUR_ID
lpe ledger init ./partner-pilot/ledger/partner-pilot.sqlite3
lpe ledger verify <ledger>
```

Use a non-anonymous `--actor` on every append (anonymous fails closed).

### 4. Three review conditions

| Tag | Reviewer sees LPE packet? | LPE runs? |
| --- | --- | --- |
| `control` | No | No |
| `instrumented` | Yes | Yes |
| `shadow` | No | Yes (overhead / shadow compile) |

### 5. Expert-time and overhead

```bash
lpe pilot record --ledger LEDGER --project-id PROJECT --actor OPERATOR \
  --kind expert-time --candidate-id C1 --condition-tag instrumented \
  --category review --minutes 20

lpe pilot overhead --ledger LEDGER --project-id PROJECT --actor OPERATOR \
  --baseline-minutes 60 --wall-minutes 65 \
  --candidate-id C1 --condition-tag shadow \
  --local-log ./partner-pilot/overhead/field.jsonl
```

Wall-clock overhead is **not** expert review minutes. Overhead events use
`category=overhead_snapshot` (excluded from TPPR denominator).

### 6. Analysis plan freeze

Partner scaffolds include an **UNFROZEN** analysis-plan stub. Partner + research
lead must sign a dated freeze before inferential claims. Until freeze: descriptive
software metrics only (`lpe pilot summary`).

## Durable warehouse model

Pilot records append to the utility ledger via `PilotWarehouse`:

| Action | EventType | Payload markers |
| --- | --- | --- |
| Register candidate + condition tag | `CANDIDATE_REGISTERED` | `source=pilot_warehouse`, `pilot_schema=pilot.warehouse.v1` |
| Packet automated | `EVIDENCE_COMPILED` | `kind=packet_automated` |
| Expert time | `EXPERT_TIME_RECORDED` | hours + minutes + `condition_tag` |
| Overhead snapshot | `EXPERT_TIME_RECORDED` | `category=overhead_snapshot` |
| Outcome marker | `REVIEW_SUBMITTED` | `kind=pilot_outcome` (not ACCEPT authority) |

## Dry-run CLI (instrumentation only)

```bash
lpe pilot init-partner --dir ./partner-pilot --project-id PROJECT
lpe pilot init-partner --validate --dir ./partner-pilot

lpe pilot record --ledger path.sqlite3 --project-id PROJECT --actor OPERATOR \
  --kind candidate --candidate-id C1 --condition-tag instrumented --obligation-ids O-01

lpe pilot summary path.sqlite3 --project-id PROJECT --format both --output ./out

lpe pilot dry-run --project examples/example_project --work-dir /tmp/pilot-dry \
  --repository-root .
```

Dry-run report artifacts label **software_instrumentation** metrics separately from
**causal / §21** non-claims (`section_21_cleared: false`, `causal_claims: false`).

## Report guidance

When publishing pilot results, separate software claims from causal claims.

**Software utility (supported):** packet automation rate, exact-environment
reproduction, instrumentation overhead, ledger/TPPR export completeness.

**Causal utility (limitations required):** state explicitly that the pilot does
**not** establish that the evidence system causally improves TPPR or proof quality
unless §21 gates are cleared under a frozen protocol.

## Ethics and data handling

- No secrets in packets, logs, or ledger exports ([`SECURITY_AND_PRIVACY.md`](SECURITY_AND_PRIVACY.md)).
- Expert-time data stored in append-only ledger events only.
