/-!
Transitive downstream of Impact.Core.coreVal via usesCore.
Hand-audited: MUST appear in cone when coreVal changes.
-/

import Impact.Consumer

def usesUsesCore : Nat := usesCore + 1
