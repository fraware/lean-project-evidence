import LpeFixture.Diamond

namespace LpeFixture.Chain

/-- Linear chain for transitive impact-cone checks. -/
def step1 : Nat := LpeFixture.Diamond.bottom

def step2 : Nat := step1 + 1

def step3 : Nat := step2 + 1

end LpeFixture.Chain
