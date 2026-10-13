# leanVM PR #533 — two admitted arithmetic lemmas closed

Date: 2026-10-13  
Upstream pinned head: `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`  
Checked candidate: `fraware/lean-project-evidence@7b0b84eb96fd2c834c15ccfad49f36b4cd16e3a0`  
Original `Encoding.lean` Git blob: `4853d8a398a1ff2762a71473c17c17e175f80b73`  
Combined `Encoding.lean` Git blob: `41b62c33554ff74b96c129e21cc7fd11d225179c`

## Kernel-checked results

In the exact upstream PR #533 verification project, both admitted
arithmetic statements now have complete Lean proof bodies:

1. `leanxmss.Proofs.Encoding.fold6`, grouping paired 6-bit
   fields into 12-bit fields using the declared low-six-bit mask.
2. `leanxmss.Proofs.Encoding.fold12`, folding six bounded 12-bit
   fields by shift/add operations into the low 12-bit digit sum.

The [composed CI #38479742934](https://github.com/fraware/lean-project-evidence/actions/runs/38479742934)
successfully compiled all 1,713 Lean build jobs and printed:

```text
'leanxmss.Proofs.Encoding.fold6' depends on axioms: [propext, Classical.choice, Quot.sound]
'leanxmss.Proofs.Encoding.fold12' depends on axioms: [propext, Classical.choice, Quot.sound]
'leanxmss.Proofs.encode_spec' depends on axioms: [propext, sorryAx, Classical.choice, Quot.sound]
'leanxmss.Proofs.verify_spec' depends on axioms: [propext, sorryAx, Classical.choice, Quot.sound]
```

These results were also validated independently before composition:
[`fold6` run](https://github.com/fraware/lean-project-evidence/actions/runs/38479334042),
[`fold12` run](https://github.com/fraware/lean-project-evidence/actions/runs/38477725808).

The [source-pinned patch reapplication run #38480309105](https://github.com/fraware/lean-project-evidence/actions/runs/38480309105)
independently validated the original Git blob, applied the two-fold patch,
and checked that the result exactly matched the kernel-checked Git blob.

[Combined patch and human review handoff](https://github.com/fraware/lean-project-evidence/tree/research/leanvm-pr533-both-folds-handoff-20261013/handoff_leanvm_533)

## Claims that are **not** established

- The upstream `encode_spec` theorem remains admitted and the higher
  `verify_spec` and `main_spec` theorem closures still include `sorryAx`.
- The Charon/Aeneas extraction, closure transformation, opaque SDK model,
  handwritten main transcription, and actual VM execution semantics remain
  external premises. Eliminating encoding admissions will not silently close
  those assumptions.
- This change is **not** accepted or merged upstream. Posting to PR #533 from
  the connected GitHub integration returned HTTP 403. A checked publication
  helper requiring an intentionally authenticated CLI is available in the
  combined handoff package.

## Next verified work gate

Complete the remaining `encode_spec` implementation correspondence:
digest-word / little-endian representation, 42-digit indexing, spare-bit
padding, 195-target-sum equivalence, and success/rejection branch semantics.
Then rebuild and inspect `#print axioms` for the entire verifier/main proof
chain. Keep source correspondence and SDK/VM modeling as independent gates.

This is substantive progress on the Ethereum implementation-verification
critical path, not yet complete implementation verification or external adoption.
