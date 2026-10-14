# XMSS guest SWAR fixed-width arithmetic obligations

**Research note:** October 13, 2026.  
**Source:** `leanEthereum/leanVM` PR #533 at `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.  
**Status:** Arithmetic envelope calculated directly from digit bounds. Independent **Lean theorem acceptance is pending** for fixed-width no-wrap statements. The separate `swar42_nat_spec` arithmetic theorem is already checked by [CI #38484404732](https://github.com/fraware/lean-project-evidence/actions/runs/38484404732).

## Mathematical maxima under padded-input hypotheses

Each digest word is less than `2^63`, so each word has exactly 21 relevant
base-eight digits, numbered 0–20, and no set high padding bit.
Each digit is in `[0,7]`.

Let `s` denote the sum of the four EVEN-masked terms, using `x,y`
for the digest words. The eleven 6-bit fields have upper bounds 28 for
fields 0–9 (four digits of at most 7 each) and 14 for the final field
(two digits of at most 7). Thus

```text
s ≤ 28·Σ(64^i, i=0..9) + 14·64^10
  = 16,653,310,622,098,900,764
  < 2^64 = 18,446,744,073,709,551,616.
```

The following LOW6 operation forms the packed 12-bit word `t` containing
six fields. The first five fields are at most 56; the final field is at
most 14. Hence

```text
t ≤ 56·Σ(4096^i, i=0..4) + 14·4096^5
  = 16,156,667,512,422,105,144
  < 15·2^60 < 2^64.
```

Since shifts are by fixed nonnegative amounts, the largest values for the
remaining cumulative reductions are attained at the largest `t`:

| Stage | Expression | Upper envelope |
|---|---|---:|
| Packed fields | `t` | 16,156,667,512,422,105,144 |
| First reduction | `u = t + (t >> 12)` | 16,160,612,011,326,505,072 |
| Second reduction | `v = u + (u >> 24)` | 16,160,612,974,574,043,360 |
| Final addition | `w = v + (v >> 48)` | 16,160,612,974,574,100,774 |

All four are strictly below `2^64`. Every prefix accumulation is no
larger than the corresponding complete nonnegative sum, so these bounds
also justify that earlier additions fit if the mathematical expression
matches the guest operand order.

## Distinct formal obligations

1. Show that the four masked terms in the actual bitwise computation equal
   the `val 64` field representation and that the initial sum fits `U64`.
2. Show that the LOW6 and shift-by-6 operations form the bounded six-field
   `val 4096` representation; this uses the checked `fold6` theorem.
3. Machine-check the stronger `t < 15·2^60` bound in Lean.
4. Machine-check the shift/add stage inequalities to prevent U64 wrapping.
5. **Separately** connect `Aeneas.Std.U64` computation semantics and result
   propagation to these natural-number equalities. A bound alone is not a
   proof that the guest operations implement the natural-number algorithm.
6. Connect the `UInt64` top-bit OR predicate to the specification's
   `Internal.padded` and the `Statement.digest` byte/word representation.

These tasks are source-pinned experiments. Their CI conclusions are
independent. The LeanVM `encode_spec` theorem still depends on `sorryAx`.

## Engineering scope and scientific honesty

The maxima above are direct arithmetic calculations from bounded digits,
not software crash, distributed-consensus, or external VM soundness results.
They exclude nonpadded inputs; the guest rejects such inputs in its
encoding branch. The provenance of that rejection still needs a separately
checked implementation correspondence proof.
