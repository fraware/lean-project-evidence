# First checked leanVM implementation-arithmetic lemma: `fold12`

**Date:** 2026-10-13  
**Status:** **Checked by Lean 4.31.0** against pinned upstream PR #533; NOT YET ACCEPTED UPSTREAM.

## Exact sources

- Upstream implementation/proof baseline: `leanEthereum/leanVM@4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.
- Source `verification/leanxmss/LeanxmssProofs/Encoding.lean` initial Git blob: `4853d8a398a1ff2762a71473c17c17e175f80b73`.
- Resulting complete source Git blob: `3f135ec7d108a821371f3db4b8e63c339665d823`.
- Candidate commit: `fraware/lean-project-evidence@9617879779e726d93c708dec8e2e552f862bd87a`.
- [Exact Lean build and `#print axioms` log](https://github.com/fraware/lean-project-evidence/actions/runs/38477725808), successful (1,713 build jobs).
- [Minimal upstream-applicable patch](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-fold12-handoff-20261013/handoff_leanvm_533).

## What changed

The originally admitted `fold12` theorem states that bitwise folding of six
bounded base-4096 fields yields their sum in the low 12 bits. Its existing
statement and every other source line were unchanged.

A naive `norm_num [val]; omega` attempt failed because nested quotients
were unconstrained. The passing proof decomposes the six-field division into
successive explicit quotient identities, bounds the intermediate remainders,
and concludes the final low-bit identity using Presburger arithmetic.

The resulting axiom audit is exactly:

```text
'leanxmss.Proofs.Encoding.fold12' depends on axioms: [propext, Classical.choice, Quot.sound]
```

**No `sorryAx`** occurs in the `fold12` theorem dependencies.

The whole verifier theorem is still incomplete:

```text
'leanxmss.Proofs.verify_spec' depends on axioms: [propext, sorryAx, Classical.choice, Quot.sound]
```

This is a substantive, self-contained formal result, not universal guest
equivalence, a proof of the SDK/VM external models, or upstream acceptance.

## Current follow-up

1. Independently verify that `fold12.patch` applies cleanly to the pinned
   PR #533 source and reconstructs the exact checked Git blob.
2. Evaluate the complementary `fold6` proof in its separate branch.
3. Integrate both only if source hashes and Lean proof dependencies match.
4. Continue `encode_spec` and the translation/SDK-model trust audit.
5. Publish the proof to upstream through a permitted contributor identity.

An attempt to submit a GitHub comment to PR #533 via the current connected
GitHub integration returned HTTP 403 `Resource not accessible by integration`.
**No upstream comment was posted.**
