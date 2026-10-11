import Lean

/-!
# Ethereum XMSS proof lab — toolchain bootstrap

A small unconditional theorem first demonstrates that GitHub Actions is
actually invoking the pinned Lean kernel. The separate XMSS obligations are
not yet discharged. This experiment is not a production artifact.
-/

namespace XmssProofLab

theorem sanity_arithmetic (n : Nat) : n + 0 = n := by simp

end XmssProofLab
