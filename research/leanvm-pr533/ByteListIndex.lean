import LeanxmssProofs.Bytes

/-!
The guest encodes each 64-bit word using the recursive `Bytes.le` function.
This lemma proves the exact byte at every valid list index. It is the
missing list/Nat normalization needed to expose pure bitvector expressions
in the specification's `Internal.digestWord` decoder.
-/

namespace leanxmss.Proofs

/-- Byte `i` of the guest's `n`-byte little-endian serialization is
    the quotient of the word's natural value by `256^i`, truncated to a byte.
    No restriction on `x` beyond the list-index validity is necessary. -/
theorem le_getD_exact (n x i : Nat) (hi : i < n) :
    (Bytes.le n x).getD i 0 = UInt8.ofNat (x / 256 ^ i) := by
  induction i generalizing n x with
  | zero =>
    cases n with
    | zero => omega
    | succ n =>
      simp [Bytes.le]
  | succ i ih =>
    cases n with
    | zero => omega
    | succ n =>
      change (Bytes.le n (x / 256)).getD i 0 =
        UInt8.ofNat (x / 256 ^ (i + 1))
      rw [ih n (x / 256) (by omega)]
      congr 1
      rw [Nat.div_div_eq_div_mul, pow_succ]
      simp [Nat.mul_comm]

end leanxmss.Proofs
