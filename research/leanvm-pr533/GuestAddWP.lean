import LeanxmssProofs.Encoding

/-!
The first actual Aeneas Std.U64 checked addition used by
leanxmss.Digits.sum, with a source-specific no-overflow proof.
This imports (and does not change) the checked SWAR42 arithmetic and
range lemmas. It is a building block, not the full Digits.sum proof.
-/

open Aeneas Aeneas.Std Result WP
namespace leanxmss.Proofs.Encoding

/-- The first checked add of the EVEN-masked low digest half succeeds
    without overflow. Its operands are exactly those of Digits.sum
    immediately following the low right shift. -/
theorem swar42_guest_first_add_spec
    (lo hi : Std.U64) (hlo : lo.val < 2 ^ 63) (hhi : hi.val < 2 ^ 63)
    (a b : Std.U64)
    (ha : a.val = lo.val &&& 8198552921648689607)
    (hb : b.val = (lo.val >>> 3) &&& 8198552921648689607) :
    (a + b) ⦃ z =>
      z.val = (lo.val &&& 8198552921648689607) +
        ((lo.val >>> 3) &&& 8198552921648689607) ⦄ := by
  have hfull := swar42_first_sum_fits_u64 lo.val hi.val hlo hhi
  have hprefix :
      (lo.val &&& 8198552921648689607) +
      ((lo.val >>> 3) &&& 8198552921648689607) < 2 ^ 64 := by
    omega
  have hmax : (a.val + b.val) ≤ UScalar.max .U64 := by
    simp only [ha, hb, UScalar.max_UScalarTy_U64_eq, U64.max_eq]
    omega
  simpa only [ha, hb] using (UScalar.add_spec hmax)

/-- Source-specific prefix bound for all three checked U64 additions in
    the EVEN-masked first stage of Digits.sum. -/
theorem swar42_guest_initial_prefixes (x y : Nat)
    (hx : x < 2 ^ 63) (hy : y < 2 ^ 63) :
    let a := x &&& 8198552921648689607
    let b := (x >>> 3) &&& 8198552921648689607
    let c := y &&& 8198552921648689607
    let d := (y >>> 3) &&& 8198552921648689607
    a + b < 2 ^ 64 ∧
    a + b + c < 2 ^ 64 ∧
    a + b + c + d < 2 ^ 64 := by
  dsimp
  have h := swar42_first_sum_fits_u64 x y hx hy
  omega

end leanxmss.Proofs.Encoding
