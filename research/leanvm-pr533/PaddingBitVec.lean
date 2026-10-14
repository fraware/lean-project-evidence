import LeanxmssProofs.Encoding

/-!
The spare top bit is a shared condition for both 64-bit XMSS digest halves.
This theorem relates the exact OR-and-shift test used by the guest's encode
function to the conjunction of individual unused-bit tests.
It does not itself prove the guest's Option/Result control flow.
-/

namespace leanxmss.Proofs.Encoding

/-- The high bit of the bitwise OR is zero exactly when the high bit of
    both 64-bit digest halves is zero. -/
theorem guest_padded_or_iff (lo hi : BitVec 64) :
    ((lo ||| hi) >>> 63 = 0) ↔
      (lo >>> 63 = 0 ∧ hi >>> 63 = 0) := by
  bv_decide

end leanxmss.Proofs.Encoding
