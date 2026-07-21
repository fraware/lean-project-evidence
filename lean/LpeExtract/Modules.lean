/-
  Module membership helpers for generic extraction.
-/
import Lean

open Lean

namespace LpeExtract.Modules

/-- True when ``name`` is rooted under one of the project module roots. -/
def isProjectName (roots : Array Name) (name : Name) : Bool :=
  roots.any fun root => name.getRoot == root.getRoot

/-- True when a module name belongs to the project roots. -/
def isProjectModule (roots : Array Name) (name : Name) : Bool :=
  isProjectName roots name

/-- Parse comma-separated Lean names from a CLI argument. -/
def parseNameList (s : String) : Array Name :=
  Id.run do
    let mut out : Array Name := #[]
    for part in s.splitOn "," do
      let trimmed := part.trim
      if !trimmed.isEmpty then
        out := out.push trimmed.toName
    return out

end LpeExtract.Modules
