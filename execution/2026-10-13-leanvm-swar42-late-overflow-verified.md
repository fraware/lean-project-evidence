# Kernel-checked nonwrapping SWAR late-fold bounds

**Source pin:** `leanEthereum/leanVM` PR #533 at `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.  
**Proof source commit:** `fraware/lean-project-evidence@e05cf74c3eee4eac4ee6c0f3992148bb8d086c52`.  
**Lean CI:** [run #38518487036](https://github.com/fraware/lean-project-evidence/actions/runs/38518487036), successful, 1,713 build jobs.

`leanxmss.Proofs.Encoding.swar42_late_folds_fit_u64` states that the
12-bit packed accumulator and its three successive shift/add fold
accumulators are all below `2^64`, provided the first five packed
12-bit fields are `≤56` and the final field `≤14`.
Those maxima follow from the sum of eight, respectively two,
base-eight chain digits drawn from two padded digest halves.

The proof uses exact monotone maximum bounds for each intermediate:
```text
s1 ≤ 16156667512422105144
s2 ≤ 16160612011326505072
s3 ≤ 16160612974574043360
s4 ≤ 16160612974574100774
```

The actual axiom report is:

```text
'leanxmss.Proofs.Encoding.swar42_late_folds_fit_u64' depends on axioms: [propext, Classical.choice, Quot.sound]
```

No `sorryAx` dependency occurs in this theorem. The same project build
also rechecked the established `swar42_nat_spec` arithmetic theorem.

## Remaining

The exact value of the guest's **first** masked `U64` sum is not
established by this later-stage bound. An independent source-backed
instantiation of the `val64` first packed field bound is being tested on
`research/leanvm-pr533-swar42-first-sum-bound-20261013`.

Further, the finite-word semantics of Aeneas `Std.U64` addition/shift/AND
must be connected to these bounded natural values before claiming
source-level nonwrapping behavior in `leanxmss.Digits.sum`.
The original `encode_spec` remains admitted.

No upstream merge or maintainer review occurred by completing this proof.
