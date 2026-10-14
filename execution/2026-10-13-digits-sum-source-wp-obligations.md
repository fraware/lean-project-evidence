# Source-derived weakest-precondition frontier for Digits.sum

**Source:** leanEthereum/leanVM PR #533, exactly
`4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`,
`verification/leanxmss/Leanxmss/Funs.lean`,
Aeneas-generated `leanxmss.Digits.sum`.
**Diagnostic CI:** [#38521214202](https://github.com/fraware/lean-project-evidence/actions/runs/38521214202),
failure at a fully elaborated source-level proof term, not an admitted theorem.

## What the pinned proof engine returned

The original function was unfolded on two padded digest words.
Aeneas's `step*` tactic recognized the exact source operations,
established array indexing, translated both three-bit shifts and all
six- and 12/24/48-bit shift postconditions, and created eight remaining
goals:

1. First checked addition: `(low & EVEN) + ((low >>> 3) & EVEN) ≤ U64.max`.
2. Second addition: previous sum plus `(high & EVEN) ≤ U64.max`.
3. Third addition: previous result plus `((high >>> 3) & EVEN) ≤ U64.max`.
4. LOW6 pair fold: `(s & LOW6) + ((s >>> 6) & LOW6) ≤ U64.max`.
5. `s1 + (s1 >>> 12) ≤ U64.max`.
6. `s2 + (s2 >>> 24) ≤ U64.max`.
7. `s3 + (s3 >>> 48) ≤ U64.max`.
8. Exact result equality between `(i14 & 4095).val` and the sum of all
   42 specification-style base-eight chain digits.

These are proof obligations, **not proved facts**. Their number and
form are directly observed in the Lean error output from that run.
No `sorry` was inserted to suppress them.

## Available checked mathematical lemmas

The same exact-source Lean project previously checked:

- `fold6`, `fold12`;
- `swar42_nat_spec`, the two-half 42-digit SWAR arithmetic identity;
- `swar42_packed_first_fits_u64`;
- `swar42_first_sum_fits_u64`;
- `swar42_late_folds_fit_u64`.

All are axiom-clean in
[combined CI #38519333671](https://github.com/fraware/lean-project-evidence/actions/runs/38519333671).

## The reusable executable bridge

The pinned Aeneas library exposes:

- `UScalar.add_spec` with explicit no-overflow precondition;
- `UScalar.ShiftRight_spec`, with shift count in range;
- `UScalar.val_and`, relating machine and natural-bit operations.

Two experiments now target their precise application:
- [first checked guest addition](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-u64-checked-add-wp-20261013);
- [all three initial checked additions](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-u64-prefix-additions-20261013).

A separate [shift and mask specialization](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-u64-shift-mask-wp-20261013)
targets the guest's concrete constants and types.

**First source-specific checked addition completed.**
[CI #38521832642](https://github.com/fraware/lean-project-evidence/actions/runs/38521832642)
passed the full 1,713-job Lean build and printed:

```text
'leanxmss.Proofs.Encoding.swar42_guest_first_add_spec' depends on axioms: [propext, Classical.choice, Quot.sound]
'leanxmss.Proofs.Encoding.swar42_guest_initial_prefixes' depends on axioms: [propext, Classical.choice, Quot.sound]
```

These establish, for the exact guest's first masked addition, successful
Aeneas checked-add execution with the mathematical sum, together with
source-specific bounds for all three initial prefix sums.

**All first-stage checked additions completed.**
[Same-build CI #38521837459](https://github.com/fraware/lean-project-evidence/actions/runs/38521837459)
compiled all 1,713 build jobs and independently reported
`[propext, Classical.choice, Quot.sound]` for
`swar42_guest_first_add_spec`, `swar42_guest_second_add_spec`,
`swar42_guest_third_add_spec`, and the common prefix-bound lemma.
These prove the Aeneas checked-addition contracts under the exact
operand-value premises at the first three guest arithmetic calls.
The entire source proof has no `sorryAx` in those dependencies.

[Clean-room source identity CI #38522667380](https://github.com/fraware/lean-project-evidence/actions/runs/38522667380)
also completed green. It independently reconstructs the parent PR #533
`Encoding.lean` candidate and the additional proof module using
content-addressed Git blob checks.
[Handoff package](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-checked-add-handoff-20261013/handoff_leanvm_533).

The direct full-function `Digits.sum` theorem remains unproved.
Other experimental helper branches have independent kernel and axiom gates.

## Next full-function proof step

Propagate the padded input and actual `low`/`high` array-index facts into
the seven addition preconditions; establish exact each-stage value
equations, and use `swar42_nat_spec` for the final sum.

The `U64` semantic refinement and `Digits.sum` function theorem
are distinct from complete `encode_spec`, which still needs digest
byte representation, spare-bit admissibility, and rejection/success
branch correspondence.

Upstream PR #533 is still draft, with no upstream review or merge
of these research candidates at the time this evidence was recorded.
