-- Ambiguous short-name fixture: two modules define ``twin``.
-- FQN resolution must surface ambiguity warnings rather than invent uniqueness.
namespace LpeFixture.AmbiguousA

def twin : Nat := 1

end LpeFixture.AmbiguousA
