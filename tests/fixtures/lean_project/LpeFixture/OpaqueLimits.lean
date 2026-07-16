/-!
  Opaque visibility bounds for elaborator IR honesty tests.

  `secretOpaque` is defined in terms of `hiddenHelper`, but consumers of the
  opaque should not invent edges to `hiddenHelper` beyond what
  `ConstantInfo.getUsedConstantsAsSet` stores for the opaque constant.

  No `axiom` declarations here: fixture axioms would appear in `axioms_used`
  and fail `lean.prohibited_axioms` for E2E ACCEPT paths. Axiom kind coverage
  lives in unit tests with synthetic IR (`test_elaborator_opaque_axiom_limits`).
-/
namespace LpeFixture.OpaqueLimits

def hiddenHelper : Nat := 42

opaque secretOpaque : Nat := hiddenHelper

def usesOpaque : Nat := secretOpaque

end LpeFixture.OpaqueLimits
