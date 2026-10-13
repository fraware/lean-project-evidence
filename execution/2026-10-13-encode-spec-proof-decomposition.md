# Source-grounded remaining `encode_spec` obligations in leanVM PR #533

**Baseline:** `leanEthereum/leanVM@4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.  
**Checked progress:** `fold12` now kernel-checked in an independent research
candidate (see [CI #38477725808](https://github.com/fraware/lean-project-evidence/actions/runs/38477725808));
the other admitted results in upstream `Encoding.lean` are **not** declared complete.

## Concrete statements

The pinned specification `Spec/EthCryptographySpecs/Xmss/Encoding.lean` defines:

- `Internal.digestWord`: little-endian decode of each eight-byte digest half.
- `Internal.digit`: an index's three bits, with digits in `Fin 8`.
- `Internal.digits`: 42 digits over two halves (21 per 64-bit word).
- `Internal.padded`: both halves have their unused bit 63 equal to zero.
- `Internal.onTarget`: the sum of 42 digits equals `TARGET_SUM=195`.
- `wotsEncode`: hashes the encoding payload and admits it exactly if both
  `padded` and `onTarget` hold.

The guest implementation `Leanxmss/Funs.lean` uses `Digits.get`,
`Digits.sum` with `EVEN=8198552921648689607` and
`LOW6=17311559823019733055`, and a guest-specific admissibility predicate.

## Proposed proof decomposition

1. **Little-endian representation:** relate `Statement.digest` of guest words
   to `Internal.digestWord` for each of the two halves; do not reuse an
   unproved hash-model equality in this step.
2. **Individual chain digits:** instantiate the already checked `get_ok`
   proof and show each value at index `0 ≤ i < 42` equals the specification's
   `Internal.digits` index.
3. **Half-word sum:** prove `fold6` without a monolithic bitvector solver,
   then combine the existing `land_even`/`land_odd` lemmas and the checked
   `fold12` result. Prove one equality per half before summing.
4. **Spare-bit admissibility:** show the guest's top-bit test is equivalent to
   `Internal.padded` for both digest words, under the actual operand widths.
5. **Target sum:** equate guest `Digits.sum` and the specification's
   `Internal.onTarget` 42-digit fold, preserving the exact value 195 and
   the error/rejection branch.
6. **Full `encode_spec`:** combine both admissibility equivalences with
   the digit equality, preserving the `none` branch and the universal digit
   correspondence for `some`. Check that neither panics under the claimed
   domain.
7. **End-to-end theorem audit:** re-run
   `lake env lean scripts/Axioms.lean` and verify that
   `verify_spec`, `verify_ok_iff`, `main_spec`, and
   `main_terminates` no longer report `sorryAx`. The Charon/Aeneas
   translation, closure patch, SDK models, and hand-transcribed `main`
   remain explicit trust assumptions until addressed separately.

## Proof quality criteria

- No `sorry` in the target theorem or hidden assumed helper.
- No artificial restatement of the desired conclusion as an axiom.
- No functional change to guest or specification during proof repair.
- Exact source identity checked before each overlay.
- `#print axioms` and the full Lean build from the same commit.
- Independent reconstruction for every result intended for upstream use.
- No complete implementation-equivalence claim until the actual theorem
  dependencies and external semantic models are justified.

The binding of the VM's actual cryptographic SDK/assembly/commit instructions
to Lean models is a **different** task from removing `sorryAx`.
