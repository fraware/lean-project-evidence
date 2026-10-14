# Exact-source Aeneas U64 operation proofs for leanVM PR #533

**Evidence date:** 2026-10-14.  
**Pinned upstream guest and Aeneas translation:** `leanEthereum/leanVM@4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d` (PR #533), Lean 4.31.0.  
**Previously kernel-checked mathematical facts:** `fold6`, `fold12`, `swar42_nat_spec`, `swar42_packed_first_fits_u64`, `swar42_first_sum_fits_u64`, `swar42_late_folds_fit_u64`, and the later source-instantiated `swar42_all_late_sums_fit_u64`.

## New independent checked Aeneas facts

The source-specific first-three checked additions in the actual `Digits.sum` source have been specialized as four no-`sorryAx` Lean theorems:

- `swar42_guest_first_add_spec`
- `swar42_guest_initial_prefixes`
- `swar42_guest_second_add_spec`
- `swar42_guest_third_add_spec`

[Successful Lean project build and explicit axiom audit #38521837459](https://github.com/fraware/lean-project-evidence/actions/runs/38521837459), 1,713 Lean build jobs.

The actual source's constant masks and the three-bit shift have been specialized as three additional checked theorems:

- `swar42_guest_W_shift_spec`
- `swar42_guest_even_mask_val`
- `swar42_guest_low6_mask_val`

[Successful Lean project build and explicit axiom audit #38522147744](https://github.com/fraware/lean-project-evidence/actions/runs/38522147744), 1,713 Lean build jobs.

For all seven, the observed axiom list is
`[propext, Classical.choice, Quot.sound]`; `sorryAx` is absent.

The source-specific later packed-accumulator bounds are also checked:
[`swar42_all_late_sums_fit_u64` CI #38590684871](https://github.com/fraware/lean-project-evidence/actions/runs/38590684871).

The [same-build composition job #38591457413](https://github.com/fraware/lean-project-evidence/actions/runs/38591457413) is an **independent acceptance gate**: its final verdict is separate from the above results.

## Original translated function diagnostic

[Exact guest attempt CI #38521214202](https://github.com/fraware/lean-project-evidence/actions/runs/38521214202)
reached `leanxmss.Digits.sum` and failed on precisely eight source-level
goals: **seven** Aeneas checked-addition overflow preconditions and **one**
final 42-digit result equality. The failure is a proof gap, not evidence
of a runtime overflow, nor a completed guest correspondence theorem.

A second attempt [CI #38590448264](https://github.com/fraware/lean-project-evidence/actions/runs/38590448264)
also failed with goals still unresolved; the attempted generic tactic was
insufficient. A third proof experiment uses the complete source-specific
late bounds:
[CI #38591839608](https://github.com/fraware/lean-project-evidence/actions/runs/38591839608).
Only its final verdict establishes whether it succeeded.

## Branch-specific scope of the padded-input assumption

The exact translated guest `Leanxmss/Funs.lean` first computes
`i := low ||| high`, then `i3 := i >>> (W * V / 2)` and returns
`ok none` if `i3 != 0#u64`. Only the other branch executes
`Digits.sum (Array.make 2#usize [low, high])`
(source lines 564–594 at the pinned PR #533 head).
Given `W = 3` and `V = 42`, that shift is 63. An initial bitvector proof [CI #38592278322](https://github.com/fraware/lean-project-evidence/actions/runs/38592278322)
compiled, but `#print axioms` exposed the additional native solver axiom
`leanxmss.Proofs.Encoding.guest_padded_or_iff._native.bv_decide.ax_1_5`.
That attempt is **excluded from the acceptable kernel-only evidence**.
The replacement uses Lean's established `BitVec.ushiftRight_or_distrib`
and `BitVec.or_eq_zero_iff` theorems, under a full multiline axiom
whitelist CI on the same source-pinned branch.

This control-flow guard explains why a padded-input `Digits.sum`
lemma is sufficient for the `encode` success branch, assuming the
guard equivalence is established. It does **not** prove that
`Digits.sum` always succeeds for arbitrary callers and inputs,
nor that `encode_spec` is complete.

## Remaining boundary

The natural arithmetic and checked-operation lemmas have not yet been
composed into an end-to-end `Digits.sum` weakest-precondition theorem.
The complete `encode_spec` and dependent `verify_spec` still include
`sorryAx`. Their full correspondence also depends on guest/spec
byte-order and padding equivalence, precise reject/accept behavior,
source translation, SDK models, and actual VM semantics.

A separate [high-bit OR condition experiment #38592278322](https://github.com/fraware/lean-project-evidence/actions/runs/38592278322)
addresses the `encode` spare-bit rejection predicate and must not be
counted as kernel-checked unless its run completes successfully.

No external maintainer accepted or merged any of these experimental
proofs. The integration account lacks upstream GitHub comment permissions.
