# Kernel-checked SWAR digit-sum bridge, 21 XMSS digits

**Evidence date:** 2026-10-13.  
**Source base:** leanEthereum/leanVM PR #533 at `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.  
**Proof candidate commit:** `fraware/lean-project-evidence@16c9f2eb176b01a97b9a07975219cbafbdfa13b3`.  
**Reproducible Lean build:** [GitHub Actions #38483944815](https://github.com/fraware/lean-project-evidence/actions/runs/38483944815) (**success**, 1,713 Lean build jobs).

## Exact new result

`leanxmss.Proofs.Encoding.swar21_spec` connects the full arithmetic
bit-mask and shift-fold algorithm to the sum of the 21 base-eight digits of
one digest half, under `x < 2^63`, corresponding to its spare bit being zero.
It composes the previously checked `land_even`, `land_odd`, `fold6`,
and `fold12` lemmas, with explicit field bounds.

The source-pinned same-build axiom report is:

```text
'leanxmss.Proofs.Encoding.swar21_spec' depends on axioms: [propext, Classical.choice, Quot.sound]
'leanxmss.Proofs.Encoding.fold6' depends on axioms: [propext, Classical.choice, Quot.sound]
'leanxmss.Proofs.Encoding.fold12' depends on axioms: [propext, Classical.choice, Quot.sound]
'leanxmss.Proofs.encode_spec' depends on axioms: [propext, sorryAx, Classical.choice, Quot.sound]
```

**Important:** `swar21_spec` is an arithmetic theorem over natural numbers.
The actual guest's `Digits.sum` folds two half words together and performs
bounded fixed-width arithmetic. A full proof still needs the combined
42-digit relationship, a no-overflow/refinement bridge between fixed-width
and natural-number arithmetic, the little-endian digest mapping, the two
spare-bit checks, and the exact admissibility/rejection correspondence.
`encode_spec` remains unproved and neither source translation nor VM/SDK
model correctness is established by this lemma.

## Why this result is reusable

The proof isolates a mathematically checkable property of the SWAR algorithm
and uses two generic field-folding lemmas. Its statement is independent of
a signature verifier's control flow. It is suitable as a component for
additional source-level equivalence proofs, subject to their concrete
representation and fixed-width semantics.

## Remaining next gate

Complete the two-half `Digits.sum` correspondence and prove the necessary
finite-word nonoverflow conditions before incorporating the result into
`encode_spec`. Check `#print axioms` of every theorem in its claimed
dependency chain. No upstream PR or comment was created by this result.
