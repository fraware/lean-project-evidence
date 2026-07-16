import LpeFixture.LibB

namespace LpeFixture.LibC

/-- Deep transitive depender of LibA.seed. -/
def deep : Nat := LpeFixture.LibB.fromSeedPlus

end LpeFixture.LibC
