# Composite checked SWAR42 arithmetic and U64 range evidence

Date: 2026-10-13 local (CI completed 2026-10-14 UTC).  
Source pin: `leanEthereum/leanVM` PR #533 `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.  
Proof commit: `fraware/lean-project-evidence@f52d9f2e457689665c6800bee2b84f27267a6119`.  
**Verified Lean CI:** [#38519333671](https://github.com/fraware/lean-project-evidence/actions/runs/38519333671), successful, 1,713 build jobs.  
**Independent pinned patch identity:** [#38519933956](https://github.com/fraware/lean-project-evidence/actions/runs/38519933956), successful.  
[Review-ready patch and reconstruction README](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-swar42-range-handoff-20261013/handoff_leanvm_533).

## Same-build mathematical claims established

`leanxmss.Proofs.Encoding.fold6` and `fold12` are complete and have
axiom reports without `sorryAx`.

`leanxmss.Proofs.Encoding.swar42_nat_spec` proves that the combined
two-half natural-number SWAR algorithm returns the sum of 42 three-bit
digest digits for padded 63-bit inputs.

`leanxmss.Proofs.Encoding.swar42_packed_first_fits_u64` proves
the packed first-stage base-64 accumulator is `<2^64` under its
digit field bounds.

`leanxmss.Proofs.Encoding.swar42_first_sum_fits_u64` applies
this property to the **actual mathematical expression** from two
padded digest halves, including the EVEN mask and 3-bit shifts.

`leanxmss.Proofs.Encoding.swar42_late_folds_fit_u64` establishes
the packed 12-bit accumulator and its 12/24/48-bit shift/add
intermediates are all `<2^64` for the required 42-digit bounds.

Exact same-build axiom lines:

```text
'leanxmss.Proofs.Encoding.swar42_packed_first_fits_u64' depends on axioms: [propext, Quot.sound]
'leanxmss.Proofs.Encoding.swar42_first_sum_fits_u64' depends on axioms: [propext, Classical.choice, Quot.sound]
'leanxmss.Proofs.Encoding.swar42_late_folds_fit_u64' depends on axioms: [propext, Classical.choice, Quot.sound]
'leanxmss.Proofs.Encoding.swar42_nat_spec' depends on axioms: [propext, Classical.choice, Quot.sound]
'leanxmss.Proofs.encode_spec' depends on axioms: [propext, sorryAx, Classical.choice, Quot.sound]
```

## What is still open

The actual Rust guest's `leanxmss.Digits.sum` is an Aeneas-translated
`Result Std.U64` computation, with each intermediate checked addition
and shift. The above mathematical invariants **do not alone prove**
that the guest returns these natural numbers.

The pinned Aeneas library exposes `UScalar.add_spec` (source requires
each `x.val+y.val ≤ U64.max`), shift postconditions and
`UScalar.val_and`. Those conditions must be discharged for
the intermediate guest values by a weakest-precondition proof of
`leanxmss.Digits.sum`.

Next, connect the digested words' bytes to the specification's
`Internal.digits`, prove the top spare-bit/target-sum equivalence,
and preserve `some`/`none` behavior in `encode_spec`.

The higher `verify_spec`, `verify_ok_iff`, and `main_spec` theorems
still depend on an admitted encoding obligation, and several
Aeneas/SDK/VM external model semantics remain trusted.

**Upstream status:** no review comment or PR was accepted/merged;
the connected GitHub installation lacks upstream writing permission.
