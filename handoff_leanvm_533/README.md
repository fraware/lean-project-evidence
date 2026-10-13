# PR #533: verified SWAR21 and both arithmetic folding lemmas

Source: `leanEthereum/leanVM@4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.  
Upstream original `Encoding.lean` Git blob: `4853d8a398a1ff2762a71473c17c17e175f80b73`.  
Candidate `Encoding.lean` Git blob: `6c3adec7a90ce8883a8501e9e4a3acbcca3df2db`.

The patch replaces the admitted bodies of `fold6` and `fold12` and adds
a new self-contained theorem `swar21_spec`. It leaves the signatures of all
existing declarations, the specification, and guest source unchanged.

[Source-pinned complete Lean CI #38483944815](https://github.com/fraware/lean-project-evidence/actions/runs/38483944815)
built 1,713 jobs and printed the following axiom closure for all three
arithmetic theorems: `[propext, Classical.choice, Quot.sound]`, with no
`sorryAx`. `encode_spec` and `verify_spec` remain admitted.

Apply against the exact pinned PR #533 Git checkout:

```bash
git apply --check swar21-and-folds.patch
git apply swar21-and-folds.patch
git hash-object verification/leanxmss/LeanxmssProofs/Encoding.lean
```

The hash must equal `6c3adec7a90ce8883a8501e9e4a3acbcca3df2db`. The separate source-identity
workflow proves reproducible reapplication; it does **not** substitute for
the independent full Lean build cited above.

**Trust boundary:** `swar21_spec` uses unbounded natural-number arithmetic
for a 21-digit half word under a proven top-bit bound. Source-level U64
nonoverflow, aggregation of both halves, the digest representation, and the
full verifier and VM assumptions remain separate obligations.

No upstream comment, PR, or merge is represented by this handoff. The
connected GitHub integration cannot write to leanEthereum.

### Pinning and independent reconstruction

```bash
git clone https://github.com/leanEthereum/leanVM.git
cd leanVM
git fetch origin pull/533/head
git checkout --detach 4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d
test "$(git hash-object verification/leanxmss/LeanxmssProofs/Encoding.lean)" = 4853d8a398a1ff2762a71473c17c17e175f80b73
```

Retrieve `swar21-and-folds.patch` from this branch and apply it from the
root of the detached checkout. Then run `lake exe cache get && lake build`
in `verification/leanxmss` and examine the axiom report.

The patch identity job is separate from the completed Lean kernel build.
