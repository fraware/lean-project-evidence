# Pilot Operator Runbook (CLOSURE-033–036 scaffolding)

This runbook describes the **operator workflows** for a live partner pilot.
It does **not** claim that a pilot has been executed, sealed, or cleared under
ENGINEERING_SPEC §21. Release `0.4.0` remains **needs live partner execution**.

Non-claims: see `docs/28_NON_CLAIMS.md`. M6/M7 stay blocked until
`learned_routing_authorized` / `synthesis_authorized` are true in a
machine-readable `Section21GateReport`.

## Prerequisites (pilot-readiness engineering toward 0.3.0)

- Typed ledger + R1–R4 quorum path available (`lpe review attest`, `accept-quorum`)
- Repair / adjudication CLI: `lpe review repair-lineage`, `repair-request`,
  `repair-complete`, `adjudicate`
- Example protocol bundle under `pilot-protocol/` (synthetic; replace for partner)
- Docker / analysis image digest known (content digest, not `latest`)
- Off-host seal path planned
- Package remains `0.2.0` until formal checklists close
  (`docs/closure/REMAINING_ACCEPTANCE.md`)

## CLOSURE-033 — Partner freeze

1. Select partner repository + domain lead; record ownership in
   `docs/closure/OWNERSHIP.md`.
2. Copy `pilot-protocol/` to a partner working directory (or regenerate via
   Python `write_example_bundle` and replace every field with real values).
3. Fill **all** required files; freeze refuses blanks / `TODO` / `TBD`:
   - `protocol.yaml`, `endpoints.yaml`, `assignment.yaml`
   - `reviewer-roster.yaml`, `held-out-set.json`
   - `comprehension.yaml`, `analysis.yaml`, `signatures.json`
4. Encrypt the randomization seed; store ciphertext in `assignment.yaml`
   (`randomization_seed_ciphertext`). Keep plaintext offline until data lock.
5. Freeze:

```bash
lpe pilot freeze-protocol --protocol-dir ./pilot-protocol
```

6. Commit the frozen bundle + `freeze.json` hashes to the partner custody store.
   Any post-freeze edit requires a **new** `protocol_id` / version.

## CLOSURE-034 — Episode recording (30–50)

Quotas (minimums):

| Condition / coverage | Minimum |
| --- | ---: |
| Control | 12 |
| Instrumented | 12 |
| Shadow | 6 |
| R3/R4 episodes | 8 |
| Distinct reviewers | 2 |
| Domain + maintainer roles | 1 each |

1. Build episode specs JSON (risk × artifact type strata; multiples of 5).
2. Assign conditions (deterministic; record before review):

```bash
lpe pilot assign --protocol-dir ./pilot-protocol \
  --episodes episodes.json --seed "$SEED_PLAINTEXT" \
  --output assignment-manifest.json
```

3. For each episode, record candidate / expert-time / overhead via
   `lpe pilot record` and `lpe pilot overhead` (ledger-backed).
4. Complete reviewer comprehension before primary analysis:

```text
# Use lpe.pilot.comprehension.score_comprehension against frozen cases
# Second failure excludes the reviewer from primary analysis
```

5. Record dimension attestations and quorum acceptance for R1–R4 as required.
   R3/R4 never auto-accept.

```bash
lpe review attest --project ./partner-project --attestation attest.json \
  --conflict conflict.json --ledger ./ledger.sqlite3 --risk-class R3
lpe review accept-quorum --project ./partner-project \
  --attestations attestations.json --ledger ./ledger.sqlite3 \
  --risk-class R3 --evidence-fingerprint "$FP" \
  --actor-id operator --artifact-id "$CAND"
# Repair cycle (attestations do not transfer to the new candidate):
lpe review repair-lineage --prior-candidate-id "$CAND" \
  --repair-request-ids rep-1 --applied-change ./fix.patch
lpe review repair-request --project ./partner-project --ledger ./ledger.sqlite3 \
  --artifact-id "$CAND" --actor-id operator --candidate-id "$CAND" \
  --rationale "REQUEST_REPAIR" --attestations attestations.json
lpe review repair-complete --project ./partner-project --ledger ./ledger.sqlite3 \
  --artifact-id "$CAND" --actor-id operator --prior-candidate-id "$CAND" \
  --repair-request-ids rep-1 --applied-change ./fix.patch \
  --new-evidence-fingerprint "$NEW_FP"
# Adjudication (provisional judgment before peer reveal):
lpe review adjudicate --project ./partner-project \
  --provisional provisional.json --record adjudication.json \
  --peer-attestations peers.json --conflict adj-conflict.json \
  --original-reviewer-ids "r1,r2" --review-minutes 25 \
  --output adjudication-attestation.json
```

## CLOSURE-035 — Persistence follow-up

1. Confirm integration for accepted candidates (`INTEGRATION_CONFIRMED`).
2. Run declared downstream suites (`DOWNSTREAM_ENABLED`).
3. Wait persistence window (default 30 calendar days) then
   `PERSISTENCE_CONFIRMED`, or explicitly censor incomplete obligations.
4. Every accepted obligation must be completed or explicitly censored in the
   ledger (no silent drop).

## CLOSURE-036 — Lock, analyze, publish

1. Data lock (fails closed on mismatch):

```bash
lpe pilot lock --protocol-dir ./pilot-protocol \
  --ledger locked.sqlite3 --seal locked.seal.json \
  --assignment assignment-manifest.json \
  --analysis-image-digest "sha256:..." \
  --expected-episodes "..." --completed-episodes "..." \
  --attestation-complete --exclusions-resolved \
  --output data-lock.json
```

2. Analyze (descriptive only):

```bash
lpe pilot analyze --protocol-id proto.partner.v1 \
  --data-lock-hash "<from data-lock.json>" \
  --episodes episode-outcomes.json --output analysis-output.json
```

3. Evaluate §21 gates (fail closed on missing observables):

```bash
lpe research evaluate-gates \
  --protocol ./pilot-protocol \
  --ledger locked.sqlite3 \
  --seal locked.seal.json \
  --analysis analysis-output.json \
  --observables observables.json \
  --output section21-gates.json
```

4. Publish engineering + methodological results only with claims that match
   the gate report. Set M6/M7 authorization **only** from
   `learned_routing_authorized` / `synthesis_authorized` in that report.
5. Update `docs/closure/MILESTONE_STATUS.json` from the gate report flags.
   Do not implement CLOSURE-037/038 training until those flags are true.

## What this repository does **not** ship

- Sealed live partner datasets
- A completed 30–50 episode study
- Causal TPPR improvement claims
- Learned routing / synthesis training (CLOSURE-037/038 remain BLOCKED)
