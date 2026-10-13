import LeanxmssProofs.Encoding

/-!
The existing fold12 theorem is about Nat operations, whereas the guest uses
U64 words. We need a bound showing the stated 12-bit folding stages fit a
64-bit word under the actual ten full fields + one partial-field regime.

This theorem does not prove the entire guest implementation correspondence.
-/

open Aeneas Aeneas.Std
namespace leanxmss.Proofs.Encoding

theorem encoding_sum_stages_below_u64 (e0 e1 e2 e3 e4 e5 : Nat)
    (h0 : e0 ≤ 56) (h1 : e1 ≤ 56) (h2 : e2 ≤ 56)
    (h3 : e3 ≤ 56) (h4 : e4 ≤ 56) (h5 : e5 < 16) :
    let s1 := val 4096 [e0, e1, e2, e3, e4, e5]
    let s2 := s1 + (s1 >>> 12)
    let s3 := s2 + (s2 >>> 24)
    s1 < 2 ^ 64 ∧ s2 < 2 ^ 64 ∧ s3 < 2 ^ 64 ∧
      s3 + (s3 >>> 48) < 2 ^ 64 := by
  dsimp
  simp only [Nat.shiftRight_eq_div_pow]
  norm_num [val]
  omega

end leanxmss.Proofs.Encoding

#print axioms leanxmss.Proofs.Encoding.encoding_sum_stages_below_u64
