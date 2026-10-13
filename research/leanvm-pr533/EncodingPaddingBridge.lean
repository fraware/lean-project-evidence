import LeanxmssProofs.Encoding

/-!
This is the exact Boolean kernel underlying the Rust guest's condition
  (low | high) >> 63 == 0.
A full proof of encode_spec must ALSO connect both guest words with the
specification's digestWord and its two spare padding bits.
-/

namespace leanxmss.Proofs.Encoding

/-- No top bit is set in an OR iff no top bit is set in either 64-bit input. -/
theorem encoding_top_bit_or (low high : BitVec 64) :
    ((low ||| high) >>> 63 = 0#64) ↔
      ((low >>> 63 = 0#64) ∧ (high >>> 63 = 0#64)) := by
  rw [BitVec.ushiftRight_or_distrib]
  have eq_zero (v : BitVec 64) : (v = 0#64) ↔ v.toNat = 0 := by
    constructor
    · rintro rfl
      rfl
    · intro h
      apply BitVec.eq_of_toNat_eq
      simpa using h
  rw [eq_zero, eq_zero, eq_zero]
  rw [BitVec.toNat_or]
  have hor_small (a b : Nat) (ha : a < 2) (hb : b < 2) :
      (a ||| b = 0 ↔ a = 0 ∧ b = 0) := by
    rcases (show a = 0 ∨ a = 1 by omega) with h | h <;>
      rcases (show b = 0 ∨ b = 1 by omega) with h' | h' <;>
      simp [h, h']
  have hl : (low >>> 63).toNat < 2 := by
    have h := BitVec.toNat_ushiftRight_lt low 63 (by decide)
    norm_num at h
    exact h
  have hh : (high >>> 63).toNat < 2 := by
    have h := BitVec.toNat_ushiftRight_lt high 63 (by decide)
    norm_num at h
    exact h
  exact hor_small _ _ hl hh

/-- Equivalently, failure of the shared guard means a half has a high bit. -/
theorem encoding_top_bit_reject (low high : BitVec 64) :
    ((low ||| high) >>> 63 ≠ 0#64) ↔
      ((low >>> 63 ≠ 0#64) ∨ (high >>> 63 ≠ 0#64)) := by
  simpa only [not_and_or] using not_congr (encoding_top_bit_or low high)

end leanxmss.Proofs.Encoding

#print axioms leanxmss.Proofs.Encoding.encoding_top_bit_or
#print axioms leanxmss.Proofs.Encoding.encoding_top_bit_reject
