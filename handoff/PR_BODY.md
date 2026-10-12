## Summary

This patch tightens the validator's XMSS signing boundary in `leanSpec`:

- Rejects signing outside the secret key's activation interval and detects preparation that stops progressing, eliminating the observed nonterminating preparation loop.
- Checks that the proposal and attestation secret-key containers agree with the validator public keys recorded in state before signing. A mismatched key is refused before one-time key use.
- Moves deterministic block proof prerequisites before proposal signing and preserves the proposer index when traversing attestation proof participants.
- Rolls back an unsigned block-production store update only for known pre-signature refusal; avoids incorrectly rolling back state after a possible signature.
- Skips a rejected individual attestation duty without preventing other registered validators from signing.
- Adds three upstream validator regression tests for expired signing keys, mismatched proposal keys and per-validator attestation-key refusal.

The patch is pinned to `leanEthereum/leanSpec@0b7d33ecbc9ee2435759c92de4da4d08d7faf1c8` and changes only `src/lean_spec/node/validator/service.py` and `tests/node/validator/test_service.py`.

## Executed evidence

In an independent GitHub Actions checkout of the pinned leanSpec revision with the exact patched files:

- Ruff lint and Ruff format checks passed.
- Whole-project `ty check` passed.
- **52/52 validator tests passed** ([strict validator CI](https://github.com/fraware/lean-project-evidence/actions/runs/38310950336)).
- **2,130 standard pytest tests passed**, with **90.66% total coverage**, above the 90% threshold.
- **1/1 multi-node interoperability test passed** ([full validation CI](https://github.com/fraware/lean-project-evidence/actions/runs/38311670261)).
- A [separate interoperability run](https://github.com/fraware/lean-project-evidence/actions/runs/38313058359) also passed.
- A [fresh-checkout patch witness](https://github.com/fraware/lean-project-evidence/actions/runs/38313259507) verified `git apply`, `git diff --check` and exact post-patch Git blob hashes against the CI-tested files.

Full [evidence and portable diff](https://github.com/fraware/lean-project-evidence/tree/research/leanspec-xmss-handoff-20261012/handoff).

The standard pytest run honors upstream exclusions for consensus fixture generation and interoperability. Those are not silently counted as passing tests.

## Security boundary

This is a *validator signing-preconditions and liveness* correction. It **does not** enforce durable at-most-once XMSS key usage across crashes, backups, parallel signers or restarts, nor does it prove the cryptographic implementation equivalent to the Lean specification. Those remain separate issues, including #1203 and #1204. The patch also does not change signature-scheme cryptography.

## Reviewer focus

Please review the order of preflight relative to irreversible XMSS `sign`, the typed refusal and rollback boundaries, the local/public key binding check, and the per-validator attestation continuation behavior. Independent external CI is linked above; I would welcome upstream CI and maintainer guidance on whether to split the liveness and key-binding portions into separate changes.