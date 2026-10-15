import LeanxmssProofs.Bytes
import Mathlib.Tactic

/-!
The Boolean/algebraic core of the specification's 8-byte little-endian
digest decoder. The original direct attempt in
`DigestWordAssemblyDiagnostic.lean` mixed List/Vector/Nat operations with
BitVec SAT preprocessing. This theorem isolates the fixed-width proposition
so that its proof can be independently kernel-checked.

This file proves neither the byte extraction from `Bytes.le` nor the
`Internal.digestWord` representation bridge. Those remain separate.
-/

namespace leanxmss.Proofs

/-- A 64-bit word equals the bitwise OR of its eight masked 8-bit lanes
    shifted back to their original positions. No assumptions on the word. -/
theorem bitvec_eight_lane_reconstruct (w : BitVec 64) :
    (w &&& 255#64) |||
    (((w >>> 8) &&& 255#64) <<< 8) |||
    (((w >>> 16) &&& 255#64) <<< 16) |||
    (((w >>> 24) &&& 255#64) <<< 24) |||
    (((w >>> 32) &&& 255#64) <<< 32) |||
    (((w >>> 40) &&& 255#64) <<< 40) |||
    (((w >>> 48) &&& 255#64) <<< 48) |||
    (((w >>> 56) &&& 255#64) <<< 56) = w := by
  ext i hi
  interval_cases i <;> simp

end leanxmss.Proofs
