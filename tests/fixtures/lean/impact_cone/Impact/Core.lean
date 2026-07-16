/-!
Hand-audited impact-cone fixture (AUDIT-012 / ISSUE-026).

Expected downstream cone when `Impact.Core.coreVal` changes:
  - Impact.Consumer.usesCore
  - Impact.Consumer.aboutCore
Must NOT include:
  - Impact.Unrelated.other
-/

def coreVal : Nat := 1

def helper : Nat := coreVal
