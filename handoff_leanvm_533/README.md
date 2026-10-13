# leanVM PR #533: full two-half target-sum arithmetic result

The candidate applies to `leanEthereum/leanVM` PR #533 at
`4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.

Original `Encoding.lean` Git blob: `4853d8a398a1ff2762a71473c17c17e175f80b73`.  
Resulting `Encoding.lean` Git blob: `8425ac78992baa500876c873d3b806ef81189ade`.

It replaces only the two arithmetic folding proof bodies (`fold6`,
`fold12`) and appends the proof of `swar42_nat_spec`. Original
statements and all other source lines are unchanged.

The complete, source-pinned Lean 4.31.0 project built successfully,
with 1,713 build jobs: [Actions #38484404732](https://github.com/fraware/lean-project-evidence/actions/runs/38484404732).
All three arithmetic theorems report
`[propext, Classical.choice, Quot.sound]`, without `sorryAx`.
This new lemma proves the **natural-number** SWAR sum over all 42
XMSS digits, using the padded input bounds. The upstream higher-level
`encode_spec` retains `sorryAx`.

[Standalone one-half `swar21_spec` proof](https://github.com/fraware/lean-project-evidence/actions/runs/38483944815)
is available separately. This two-half patch does not include it.

### Clean-room application

```bash
git clone https://github.com/leanEthereum/leanVM.git
cd leanVM
git fetch origin pull/533/head
git checkout --detach 4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d
test "$(git hash-object verification/leanxmss/LeanxmssProofs/Encoding.lean)" = 4853d8a398a1ff2762a71473c17c17e175f80b73
git apply --check /path/to/swar42-and-folds.patch
git apply /path/to/swar42-and-folds.patch
test "$(git hash-object verification/leanxmss/LeanxmssProofs/Encoding.lean)" = 8425ac78992baa500876c873d3b806ef81189ade
```

The separate CI workflow on this branch checks that the original and resulting
Git blobs exactly match. The full Lean build is separately attested in the
run cited above.

### What is still unproved

Fixed-width `Std.U64` correspondence, no-overflow assumptions, digest byte
decoding, padded and target-sum Bool equivalence, and guest acceptance/
rejection branches. Aeneas/Charon extraction, opaque SDK functions, and
VM execution are also separately trusted. Neither `encode_spec` nor
`verify_spec` becomes complete from this arithmetic patch.

**Publication status:** Prepared for external technical review. No upstream
comment, PR, or merge has been created by this handoff.
