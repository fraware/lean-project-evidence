import LpeFixture.LibC
import LpeFixture.Consumer

namespace LpeFixture.Cross

/-- Fan-in across Lib* and Consumer branches (hand-audited multi-module cone). -/
def bridge : Nat := LpeFixture.LibC.deep + LpeFixture.Consumer.usesCore

def bridgeTwice : Nat := bridge + bridge

end LpeFixture.Cross
