# Explicit non-claims (canonical)

This is the **canonical** anti-oversell list for Lean Project Evidence.
CLI outputs (`lpe pilot summary`, `lpe pilot dry-run`), `lpe doctor`,
`lpe research status`, and partner `NON_CLAIMS.md` scaffolds must stay
consistent with this document.

**Software metrics ≠ causal utility.** Dry-run automation rates, warehouse
aggregations, and TPPR snapshots from instrumentation do **not** clear
ENGINEERING_SPEC §21 and do **not** prove LPE improves outcomes.

## Non-claims

1. **ENGINEERING_SPEC §21 is not passed.** Shadow-pilot and learned-routing
   criteria are unmet. Instrumentation and fixture dry-runs do not clear them.
2. **No causal utility / causal TPPR** from dry-runs or `lpe pilot summary`
   warehouse metrics alone.
3. **No R3/R4 auto-ACCEPT or single-reviewer production ACCEPT** (ADR 0003).
   `lpe review record` refuses ACCEPT for R3/R4; auto-accept remains impossible.
   Qualified human acceptance uses `lpe review attest` + `lpe review accept-quorum`
   only (still not §21 clearance). Gates escalate high-risk candidates.
4. **No Mathlib-scale elaborator-complete kernel truth.** Fixture/project
   toolchain extraction is not Mathlib-scale. Regex-stub findings are
   incomplete; empty `axioms_used` is not axiom closure.
5. **M6 / M7 training (EPIC-039 / EPIC-040) blocked until §21.** Training
   entrypoints do **not** exist. `lpe routing` / `lpe research train` exit
   non-zero. Deterministic routing baseline (`deterministic_baseline.v1`) is
   wired into review-question selection as an explicit `baseline_id` for a
   future held-out comparison; synthesis fixture harness is a scaffold only.
   Neither is learned routing or model training.
6. **Dry-run / warehouse tests are not a study.** Synthetic corpora do not
   substitute for prospective human expert review under a frozen analysis plan.
7. **No WORM / external root of trust** for the utility ledger (archive + seal
   are integrity aids, not hardware WORM).
8. **No opaque quality scalars** (ADR 0002).

## Engineering enforcement

| Surface | Behavior |
| --- | --- |
| `lpe pilot summary` / `dry-run` | Mandatory `NON_CLAIMS` block; refuse `--claim-section-21` / `--claim-causal` |
| `lpe research status` | Prints M6–M7 / EPIC-039/040 / §21 gate matrix |
| `lpe routing` / `lpe research train` | Exit non-zero: blocked until §21 |
| `lpe lean status` / `lpe doctor` | Extractor mode + “not Mathlib-scale” warning; ADR 0003 active check |
| Packet markdown | Regex-stub banner when extractor is incomplete |
| `lpe.routing` / `lpe.synthesis` `.train()` | Raises `ResearchGateBlocked` |

## Related

- `VALIDATION_REPORT.md` — honesty preamble and audit §9 mirror
- `docs/26_SPEC_ROADMAP_AUDIT.md` §8–9 — “do not claim” scorecard
- `docs/27_PARTNER_PILOT_HANDOFF.md` — partner pilot still deferred
- `docs/adr/0003-human-authority.md` — R3/R4 human authority
- `docs/ENGINEERING_SPEC.md` §21 — scientific clearance criteria (not claimed)
