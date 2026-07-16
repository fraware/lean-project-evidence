/-
  LPE elaborator extraction helper.

  Emits `.lpe/lean-extraction.json` with Environment-based declaration
  dependency edges (`ConstantInfo.getUsedConstantsAsSet`) and separate
  module import edges. Schema version 1.1.

  Residual limitations (honest):
  - Tactic proofs may erase intermediate constants; only constants remaining
    in the elaborated type/value are observed.
  - Opaque / axiom / quotient constants expose type (and opaque value) deps
    only as Lean stores them — no body unfold beyond that.
  - Import edges are module→module from `.olean` ModuleData, not per-decl
    import provenance.
-/
import Lean
import LpeFixture

open Lean

/-- Extraction JSON schema version emitted by this helper. -/
def extractionSchemaVersion : String := "1.1"

def isFixtureName (name : Name) : Bool :=
  name.getRoot == `LpeFixture

def isFixtureModule (name : Name) : Bool :=
  name == `LpeFixture || name.getRoot == `LpeFixture

def kindOf : ConstantInfo → String
  | .axiomInfo _ => "axiom"
  | .defnInfo _ => "def"
  | .thmInfo _ => "theorem"
  | .opaqueInfo _ => "opaque"
  | .quotInfo _ => "quot"
  | .inductInfo _ => "inductive"
  | .ctorInfo _ => "constructor"
  | .recInfo _ => "recursor"

def escapeJsonString (s : String) : String :=
  (((s.replace "\\" "\\\\").replace "\"" "\\\"").replace "\n" "\\n").replace "\r" "\\r"
    |>.replace "\t" "\\t"

def jsonString (s : String) : String :=
  "\"" ++ escapeJsonString s ++ "\""

def jsonStringArray (xs : List String) : String :=
  "[" ++ ", ".intercalate (xs.map jsonString) ++ "]"

def jsonEdge (a b : String) : String :=
  "[" ++ jsonString a ++ ", " ++ jsonString b ++ "]"

def shortName (name : Name) : String :=
  match name with
  | .str _ s => s
  | _ => name.toString

def modulePath (name : Name) : String :=
  match name with
  | .str p _ => (p.toString.replace "." "/") ++ ".lean"
  | _ => name.toString.replace "." "/" ++ ".lean"

def collectDeclarations (env : Environment) : List (Name × ConstantInfo) :=
  env.constants.fold (init := []) fun acc name info =>
    if name.isInternal || !isFixtureName name then acc
    else (name, info) :: acc

def axiomsOf (env : Environment) (n : Name) : Array Name :=
  (((CollectAxioms.collect n).run env).run {}).2.axioms

def collectAxioms (env : Environment) (decls : List (Name × ConstantInfo)) : List String :=
  Id.run do
    let mut seen : NameSet := {}
    let mut out : List String := []
    for (name, _) in decls do
      for ax in axiomsOf env name do
        if !seen.contains ax then
          seen := seen.insert ax
          out := ax.toString :: out
    return out.reverse

/--
  Environment-based declaration edges: dependee → depender among fixture decls.
  Uses `ConstantInfo.getUsedConstantsAsSet` (type + value constants).
-/
def collectDeclEdges (decls : List (Name × ConstantInfo)) : List (String × String) :=
  Id.run do
    let fixtureNames : NameSet :=
      decls.foldl (init := {}) fun s (n, _) => s.insert n
    let mut edges : List (String × String) := []
    let mut seenPairs : NameSet := {}
    for (depender, info) in decls do
      let used := info.getUsedConstantsAsSet
      for dependee in used do
        if dependee != depender && fixtureNames.contains dependee then
          -- Encode pair as a synthetic name key for dedup.
          let key := Name.mkStr dependee depender.toString
          if !seenPairs.contains key then
            seenPairs := seenPairs.insert key
            edges := (dependee.toString, depender.toString) :: edges
    return edges.reverse

/-- Module-level import edges: imported_module → importing_module (fixture only). -/
def collectImportEdges (env : Environment) : List (String × String) × List String :=
  Id.run do
    let mut edges : List (String × String) := []
    let mut imports : List String := []
    let mut seenImp : NameSet := {}
    let mut seenEdge : NameSet := {}
    let moduleNames := env.allImportedModuleNames
    for h : i in [0:moduleNames.size] do
      let importing := moduleNames[i]'h.upper
      if !isFixtureModule importing then
        continue
      let some data := env.header.moduleData[i]? | continue
      for imp in data.imports do
        let imported := imp.module
        if !isFixtureModule imported then
          continue
        let key := Name.mkStr imported importing.toString
        if !seenEdge.contains key then
          seenEdge := seenEdge.insert key
          edges := (imported.toString, importing.toString) :: edges
        if !seenImp.contains imported then
          seenImp := seenImp.insert imported
          imports := imported.toString :: imports
    return (edges.reverse, imports.reverse)

def declJson (name : Name) (info : ConstantInfo) : String :=
  let kind := kindOf info
  let short := shortName name
  let sig := s!"{kind} {short} : {info.type}"
  let path := modulePath name
  let isAx := kind == "axiom"
  "{" ++
    "\"name\": " ++ jsonString name.toString ++ ", " ++
    "\"kind\": " ++ jsonString kind ++ ", " ++
    "\"path\": " ++ jsonString path ++ ", " ++
    "\"line\": 0, " ++
    "\"signature\": " ++ jsonString sig ++ ", " ++
    "\"signature_hash\": \"\", " ++
    "\"is_axiom\": " ++ (if isAx then "true" else "false") ++ ", " ++
    "\"public\": true" ++
  "}"

def buildPayload (env : Environment) : String :=
  let decls := collectDeclarations env
  let axioms := collectAxioms env decls
  let declEdges := collectDeclEdges decls
  let (importEdges, fixtureImports) := collectImportEdges env
  let declJsons := decls.map fun (n, i) => declJson n i
  let declEdgeJsons := declEdges.map fun (a, b) => jsonEdge a b
  let importEdgeJsons := importEdges.map fun (a, b) => jsonEdge a b
  -- Backward-compatible dependency_edges == declaration edges (Environment-based).
  let notes := jsonStringArray [
    "emitted by lake exe lpe_extract (Lean elaborator environment)",
    "declaration edges from ConstantInfo.getUsedConstantsAsSet (dependee→depender)",
    "import_edges are module→module from Environment ModuleData",
    "limitations: tactic-erased consts; opaque/axiom body visibility; no per-decl import provenance"
  ]
  "{" ++
    "\"extraction_schema_version\": " ++ jsonString extractionSchemaVersion ++ ", " ++
    "\"declarations\": [" ++ ", ".intercalate declJsons ++ "], " ++
    "\"axioms_used\": " ++ jsonStringArray axioms ++ ", " ++
    "\"imports\": " ++ jsonStringArray fixtureImports ++ ", " ++
    "\"declaration_dependency_edges\": [" ++ ", ".intercalate declEdgeJsons ++ "], " ++
    "\"import_edges\": [" ++ ", ".intercalate importEdgeJsons ++ "], " ++
    "\"dependency_edges\": [" ++ ", ".intercalate declEdgeJsons ++ "], " ++
    "\"placeholders\": [], " ++
    "\"errors\": [], " ++
    "\"extractor\": \"lean.toolchain\", " ++
    "\"complete\": true, " ++
    "\"toolchain_available\": true, " ++
    "\"notes\": " ++ notes ++
  "}"

unsafe def main (args : List String) : IO UInt32 := do
  let filtered := args.filter (· != "--")
  let outPath :=
    match filtered with
    | p :: _ => p
    | [] => ".lpe/lean-extraction.json"
  let cwd ← IO.currentDir
  let lakeLib := cwd / ".lake" / "build" / "lib"
  initSearchPath (← findSysroot) [lakeLib.toString]
  let env ← importModules #[{ module := `LpeFixture }] {} (trustLevel := 0)
  let payload := buildPayload env
  let out : System.FilePath := outPath
  if let some parent := out.parent then
    IO.FS.createDirAll parent
  IO.FS.writeFile out payload
  IO.println s!"wrote {outPath}"
  return 0
