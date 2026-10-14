# LeanVM padding bitvector: compiler-trust boundary

**Date:** October 13, 2026, local (workflow UTC October 14).  
**Source:** `leanEthereum/leanVM` PR #533 at `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.  
**CI:** [#38515722655](https://github.com/fraware/lean-project-evidence/actions/runs/38515722655), Lean 4.31.0 full 1,713-job build successful.

## Exact results

The isolated padding bridge declared two propositions over `BitVec 64`:

1. `top_bit_clear_iff_unsigned_small`: shifting the high bit away returns
   zero exactly for unsigned words below the top-bit threshold.
2. `or_top_bit_clear_iff_both_words`: the OR of two words has its high bit
   clear exactly if both words have that bit clear.

Both compiled with `bv_decide` and **no `sorryAx`**. However the
**actual** `#print axioms` log includes dedicated native computation
axioms, notably
`_native.bv_decide.ax_1_5`, in **both** theorems' dependency closures.

In Lean 4.31, this means that the decision procedure's compiled execution
result is trusted through a generated axiom. The source is not a
kernel-only proof of the two bitvector propositions. Official Lean
reference: https://lean-lang.org/doc/reference/latest/ValidatingProofs/

The independent `swar42_nat_spec` arithmetic theorem in the same build
has axiom dependencies `[propext, Classical.choice, Quot.sound]`, without
a native `bv_decide` axiom. Do not conflate these levels of trust.

## Acceptance policy

- The two padding propositions are **compiler-trusted bitvector results**.
- They are **not** presented as kernel-only theorems.
- They are not yet a proof of `wotsEncode`'s `Internal.padded`
  correspondence because digest byte/word representation and guest error
  handling still need proof.
- If they become part of the final trusted claim, either justify the
  compiler-trust assumption explicitly or reprove them using an
  axiom-free Lean derivation.
- Before importing into upstream, perform a complete axiom audit on the
  final theorem and compare it with maintainers' intended trust policy.

The test workflow on `research/leanvm-pr533-padding-bitvector-bridge-20261013`
has been updated to state and confirm the native-axiom condition in logs,
instead of treating absence of `sorryAx` as sufficient.

**Publication:** No upstream comment or PR was created.
