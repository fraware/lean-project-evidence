import LpeFixture.LibA

namespace LpeFixture.LibB

def fromSeed : Nat := LpeFixture.LibA.seed

def fromSeedPlus : Nat := LpeFixture.LibA.seedPlus + fromSeed

end LpeFixture.LibB
