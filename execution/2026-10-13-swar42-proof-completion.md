# Kernel-checked two-half XMSS target-sum arithmetic

**Date:** 2026-10-13  
**Pinned upstream:** `leanEthereum/leanVM` PR #533 head `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.  
**Proof candidate commit:** `fraware/lean-project-evidence@74b34f13b147e874951d13840f4927c729d115cc`.  
**Lean CI:** [run #38484404732](https://github.com/fraware/lean-project-evidence/actions/runs/38484404732), success; complete Lean 4.31.0 project, 1,713 build jobs.

## Proved proposition

`leanxmss.Proofs.Encoding.swar42_nat_spec` takes two natural-number
representations `x`, `y` of XMSS digest halves, each below `2^63`.
It proves that the guest's combined sequence of EVEN field masks, adjacent
6-bit field shifts/additions, LOW6 field masks, 12-bit and 24-bit sums, and
final low-12-bit extraction equals **the sum of exactly 42 base-eight
digits**, 21 from each half.

It uses the pre-existing checked `land_even` and `land_odd` identities and
our checked `fold6` and `fold12` results, with explicit field
bounds (`c0`–`c9 < 64`, `c10 < 16`, and each packed field `≤56`).
The bound `≤56` is critical because up to eight three-bit digits
from two halves are summed into a single 12-bit field.

Actual axiom report:

```text
'leanxmss.Proofs.Encoding.swar42_nat_spec' depends on axioms: [propext, Classical.choice, Quot.sound]
'leanxmss.Proofs.Encoding.fold6' depends on axioms: [propext, Classical.choice, Quot.sound]
'leanxmss.Proofs.Encoding.fold12' depends on axioms: [propext, Classical.choice, Quot.sound]
'leanxmss.Proofs.encode_spec' depends on axioms: [propext, sorryAx, Classical.choice, Quot.sound]
```

No `sorryAx` occurs in the three checked arithmetic theorem dependencies.
The complete `encode_spec` theorem **is still admitted**.

## Artifact identities and upstream handoff

The original pinned `Encoding.lean` Git blob is
`4853d8a398a1ff2762a71473c17c17e175f80b73`.
The source-pinned candidate blob is
`8425ac78992baa500876c873d3b806ef81189ade`.

[Independent review patch](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-swar42-handoff-20261013/handoff_leanvm_533)
replaces the two admitted fold proofs and adds this two-half theorem.
Independent patch-identity CI runs on the handoff branch and must be checked
before describing that separate handoff gate as complete.

## Remaining substantive proof obligations

1. **Fixed-width refinement.** Connect the guest's `Std.U64` AND, shift,
   addition, and final mask operations to these natural-number identities.
   Prove the required intermediate upper bounds and absence of wrapping.
2. **Digest representation.** Connect little-endian guest digest words to the
   specification's `Internal.digestWord` and indexed digits.
3. **Admissibility.** Prove that the guest's top-bit OR/shift test implements
   `Internal.padded` and its constant-sum check implements `onTarget`.
4. **Control flow and results.** Preserve `none` and `some` behavior,
   per-index digits, and no-panic scope to discharge `encode_spec`.
5. **Higher theorem closure and external models.** Re-run the axiom closure
   for `verify_spec`, `verify_ok_iff`, `main_spec`, and
   `main_terminates`. Audit Charon/Aeneas, closure patches, SDK models,
   hand-transcribed main, and actual VM semantics as distinct premises.

The proof is a substantial source-derived mathematical result and a direct
input to an implementation-correspondence theorem. It is **not yet a proof
of the full guest or VM**, nor an accepted upstream contribution.
