import LeanxmssProofs.Encoding

/-! Source-specific Aeneas word semantics for Digits.sum's shift and
mask operations. This file preserves the upstream translated guest. -/

open Aeneas Aeneas.Std Result WP

namespace leanxmss.Proofs.Encoding

/-- The actual guest expression low >>> W is a checked three-bit
right shift, with no change to the 64-bit word interpretation. -/
theorem swar42_guest_W_shift_spec (lo : Std.U64) :
    (lo >>> leanxmss.W) ⦃ z =>
      z.val = lo.val >>> 3 ∧ z.bv = lo.bv >>> 3 ⦄ := by
  have hw : leanxmss.W.val < UScalarTy.U64.numBits := by
    simp [leanxmss.W, UScalarTy.U64_numBits_eq]
  have hs := UScalar.ShiftRight_spec lo leanxmss.W hw
  have hW : leanxmss.W.val = 3 := by simp [leanxmss.W]
  simpa only [hW] using hs

/-- The actual guest source's EVEN mask is interpreted as a bitwise
AND of natural-number word values. -/
theorem swar42_guest_even_mask_val (lo : Std.U64) :
    (lo &&& leanxmss.Digits.sum.EVEN).val =
      lo.val &&& 8198552921648689607 := by
  rw [UScalar.val_and]
  simp [leanxmss.Digits.sum.EVEN]

/-- The LOW6 mask operation in the guest has exact natural AND semantics. -/
theorem swar42_guest_low6_mask_val (lo : Std.U64) :
    (lo &&& leanxmss.Digits.sum.LOW6).val =
      lo.val &&& 17311559823019733055 := by
  rw [UScalar.val_and]
  simp [leanxmss.Digits.sum.LOW6]

end leanxmss.Proofs.Encoding
