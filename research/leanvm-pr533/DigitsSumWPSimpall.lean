import LeanxmssProofs.Encoding

/-!
Diagnostic attempt to execute the original translated Digits.sum body
through Aeneas's weakest-precondition prover, using the already checked
padded two-word SWAR arithmetic and range facts. No sorry or axiom added.
The CI verdict determines whether this source proof is established.
-/

open Aeneas Aeneas.Std Result WP
namespace leanxmss.Proofs.Encoding

theorem digits_sum_impl_spec
    (lo hi : Std.U64) (hlo : lo.val < 2 ^ 63) (hhi : hi.val < 2 ^ 63) :
    ∃ v, leanxmss.Digits.sum (Std.Array.make 2#usize [lo, hi]) = ok v ∧
      v.val =
        (d lo.val 0 + d lo.val 1 + d lo.val 2 + d lo.val 3 +
         d lo.val 4 + d lo.val 5 + d lo.val 6 + d lo.val 7 +
         d lo.val 8 + d lo.val 9 + d lo.val 10 + d lo.val 11 +
         d lo.val 12 + d lo.val 13 + d lo.val 14 + d lo.val 15 +
         d lo.val 16 + d lo.val 17 + d lo.val 18 + d lo.val 19 +
         d lo.val 20) +
        (d hi.val 0 + d hi.val 1 + d hi.val 2 + d hi.val 3 +
         d hi.val 4 + d hi.val 5 + d hi.val 6 + d hi.val 7 +
         d hi.val 8 + d hi.val 9 + d hi.val 10 + d hi.val 11 +
         d hi.val 12 + d hi.val 13 + d hi.val 14 + d hi.val 15 +
         d hi.val 16 + d hi.val 17 + d hi.val 18 + d hi.val 19 +
         d hi.val 20) := by
  apply exists_ok_of_spec
  unfold leanxmss.Digits.sum
  simp only [leanxmss.Digits.sum.EVEN, leanxmss.Digits.sum.LOW6, leanxmss.W, lift]
  step*
  all_goals
    have hfirst := swar42_first_sum_fits_u64 lo.val hi.val hlo hhi
    have hlate := swar42_all_late_sums_fit_u64 lo.val hi.val hlo hhi
    have hsum := swar42_nat_spec lo.val hi.val hlo hhi
    dsimp at hlate hsum
    simp_all only [Std.Array.make_val, UScalar.val_and,
      UScalar.max_UScalarTy_U64_eq, U64.max_eq]
    omega

end leanxmss.Proofs.Encoding
