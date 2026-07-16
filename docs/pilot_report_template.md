# Pilot report template

Use this template when publishing M5 results (ISSUE-038). Clearly separate software claims from causal claims.

## Summary

- **Project:**
- **Pilot period:**
- **Candidates analyzed:** N = 
- **Condition tags:**

## Software utility (supported claims)

Report only what the system measured directly:

| Metric | Result | Target |
| --- | --- | --- |
| Packet automation rate | | ≥80% |
| Exact-environment reproduction | | ≥90% |
| Instrumentation overhead | | <10% expert time |
| Ledger/TPPR export completeness | | 100% verifiable |

## Reviewer feedback (qualitative)

- Evidence dimensions understood: yes / partial / no
- Actionable findings: examples
- Friction points: examples

## Causal utility (limitations required)

State explicitly:

> This pilot does **not** establish that the evidence system causally improves TPPR or proof quality. Observed TPPR changes may reflect selection, obligation mix, or reviewer practice.

If inferential analysis was pre-registered, describe it here. Otherwise, limit to descriptive TPPR and expert-time tables.

## Known limitations

- Lean extraction uses regex stub when toolchain unavailable.
- Semantic providers emit UNKNOWN until full M4 integration.
- M6/M7 learned routing and synthesis were not trained (scaffold only).

## Data availability

- Ledger export path:
- Schema version:
- Reproduction command: `lpe evidence compile --project ... --candidate ... --skip-build`

## Recommendations

- Proceed to M6: yes / no / conditional
- Blockers:
