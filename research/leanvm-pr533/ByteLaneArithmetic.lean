import BytePackBitVec

/-!
Bridge fixed-width bitvector lane extraction to the mathematical
little-endian quotient/remainder representation used by
`leanxmss.Bytes.le`.

Unlike the eight-lane reconstruction theorem, these statements involve
natural numbers. Their proofs must be checked independently before they
are used at the `Internal.digestWord` boundary.
-/

namespace leanxmss.Proofs

/-- Extracting lane `i` from a 64-bit bitvector is mathematically the
    `i`th base-256 digit of the original natural number. -/
theorem bitvec_lane_toNat (w : BitVec 64) (i : Nat) :
    ((w >>> (8 * i)) &&& 255#64).toNat =
      w.toNat / 256 ^ i % 256 := by
  simp only [BitVec.toNat_and, BitVec.toNat_ushiftRight,
    Nat.shiftRight_eq_div_pow]
  norm_num
  rw [show (2 : Nat) ^ (8 * i) = 256 ^ i by
    rw [pow_mul]
    norm_num]
  simpa only [show (2 : Nat) ^ 8 - 1 = 255 by decide] using
    (Nat.and_two_pow_sub_one_eq_mod (w.toNat / 256 ^ i) 8)

/-- The actual zero-extended 8-bit quotient remainder equals the
    corresponding masked lane in `BitVec 64`. -/
theorem bitvec_byte_ofNat (w : BitVec 64) (i : Nat) :
    BitVec.ofNat 64 (w.toNat / 256 ^ i % 256) =
      ((w >>> (8 * i)) &&& 255#64) := by
  apply BitVec.eq_of_toNat_eq
  rw [bitvec_lane_toNat]
  simp only [BitVec.toNat_ofNat]
  rw [Nat.mod_eq_of_lt]
  exact lt_trans (Nat.mod_lt _ (by decide : 0 < 256)) (by decide : 256 < 2 ^ 64)

end leanxmss.Proofs
