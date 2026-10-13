# leanVM PR #533: independently reproduced proof boundary

**Date:** October 13, 2026  
**Upstream:** [leanEthereum/leanVM PR #533](https://github.com/leanEthereum/leanVM/pull/533), exact source `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.  
**Independent run:** [fraware/lean-project-evidence Actions #38471306908](https://github.com/fraware/lean-project-evidence/actions/runs/38471306908), job `leanvm-proof-baseline`, success.

## Reproduction

- Matched `verification/leanxmss/lean-toolchain`: `leanprover/lean4:v4.31.0`.
- Used the upstream repository's vendored Ethereum XMSS specification and pinned Aeneas translation/model files.
- Fetched Mathlib's pinned binary cache and successfully built the verification project (**1,713 build jobs**).
- Ran the actual `lake env lean scripts/Axioms.lean` to audit the complete reported axiom closure of the published main theorems.
- Examined all exact `sorry` lines in `LeanxmssProofs/Encoding.lean`: 136, 145, 179.

## Admitted statements and consequences

| Theorem | Declaration line | Proof line | Status |
|---|---:|---:|---|
| `leanxmss.Proofs.Encoding.fold6` | 130 | 136 | uses `sorry` |
| `leanxmss.Proofs.Encoding.fold12` | 139 | 145 | uses `sorry` |
| `leanxmss.Proofs.encode_spec` | 173 | 179 | uses `sorry` |

Actual `#print axioms` output:
- `leanxmss.Proofs.verify_spec`: `[propext, sorryAx, Classical.choice, Quot.sound]`.
- `leanxmss.Proofs.verify_ok_iff`: same.
- `leanxmss.Main.main_spec`: same.
- `leanxmss.Main.main_terminates`: same.
- `leanxmss.Proofs.encode_spec`: same.
- `leanxmss.Proofs.Words.publicKey_onto`, `signature_onto`, `message_onto`: `[propext, Classical.choice, Quot.sound]`.
- `leanxmss.Proofs.wots_leaf_spec`, `merkle_root_spec`, `tweak_hash_spec`: `[propext, Classical.choice, Quot.sound]`.

The compiler emitted source warnings for all three admitted declarations. The successful build is **not proof** of the guest's complete equivalence or `main`'s specification correspondence. Its proof dependency graph currently contains `sorryAx`.

## Arithmetic feasibility check (not proof)

Using the **exact mathematical expressions and bounds** of `fold6` and `fold12`, a seeded Python reference (seed `20261013`) checked four boundary configurations and 200,000 random valid input configurations per lemma without a mismatch. This checks statement consistency on a limited set only; neither universal theorem has been established by that experiment.

## Proof implementation strategy

- `fold6`: use the existing Lean lemmas `low6_val`, `val_land`, `val_cons_div`, `land_63`, and `land_15` to split alternating 6-bit fields and the shifted sum. Reassemble into 12-bit chunks with exact bit-width bounds. Do not invoke a monolithic 10-minute bitvector decision procedure.
- `fold12`: reduce shifts to quotient by powers of `4096`, expand the six-field polynomial `val 4096`, establish no carry reaches the low 12 bits because the digit sum is at most `6*56=336<4096`, and use bounded integer arithmetic to conclude the mask equals the sum.
- `encode_spec`: only after both folds have kernel-checked, connect guest digit extraction, digest word serialization, top-bit tests, and the 42-term target-sum predicate to the specification's `wotsEncode`.
- Re-run `scripts/Axioms.lean` after each proof. Remove `sorryAx` from the claimed theorem's dependency closure; independently audit Aeneas/Charon/SDK shim and hand-transcribed `main` assumptions.

**Next:** Attempt the smallest self-contained arithmetic lemma in a source-pinned test overlay. The outcome must be labeled successful only if Lean compiles the replacement and reports no `sorryAx` for that lemma. No upstream PR publication is implied.
