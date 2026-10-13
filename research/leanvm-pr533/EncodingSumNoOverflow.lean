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

set_option maxHeartbeats 2000000
/-- A digit-sum accumulator of ten complete six-bit fields and one
partial high field cannot wrap a 64-bit machine word, provided its lower
fields are sums of at most four three-bit digits (0..28 each). -/
theorem encoding_initial_sum_below_u64
    (c0 c1 c2 c3 c4 c5 c6 c7 c8 c9 c10 : Nat)
    (h0 : c0 ≤ 28) (h1 : c1 ≤ 28) (h2 : c2 ≤ 28)
    (h3 : c3 ≤ 28) (h4 : c4 ≤ 28) (h5 : c5 ≤ 28)
    (h6 : c6 ≤ 28) (h7 : c7 ≤ 28) (h8 : c8 ≤ 28)
    (h9 : c9 ≤ 28) (h10 : c10 < 16) :
    val 64 [c0, c1, c2, c3, c4, c5, c6, c7, c8, c9, c10] < 2 ^ 64 := by
  simp only [val_cons, val_nil]
  omega

set_option maxHeartbeats 200000

end leanxmss.Proofs.Encoding

#print axioms leanxmss.Proofs.Encoding.encoding_sum_stages_below_u64

#print axioms leanxmss.Proofs.Encoding.encoding_initial_sum_below_u64
