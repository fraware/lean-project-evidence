-- Fixture counterexample harness: intentional type error (FAIL path for ISSUE-031).
-- Lake env lean must fail closed — never silent PASS.
import LpeFixture.Core

def cexBadType : String := LpeFixture.Core.helper
