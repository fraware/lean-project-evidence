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

end XmssProofLab
