import LpeFixture.Core

namespace LpeFixture.Diamond

/-- Diamond apex: depends on Core.coreVal. -/
def apex : Nat := LpeFixture.Core.coreVal

def leftBranch : Nat := apex + 1

def rightBranch : Nat := apex + 2

/-- Merges both branches (diamond bottom). -/
def bottom : Nat := leftBranch + rightBranch

end LpeFixture.Diamond
