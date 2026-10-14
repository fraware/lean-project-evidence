# First kernel-checked 64-bit SWAR range invariant

**Date and provenance:** 2026-10-13 local, source `leanEthereum/leanVM` PR #533 at
`4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.  
**Proof commit:** `fraware/lean-project-evidence@afda3853a5ced8f5da719436ddb12f400d3244f1`.  
**Native Lean acceptance:** [GitHub Actions #38518388192](https://github.com/fraware/lean-project-evidence/actions/runs/38518388192), success; 1,713 build jobs.

The proved theorem `leanxmss.Proofs.Encoding.swar42_packed_first_fits_u64` states:

For natural-number digit-sum fields `c0...c9 ≤ 28` and `c10 ≤14`,
their base-64 packing `val 64 [c0,...,c10]` is strictly below `2^64`.

It is the mathematical range fact needed by the first aggregate step
of the guest's SWAR algorithm. The extreme packed value is
`16653310622098900764 = 0xe71c71c71c71c71c < 2^64`.

The actual `#print axioms` output:

```text
'leanxmss.Proofs.Encoding.swar42_packed_first_fits_u64' depends on axioms: [propext, Quot.sound]
```

**Remaining:** Instantiate these field bounds on the real two-word masked
digest expression; map the guest's `U64` addition and shift semantics
onto nonwrapping natural arithmetic. The statement does not establish
that a VM expression has exactly this value, nor close `encode_spec`.

A dedicated source-identity-pinned instantiation is under test on
`research/leanvm-pr533-swar42-first-sum-bound-20261013`; its outcome
must be independently verified before making a claim of success.

The 12/24/48-bit subsequent accumulator range lemma is a separate
candidate under test on `research/leanvm-pr533-swar42-fold-overflow-20261013`.

No upstream comment, PR, or merge is represented by this result.
