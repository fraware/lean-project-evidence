# Source-pinned `Digits.sum` implementation-model proof handoff

Status: **kernel-checked in hosted CI; not submitted to upstream**.
Date: 2026-10-15.

## Exact source and result

- Upstream base: `leanEthereum/leanVM` PR #533 head `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.
- Lean toolchain: `leanprover/lean4:v4.31.0` from `verification/leanxmss/lean-toolchain`.
- Proof-checked research commit: `2de7458b20d060e6bb70a241157caa6bc8df13c2`.
- Replacement proof source: `research/leanvm-pr533/Encoding-swar42-late-source-bound.lean` (supporting arithmetic and range lemmas; includes the original still-admitted `encode_spec`).
- New theorem source: `research/leanvm-pr533/DigitsSumWPSimpall.lean`.
- Executed workflow: `.github/workflows/leanvm-pr533-digits-sum-wp-simpall-20261014.yml`.
- [Successful source-pinned workflow #38767107127](https://github.com/fraware/lean-project-evidence/actions/runs/38767107127): Lean build (1,706 jobs), theorem compilation, and independent `#print axioms` audit.

The verified result is `leanxmss.Proofs.Encoding.digits_sum_impl_spec`. For `lo hi : Std.U64` with `lo.val < 2^63` and `hi.val < 2^63`, it proves that the actual Aeneas-translated `leanxmss.Digits.sum` on `Std.Array.make 2#usize [lo, hi]` returns `ok v`, and that `v.val` equals the sum of the 21 three-bit digits in each word.

The recorded axiom closure for this theorem is exactly:

```text
[propext, Classical.choice, Quot.sound]
```

No `sorryAx` occurs in this theorem's dependencies. The source-file warning about a `sorry` refers to **upstream `leanxmss.Proofs.encode_spec`**, which is a separate declaration and remains unproved. Do not infer that the entire PR #533 proof is axiom-clean.

## Reproduce independently

From an authenticated or public clone of `fraware/lean-project-evidence` at commit `2de7458b20d060e6bb70a241157caa6bc8df13c2`, follow the exact [CI workflow](https://github.com/fraware/lean-project-evidence/blob/2de7458b20d060e6bb70a241157caa6bc8df13c2/.github/workflows/leanvm-pr533-digits-sum-wp-simpall-20261014.yml). It checks out leanVM PR #533 at its exact SHA, copies both source files, verifies the Lean 4.31.0 pin, runs `lake exe cache get`, builds `LeanxmssProofs.Encoding`, compiles `DigitsSumWPSimpall.lean`, and prints the theorem's axiom closure.

Do not substitute upstream main for the pinned PR head: the proof references the exact Aeneas translation and surrounding definitions of #533.

## Proof scope and trusted boundaries

This theorem establishes correspondence between the **Aeneas-translated model of the Rust guest's digit-sum operation** and a mathematical 42-digit sum for padded 63-bit word inputs. It is a universal theorem over the modeled inputs, not a finite-input test.

Separate obligations remain:
1. Complete `encode_spec`: connect the guest's `tweak_hash`, high-bit admissibility check, digit-sum comparison, and digit retrieval to the specification's `wotsEncode`, including both rejection and acceptance.
2. Audit the source-to-translation boundary: the checked translated function corresponds to Rust source `programs/leanxmss/guest/src/lib.rs`, lines 196–210, under Charon/Aeneas translation and external-model assumptions. This theorem does **not** certify translation correctness or the compiled guest.
3. Obtain maintainer review, select the intended integration base, and integrate a focused patch into PR #533 if the Rust/Aeneas path remains part of the deployment verification critical path.
4. Re-run the full dependent axiom audit after incorporation. In particular, `encode_spec`, `verify_spec`, and `verify_ok_iff` are **not yet established without `sorryAx`**.

## Integration recommendation

Upstream already has a minimal source-pinned [two-fold patch](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-both-folds-handoff-20261013/handoff_leanvm_533), which proves `fold6` and `fold12` with their existing statements unchanged. That smaller patch is the easiest initial maintainer review.

The newly checked `digits_sum_impl_spec` is a subsequent, stronger contribution built on a richer SWAR/range proof overlay. Do not present the two artifacts as a single minimal patch until a clean exact-source integration diff has been constructed and checked.

No upstream PR, review comment, or merge has been completed by this handoff.
