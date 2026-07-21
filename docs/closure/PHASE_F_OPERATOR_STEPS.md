# Phase F operator steps (0.4.0 — partner pilot)

**Status:** scaffolding only. Package `0.2.0` holds formal acceptance open;
Phase D–E machinery toward `0.3.0` is present but **does not** claim a completed
partner study, causal TPPR improvement, or §21 clearance.

`docs/closure/MILESTONE_STATUS.json` records `formal_0_4_0_requires_live_partner: true`.

## Human inputs required before CLOSURE-033

1. Select an active partner Lean repository and domain lead.
2. Confirm repository maintainer + at least one domain reviewer + research lead signatories.
3. Resolve reviewer conflicts (authorship, collaboration, packet construction).
4. Choose recruitment window dates and persistence follow-up calendar (default 30 days).
5. Provide real `repository_remote` and `repository_commit_at_freeze` (no placeholders).

## Exact operator sequence

```bash
# 1. Scaffold working directory (instrumentation only)
lpe pilot init-partner --root ./partner-work --project-id PARTNER_ID

# 2. Create machine-readable protocol bundle (edit all fields; no blanks)
lpe pilot protocol-init ./pilot-protocol --project-id PARTNER_ID
# Edit protocol.yaml, endpoints.yaml, assignment.yaml, reviewer-roster.yaml,
# held-out-set.json, comprehension.yaml, analysis.yaml, signatures.json
# Recompute cross-hashes after edits (or re-run a helper that rewrites hashes).

lpe pilot protocol-validate ./pilot-protocol
lpe pilot freeze-protocol --protocol-dir ./pilot-protocol

# 3. Initialize durable ledger + off-host seal path
lpe ledger init ./partner-work/ledger/pilot.sqlite3
# After first events:
lpe ledger seal ./partner-work/ledger/pilot.sqlite3 --seal /secure/offhost/pilot.seal.json

# 4. Assign conditions (seed stays encrypted until data lock)
# episodes.json: list of {candidate_id, risk_class, artifact_type, author_id}
lpe pilot assign \
  --protocol-dir ./pilot-protocol \
  --episodes ./episodes.json \
  --seed "$PILOT_SEED" \
  --output ./assignment-manifest.json

# 5. Comprehension calibration (five external cases) per reviewer
lpe pilot comprehension-score \
  --protocol ./pilot-protocol \
  --cases ./calibration-cases.json \
  --attempt ./attempt.json \
  --reviewer-id REVIEWER \
  --output ./comprehension/REVIEWER.json

# 6. Execute 30–50 episodes (CLOSURE-034) — human field work
# Quotas: >=12 control, >=12 instrumented, >=6 shadow, >=8 R3/R4,
# >=2 reviewers, >=1 domain + >=1 maintainer.
# Record via: lpe pilot record ... / lpe review attest ... / lpe review accept-quorum ...

# 7. Integration + 30-day persistence (CLOSURE-035)
# Every accepted obligation: completed persistence or explicit censor event.

# 8. Data lock (CLOSURE-029 / 036 prelude)
lpe pilot lock \
  --protocol-dir ./pilot-protocol \
  --ledger ./partner-work/ledger/pilot.sqlite3 \
  --seal /secure/offhost/pilot.seal.json \
  --assignment ./assignment-manifest.json \
  --analysis-image-digest "sha256:..." \
  --expected-episodes "id1,id2,..." \
  --completed-episodes "id1,id2,..." \
  --attestation-complete \
  --exclusions-resolved \
  --output ./locked/data-lock.json

# 9. Analysis + §21 gates (fail closed on missing observables)
lpe pilot analyze \
  --protocol-id PROTO_ID \
  --data-lock-hash LOCK_HASH \
  --episodes ./locked/episodes.json \
  --output ./locked/analysis.json

lpe research evaluate-gates \
  --protocol ./pilot-protocol \
  --ledger ./partner-work/ledger/pilot.sqlite3 \
  --seal /secure/offhost/pilot.seal.json \
  --analysis ./locked/analysis.json \
  --observables ./locked/observables.json \
  --output ./locked/section21-gates.json
```

## Non-claims (must remain until gates pass)

- No causal utility claim from instrumented vs control without §21 gate pass.
- No Mathlib-scale completeness claim from fixture extraction.
- No R3/R4 auto-accept; quorum attestations only.
- `learned_routing_authorized` / `synthesis_authorized` stay false until the gate report says otherwise (CLOSURE-037/038).

## What engineering will not invent

Do not fabricate partner episodes, sealed analysis outputs, or a green §21 report for release marketing. Update `MILESTONE_STATUS.json` only after real lock + gate artifacts exist.
