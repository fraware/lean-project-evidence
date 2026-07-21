/-
  Generic LPE extractor entrypoint.

  Args (positional):
    1. output JSON path
    2. comma-separated project module roots (e.g. LpeFixture,MyLib)
    3. snapshot fingerprint
    4. toolchain spec string
    5. optional comma-separated modules to import (defaults to roots)
-/
import Lean
import LpeExtract.Environment
import LpeExtract.Modules
import LpeExtract.Protocol

open Lean
open LpeExtract

unsafe def main (args : List String) : IO UInt32 := do
  let filtered := args.filter (· != "--")
  let outPath :=
    match filtered with
    | p :: _ => p
    | [] => ".lpe/lean-extraction-v2.json"
  let rootsArg :=
    match filtered.drop 1 with
    | r :: _ => r
    | [] => ""
  let snapshot :=
    match filtered.drop 2 with
    | s :: _ => s
    | [] => "unknown"
  let toolchain :=
    match filtered.drop 3 with
    | t :: _ => t
    | [] => ""
  let modulesArg :=
    match filtered.drop 4 with
    | m :: _ => m
    | [] => rootsArg

  if rootsArg.isEmpty then
    IO.eprintln "lpe_extract: missing project module roots argument"
    return 2

  let roots := Modules.parseNameList rootsArg
  let modules := Modules.parseNameList modulesArg
  let leanVer := Lean.versionString
  let lakeVer := ""

  let cwd ← IO.currentDir
  let lakeLib := cwd / ".lake" / "build" / "lib"
  initSearchPath (← findSysroot) [lakeLib.toString]

  let imports : Array Import := modules.map fun m => { module := m }
  let env ← importModules imports {} (trustLevel := 0)

  let allImported := Id.run do
    let mut ok := true
    for m in modules do
      if !env.allImportedModuleNames.contains m then
        ok := false
    pure ok
  let payload := Environment.buildPayload
    env roots snapshot leanVer lakeVer toolchain allImported
  let out : System.FilePath := outPath
  if let some parent := out.parent then
    IO.FS.createDirAll parent
  IO.FS.writeFile out payload
  IO.println s!"wrote {outPath}"
  return 0
