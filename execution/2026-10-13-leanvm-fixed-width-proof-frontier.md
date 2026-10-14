# Fixed-width refinement frontier for leanVM PR #533

**Current source pin:** `leanEthereum/leanVM@4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.  
**Proved baseline:** [full two-half arithmetic theorem](https://github.com/fraware/lean-project-evidence/actions/runs/38484404732), including axiom-clean `fold6`, `fold12`, and `swar42_nat_spec`.  
**Integration and trust status:** The real guest uses finite-width `Std.U64`; `encode_spec` is still admitted. These bounds alone do not establish guest correspondence.

## Exact bounds derived from the field specification

For padded `x,y < 2^63`, the guest's first EVEN-mask aggregation sums at most four base-eight digits per 6-bit field. The ten low fields are each `≤28`; the top field consists of two remaining digits and is `≤14`.

The most extreme base-64 packed field number is

```text
val 64 ([28] * 10 ++ [14])
= 16653310622098900764
= 0xe71c71c71c71c71c
< 2^64.
```

The next LOW6 pair fold groups eight base-eight digits per 12-bit field, so the five low fields are each `≤56`, and the final field is `≤14`. Saturating every field at these bounds gives the exact sequence of maximum unsigned natural-number accumulators:

| Step | Maximum hex value | Mathematical operation |
|---|---|---|
| Packed LOW6 output `s1` | `0xe038038038038038` | `val 4096 [56,56,56,56,56,14]` |
| `s2` | `0xe046070070070070` | `s1 + (s1 >>> 12)` |
| `s3` | `0xe04607e0b60e00e0` | `s2 + (s2 >>> 24)` |
| `s4` | `0xe04607e0b60ee126` | `s3 + (s3 >>> 48)` |

All numbers are strictly below `2^64`. This is an exact arithmetic calculation on the field bounds; it is **not yet a kernel-checked refinement theorem**. In particular, a proof must connect the guest's successive `U64` operations to these natural-number values.

## Current standalone proof attempts

- `research/leanvm-pr533-swar42-no-wrap-20261013`, [CI #38518388192](https://github.com/fraware/lean-project-evidence/actions/runs/38518388192), proves a generic first-stage base-64 field bound.
- `research/leanvm-pr533-swar42-fold-overflow-20261013`, [CI #38518487036](https://github.com/fraware/lean-project-evidence/actions/runs/38518487036), attempts machine-checked bounds for the later 12/24/48-bit shift/add stages.

**Do not label either lemma completed until its exact CI succeeds and `#print axioms` excludes `sorryAx`.** A later patch must also show the guest's `U64` result values equal the bounded natural-number results at every step.

## Substantive remaining obligations

1. Build `Std.U64` addition/shift/AND refinement lemmas and instantiate the proven bounds at each intermediate operation, including evaluation order and wrapping semantics.
2. Translate the guest's two digest `U64` words into the specification's little-endian bytes and the same 42 base-eight digits.
3. Prove the high-bit padding predicate and target-sum Bool test agree with their specification equivalents.
4. Preserve success, rejection, and no-panic behavior in `encode_spec`, then audit all higher-level axiom dependencies and remaining external models.

The user-visible achievement at this point is **exactly bounded mathematical arithmetic**. A verified end-to-end implementation theorem depends on the distinct refinement and model obligations.
