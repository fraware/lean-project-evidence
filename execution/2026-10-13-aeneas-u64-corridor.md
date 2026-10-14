# Exact Aeneas U64 verification corridor for leanXMSS Digits.sum

**Guest source:** `leanEthereum/leanVM` PR #533,
`verification/leanxmss/Leanxmss/Funs.lean`, upstream SHA
`4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.
**Pinned external semantics:** `AeneasVerif/aeneas@aa66752b15d02335f936f607b5ad5b9fecb65b13`,
as required by `verification/leanxmss/lakefile.lean`.
This source exactness matters: relying on latest Aeneas definitions is not
an acceptable correspondence proof.

## Independently checked Aeneas semantic interfaces

- `backends/lean/Aeneas/Std/Scalar/Ops/Add.lean`, lines 116–123:
  `UScalar.add_spec` is a weakest-precondition theorem requiring
  `x.val + y.val ≤ UScalar.max ty`, concluding that `x + y`
  returns a value equal to the **mathematical** sum. The concrete
  `U64.add_spec` specialization is generated at lines 135–137.
- `backends/lean/Aeneas/Std/Scalar/Bitwise.lean`, lines 168–180:
  `UScalar.ShiftRight_spec` and its `U64` specialization give
  `z.val = x.val >>> shift` for a shift strictly below word width.
  The source also treats signed shift variants separately.
- Same `Bitwise.lean`, line 342:
  `UScalar.val_and` provides
  `(x &&& y).val = x.val &&& y.val`.

These are external checked library lemmas, **not** newly proved results
of this project. Their hypotheses must be discharged at every actual
guest program operation before the guest-source correspondence is claimed.

## Actual code path and proof obligations

In `Leanxmss/Funs.lean` lines 500–522, `Digits.sum` first selects
`low` and `high`, uses the EVEN mask and W-bit shifts, adds four
partial terms, applies LOW6, folds by 6, then shifts and adds by
12, 24, and 48 before the final `&&& 4095#u64`.

To establish `Digits.sum` correctness on padded digest words:
1. Use Aeneas `step*` / `exists_ok_of_spec` with the actual
   `leanxmss.Digits.sum` result type, preserving all error paths.
2. Carry a `Std.U64.val` invariant through each `AND` and shift.
   The actual shift parameters are 3, 6, 12, 24, and 48, all
   strictly below the 64-bit width.
3. At every guest addition, discharge the corresponding
   `U64.add_spec` precondition. Combine the first packed-field bound,
   the digest-word instantiation, and the late fold bounds. Do not
   infer nonwrapping from the final low-bit mask.
4. Instantiate the already-proved `swar42_nat_spec`; identify the result
   with the sum of the 42 actual specification digits.
5. Establish the top-bit and digest-word representation mapping before
   using this result to justify `Internal.onTarget`.
6. Prove the `some` / `none` behavior and exact digit retrieval in
   `encode_spec`; only then inspect the higher verifier axiom closure.

## Status boundaries

- `fold6`, `fold12`, and `swar42_nat_spec` are kernel checked.
- `swar42_packed_first_fits_u64` is kernel checked:
  [CI #38518388192](https://github.com/fraware/lean-project-evidence/actions/runs/38518388192).
- `swar42_late_folds_fit_u64` is kernel checked:
  [CI #38518487036](https://github.com/fraware/lean-project-evidence/actions/runs/38518487036).
- Source-backed first digest-word instantiation and same-build composition
  must be confirmed independently before being declared done.
- The complete `Digits.sum` weakest-precondition theorem, digest
  representation, and higher `encode_spec` are **not yet proved**.

The rationale for this note is to prevent a mathematical range theorem
from silently being promoted to a verified source-level guest result.
