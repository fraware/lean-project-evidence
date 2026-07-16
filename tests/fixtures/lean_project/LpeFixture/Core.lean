namespace LpeFixture.Core

def coreVal : Nat := 1

def helper : Nat := coreVal + 1

theorem corePositive : 0 < coreVal := Nat.zero_lt_succ 0

end LpeFixture.Core
