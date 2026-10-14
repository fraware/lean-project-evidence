import LeanxmssProofs.Encoding

/-! Conditional source-specific Aeneas U64 checked additions for the
last three SWAR shift/add stages, using saturating packed-field bounds.
No guest or verified arithmetic source is changed. -/

open Aeneas Aeneas.Std Result WP

namespace leanxmss.Proofs.Encoding

/-- Checked shift/add at 12 bits in the actual Aeneas guest,
    under the saturated upstream accumulator bound. -/
theorem swar42_guest_fold12_add_spec
    (acc shifted : Std.U64)
    (hacc : acc.val ≤ 17599790199171444798)
    (hshift : shifted.val = acc.val >>> 12) :
    (acc + shifted) ⦃ z =>
      z.val = acc.val + (acc.val >>> 12) ⦄ := by
  have hmax : acc.val + shifted.val ≤ UScalar.max .U64 := by
    simp only [hshift, UScalar.max_UScalarTy_U64_eq, U64.max_eq]
    rw [Nat.shiftRight_eq_div_pow]
    norm_num at *
    omega
  simpa only [hshift] using (UScalar.add_spec hmax)


/-- Checked shift/add at 24 bits in the actual Aeneas guest,
    under the saturated upstream accumulator bound. -/
theorem swar42_guest_fold24_add_spec
    (acc shifted : Std.U64)
    (hacc : acc.val ≤ 17604087022950539389)
    (hshift : shifted.val = acc.val >>> 24) :
    (acc + shifted) ⦃ z =>
      z.val = acc.val + (acc.val >>> 24) ⦄ := by
  have hmax : acc.val + shifted.val ≤ UScalar.max .U64 := by
    simp only [hshift, UScalar.max_UScalarTy_U64_eq, U64.max_eq]
    rw [Nat.shiftRight_eq_div_pow]
    norm_num at *
    omega
  simpa only [hshift] using (UScalar.add_spec hmax)


/-- Checked shift/add at 48 bits in the actual Aeneas guest,
    under the saturated upstream accumulator bound. -/
theorem swar42_guest_fold48_add_spec
    (acc shifted : Std.U64)
    (hacc : acc.val ≤ 17604088072235892987)
    (hshift : shifted.val = acc.val >>> 48) :
    (acc + shifted) ⦃ z =>
      z.val = acc.val + (acc.val >>> 48) ⦄ := by
  have hmax : acc.val + shifted.val ≤ UScalar.max .U64 := by
    simp only [hshift, UScalar.max_UScalarTy_U64_eq, U64.max_eq]
    rw [Nat.shiftRight_eq_div_pow]
    norm_num at *
    omega
  simpa only [hshift] using (UScalar.add_spec hmax)

end leanxmss.Proofs.Encoding
