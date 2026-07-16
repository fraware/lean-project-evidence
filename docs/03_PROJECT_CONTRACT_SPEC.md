# Project Contract specification

## Location

`.lean-project-contract/`

## Files

- `project.yaml`
- `intent/project.md`
- `terminology.yaml`
- `obligations.yaml`
- `policies.yaml`
- `review.yaml`
- `tests/`

## Contract-authoring rule

Record only information that changes an acceptance decision or makes a downstream milestone measurable.

Every minute of contract maintenance belongs in the TPPR denominator.

## Change control

Contract changes are reviewed separately from candidate changes.

A candidate cannot modify its own acceptance contract in the same evidence run.

Contract version and content hash are recorded in every packet.
