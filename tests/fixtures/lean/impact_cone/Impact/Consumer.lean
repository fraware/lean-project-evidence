import Impact.Core

def usesCore : Nat := coreVal + helper

theorem aboutCore : usesCore = coreVal + helper := by
  rfl
