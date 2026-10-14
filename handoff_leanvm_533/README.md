# leanVM PR #533: source-pinned SWAR arithmetic and 64-bit range proof package

**Upstream commit** `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.  
**Original `Encoding.lean` Git blob** `4853d8a398a1ff2762a71473c17c17e175f80b73`.  
**Candidate `Encoding.lean` Git blob** `7460dd8c3920c39e2d599ba36d16b77c3d444d1e`.

This one-file candidate preserves the original declarations and guest semantics,
replaces the `fold6` and `fold12` admissions with checked proof bodies,
and adds the following bounded-arithmetic lemmas:

- `swar42_nat_spec`, complete 42-digit mathematical SWAR sum
  ([CI #38484404732](https://github.com/fraware/lean-project-evidence/actions/runs/38484404732))
- `swar42_packed_first_fits_u64`, initial field packing below `2^64`
  ([CI #38518388192](https://github.com/fraware/lean-project-evidence/actions/runs/38518388192))
- `swar42_first_sum_fits_u64`, source-based first masked two-word aggregation
  below `2^64` ([CI #38519013331](https://github.com/fraware/lean-project-evidence/actions/runs/38519013331))
- `swar42_late_folds_fit_u64`, later packed shift/add accumulators below `2^64`
  ([CI #38518487036](https://github.com/fraware/lean-project-evidence/actions/runs/38518487036)).

**Combined same-build gate passed**:
[Actions #38519333671](https://github.com/fraware/lean-project-evidence/actions/runs/38519333671),
1,713 Lean build jobs, with axiom reports excluding `sorryAx` for
`swar42_nat_spec` and all three new range theorems.
`encode_spec` still includes `sorryAx`.

**Clean-source patch identity gate passed**:
[Actions #38519933956](https://github.com/fraware/lean-project-evidence/actions/runs/38519933956).
The exact pinned PR source was reconstructed to the same candidate Git blob.

### Exact reconstruction

In a checkout detached at the pinned PR head:

```bash
test "$(git hash-object verification/leanxmss/LeanxmssProofs/Encoding.lean)" = 4853d8a398a1ff2762a71473c17c17e175f80b73
git apply --check swar42-and-range.patch
git apply swar42-and-range.patch
test "$(git hash-object verification/leanxmss/LeanxmssProofs/Encoding.lean)" = 7460dd8c3920c39e2d599ba36d16b77c3d444d1e
git diff --check
```

### Remaining proof boundaries

These theorems are quantitative bounds in Lean's natural-number model.
They do **not** themselves supply an Aeneas weakest-precondition theorem
that the guest `Std.U64` code follows the same values. That needs each
actual `U64.add_spec` precondition and shift/bitwise postcondition,
plus the byte/word model and admissibility branches.

`encode_spec` and the top-level verifier still have `sorryAx`;
external Charon/Aeneas translation correctness, SDK models, and VM
semantics are additional premises. No upstream review or merge is claimed.
