import DigitsSumWPSimpall
import PaddingBitVec

/-!
Source-pinned link between the leanXMSS guest's high-bit admission guard and
its Aeneas-translated `Digits.sum` preconditions. This is a proof about the
guest's actual guard over its two 64-bit words, not about arbitrary "safe"
inputs postulated independently of the execution path.

The source-to-model translation and the hash digest/byte mapping are separate
trusted boundaries; this file does not discharge `encode_spec`.
-/

namespace leanxmss.Proofs.Encoding

/-- A word has its spare top bit clear iff it is smaller than `2^63`.
    The equivalence uses the exact unsigned shift semantics. -/
theorem top_bit_zero_iff_lt (w : BitVec 64) :
    (w >>> 63 = (0 : BitVec 64)) ↔ w.toNat < 2 ^ 63 := by
  have hshift : (w >>> 63).toNat = w.toNat / 2 ^ 63 := by
    simp only [BitVec.toNat_ushiftRight, Nat.shiftRight_eq_div_pow]
  constructor
  · intro h
    have hzero : w.toNat / 2 ^ 63 = 0 := by
      rw [← hshift, h]
      rfl
    have hp : (2 : Nat) ^ 63 = 9223372036854775808 := by decide
    rw [hp] at hzero ⊢
    omega
  · intro h
    apply BitVec.eq_of_toNat_eq
    rw [hshift]
    simpa using (Nat.div_eq_of_lt h)

/-- The exact bitvector guard in the Rust guest's `encode` function implies
    exactly the two numerical range premises of `digits_sum_impl_spec`. -/
theorem guest_guard_iff_digit_sum_bounds (lo hi : Std.U64) :
    ((lo.bv ||| hi.bv) >>> 63 = (0 : BitVec 64)) ↔
      lo.val < 2 ^ 63 ∧ hi.val < 2 ^ 63 := by
  change ((lo.bv ||| hi.bv) >>> 63 = (0 : BitVec 64)) ↔
    lo.bv.toNat < 2 ^ 63 ∧ hi.bv.toNat < 2 ^ 63
  rw [guest_padded_or_iff]
  exact and_congr (top_bit_zero_iff_lt lo.bv) (top_bit_zero_iff_lt hi.bv)

/-- Once the guest has passed its high-bit guard, the modeled digit-sum
    operation returns successfully. Its exact returned numeric value is
    already established by `digits_sum_impl_spec`, which this theorem uses. -/
theorem digits_sum_succeeds_under_guest_guard (lo hi : Std.U64)
    (hguard : ((lo.bv ||| hi.bv) >>> 63 = (0 : BitVec 64))) :
    ∃ v, leanxmss.Digits.sum (Std.Array.make 2#usize [lo, hi]) = .ok v := by
  obtain ⟨hlo, hhi⟩ :=
    (guest_guard_iff_digit_sum_bounds lo hi).mp hguard
  obtain ⟨v, hv, _⟩ := digits_sum_impl_spec lo hi hlo hhi
  exact ⟨v, hv⟩

end leanxmss.Proofs.Encoding
