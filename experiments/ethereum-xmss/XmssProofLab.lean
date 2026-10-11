import Lean

/-!
# Ethereum XMSS proof lab — bounded radix arithmetic

Lean 4.31.0, pinned to the leanVM #533 development. These are small
machine-checkable building blocks for the six- and twelve-bit field
identities in `LeanxmssProofs/Encoding.lean`. They do not yet prove
the upstream `fold6`, `fold12` or `encode_spec` theorem.
-/

namespace XmssProofLab

theorem sanity_arithmetic (n : Nat) : n + 0 = n := by simp

/-- Dropping a bounded low-order radix-4096 lane preserves the higher lanes. -/
theorem div_radix_4096 (low high : Nat) (hlow : low < 4096) :
    (low + 4096 * high) / 4096 = high := by
  omega

/-- A bounded low-order radix-4096 lane is the exact modulo residue. -/
theorem mod_radix_4096 (low high : Nat) (hlow : low < 4096) :
    (low + 4096 * high) % 4096 = low := by
  omega

/-- The exact finite-lane `fold12` statement from leanVM PR #533. -/
def val (B : Nat) : List Nat → Nat
  | [] => 0
  | c :: cs => c + B * val B cs

set_option maxHeartbeats 5000000 in
theorem fold12 (e0 e1 e2 e3 e4 e5 : Nat) (h0 : e0 ≤ 56) (h1 : e1 ≤ 56)
    (h2 : e2 ≤ 56) (h3 : e3 ≤ 56) (h4 : e4 ≤ 56) (h5 : e5 ≤ 56) :
    let s1 := val 4096 [e0, e1, e2, e3, e4, e5]
    let s2 := s1 + s1 >>> 12
    let s3 := s2 + s2 >>> 24
    (s3 + s3 >>> 48) &&& 4095 = e0 + e1 + e2 + e3 + e4 + e5 := by
  dsimp [val]
  simp only [Nat.shiftRight_eq_div_pow]
  rw [show (4095 : Nat) = 2 ^ 12 - 1 by decide, Nat.and_two_pow_sub_one_eq_mod]
  omega

end XmssProofLab
