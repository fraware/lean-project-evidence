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


/-- The second checked addition combines the first low-word partial sum with
    the high-word EVEN mask, and cannot overflow for two padded words. -/
theorem swar42_guest_second_add_spec
    (lo hi : Std.U64) (hlo : lo.val < 2 ^ 63) (hhi : hi.val < 2 ^ 63)
    (ab c : Std.U64)
    (hab : ab.val = (lo.val &&& 8198552921648689607) +
      ((lo.val >>> 3) &&& 8198552921648689607))
    (hc : c.val = hi.val &&& 8198552921648689607) :
    (ab + c) ⦃ z =>
      z.val = (lo.val &&& 8198552921648689607) +
        ((lo.val >>> 3) &&& 8198552921648689607) +
        (hi.val &&& 8198552921648689607) ⦄ := by
  have hprefix := swar42_guest_initial_prefixes lo.val hi.val hlo hhi
  dsimp at hprefix
  rcases hprefix with ⟨_, hsecond, _⟩
  have hmax : (ab.val + c.val) ≤ UScalar.max .U64 := by
    simp only [hab, hc, UScalar.max_UScalarTy_U64_eq, U64.max_eq]
    omega
  simpa only [hab, hc] using (UScalar.add_spec hmax)

/-- The third checked addition combines both digest halves' masked
    portions. The return value equals the full first-stage SWAR value. -/
theorem swar42_guest_third_add_spec
    (lo hi : Std.U64) (hlo : lo.val < 2 ^ 63) (hhi : hi.val < 2 ^ 63)
    (abc dword : Std.U64)
    (habc : abc.val = (lo.val &&& 8198552921648689607) +
      ((lo.val >>> 3) &&& 8198552921648689607) +
      (hi.val &&& 8198552921648689607))
    (hd : dword.val = (hi.val >>> 3) &&& 8198552921648689607) :
    (abc + dword) ⦃ z =>
      z.val = (lo.val &&& 8198552921648689607) +
        ((lo.val >>> 3) &&& 8198552921648689607) +
        (hi.val &&& 8198552921648689607) +
        ((hi.val >>> 3) &&& 8198552921648689607) ⦄ := by
  have hprefix := swar42_guest_initial_prefixes lo.val hi.val hlo hhi
  dsimp at hprefix
  rcases hprefix with ⟨_, _, hthird⟩
  have hmax : (abc.val + dword.val) ≤ UScalar.max .U64 := by
    simp only [habc, hd, UScalar.max_UScalarTy_U64_eq, U64.max_eq]
    omega
  simpa only [habc, hd] using (UScalar.add_spec hmax)

end leanxmss.Proofs.Encoding
