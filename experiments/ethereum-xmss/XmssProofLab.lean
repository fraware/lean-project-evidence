import Mathlib

/-!
# Isolated Ethereum XMSS proof lab

This lab pins the exact Lean 4.31.0 version of the in-flight leanVM #533
verification project. It is not an upstream proof or a production artifact.
No sorry, admitted axioms, or synthetic theorem shortcuts are permitted.
-/

namespace XmssProofLab

theorem sanity_arithmetic (n : Nat) : n / 1 = n := by omega

end XmssProofLab
