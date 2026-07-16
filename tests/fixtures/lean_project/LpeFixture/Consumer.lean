import LpeFixture.Core

namespace LpeFixture.Consumer

def usesCore : Nat := LpeFixture.Core.helper

def usesUsesCore : Nat := usesCore + LpeFixture.Core.coreVal

end LpeFixture.Consumer
