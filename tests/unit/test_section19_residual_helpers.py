"""Cheap residual coverage for compiler / extractor / generic helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import yaml

from lpe.evidence.compiler import (
    _extract_executor_from_notes,
    _is_incomplete_axiom_extractor,
    _is_toolchain_complete,
    _normalize_network_policy,
    _select_executor,
    _subject_hash,
)
from lpe.lean.extractor import (
    TOOLCHAIN_EXTRACTOR,
    _coerce_edges,
    _collect_uses,
    _find_placeholders,
    _module_name_from_path,
    _signature_from_header,
    expand_imports,
    impact_cone,
    lean_toolchain_available,
    list_lean_source_modules,
    project_requires_toolchain,
    signature_for_hash,
)
from lpe.lean.generic import (
    discover_lake_workspace,
    load_supported_toolchain_prefixes,
    read_toolchain_spec,
    snapshot_fingerprint_for,
    toolchain_is_supported,
)
from lpe.lean.models import ExtractionError
from lpe.models import EvidenceDimension


def test_compiler_normalize_and_select() -> None:
    assert _normalize_network_policy("") == "deny"
    assert _normalize_network_policy("ALLOW") == "allow"
    assert _normalize_network_policy("weird") == "deny"
    executor, isolated = _select_executor(insecure_host_exec=True, network_policy="allow")
    assert executor is not None
    assert isolated is False


def test_compiler_subject_hash_and_axiom_helpers() -> None:
    h = _subject_hash(
        check_id="lean.build",
        dimension=EvidenceDimension.KERNEL,
        details={"x": 1},
    )
    assert len(h) == 16
    assert _is_incomplete_axiom_extractor("lean.regex-extractor") is True
    assert _is_incomplete_axiom_extractor(TOOLCHAIN_EXTRACTOR) is False

    complete = MagicMock()
    complete.extractor = TOOLCHAIN_EXTRACTOR
    complete.complete = True
    complete.errors = []
    complete.notes = ["produced by lake exe lpe_extract via docker-sandbox"]
    assert _is_toolchain_complete(complete) is True
    assert _extract_executor_from_notes(complete) == "docker-sandbox"

    incomplete = MagicMock()
    incomplete.extractor = "lean.regex-extractor"
    incomplete.complete = False
    incomplete.errors = ["x"]
    incomplete.notes = ["nope"]
    assert _is_toolchain_complete(incomplete) is False
    assert _extract_executor_from_notes(incomplete) is None

    hostish = MagicMock()
    hostish.notes = ["produced by lake exe lpe_extract"]
    assert _extract_executor_from_notes(hostish) == "host"


def test_generic_toolchain_and_discover(tmp_path: Path) -> None:
    assert read_toolchain_spec(tmp_path) == ""
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.14.0\n", encoding="utf-8")
    assert "v4.14" in read_toolchain_spec(tmp_path)

    assert toolchain_is_supported("") is False
    assert toolchain_is_supported("leanprover/lean4:v4.14.0", prefixes=("leanprover/lean4:v4.14",))
    assert not toolchain_is_supported("other", prefixes=("leanprover/lean4:v4.14",))

    fp = snapshot_fingerprint_for(tree_hash="a" * 64, toolchain_spec="t")
    assert len(fp) == 64

    matrix = tmp_path / "matrix.yaml"
    matrix.write_text(
        yaml.safe_dump(
            {
                "toolchains": [
                    {"status": "pending_selection"},
                    {"prefix": "leanprover/lean4:v4.99", "status": "supported"},
                    {"id": "x", "accepted_prefixes": ["custom/"]},
                    "bad",
                ]
            }
        ),
        encoding="utf-8",
    )
    prefixes = load_supported_toolchain_prefixes(matrix)
    assert any("v4.99" in p or p.startswith("custom") for p in prefixes)

    bad_matrix = tmp_path / "bad.yaml"
    bad_matrix.write_text("{[", encoding="utf-8")
    assert load_supported_toolchain_prefixes(bad_matrix)

    err = discover_lake_workspace(tmp_path)
    assert isinstance(err, ExtractionError)

    (tmp_path / "lakefile.toml").write_text(
        'name = "Demo"\n[[lean_lib]]\nname = "Demo"\n',
        encoding="utf-8",
    )
    info = discover_lake_workspace(tmp_path)
    assert not isinstance(info, ExtractionError)
    assert info.package_name == "Demo"


def test_extractor_helpers(tmp_path: Path) -> None:
    assert _coerce_edges([("a", "b"), ["c", "d"], "bad", ("x",)]) == [
        ("a", "b"),
        ("c", "d"),
    ]
    assert _module_name_from_path("Foo/Bar.lean") == "Foo.Bar"
    assert signature_for_hash("theorem foo : Nat := 1").startswith("theorem")
    assert _signature_from_header("def foo : Nat := 1")
    assert "sorry" in _find_placeholders("have := sorry")
    uses = _collect_uses("exact foo bar", known_names={"foo", "bar", "self"}, self_name="self")
    assert "foo" in uses

    assert expand_imports(["Foo", "Missing"], {"Foo", "Bar"}) == ["Foo"]
    assert isinstance(lean_toolchain_available(tmp_path), bool)
    (tmp_path / "A.lean").write_text("def x := 1\n", encoding="utf-8")
    mods = list_lean_source_modules(tmp_path)
    assert "A" in mods
    _ = project_requires_toolchain(tmp_path)

    cone = impact_cone({"Foo.a": ["Foo.b"], "Foo.b": ["Foo.c"]}, changed={"Foo.a"})
    assert "Foo.b" in cone
    assert "Foo.c" in cone


def test_generic_list_modules_and_aggregator_paths(tmp_path: Path) -> None:
    from lpe.lean.generic import (
        _list_lean_modules_under,
        _write_aggregator,
        _write_ephemeral_lakefile,
    )

    lib = tmp_path / "Demo"
    lib.mkdir()
    (lib / "A.lean").write_text("--\n", encoding="utf-8")
    (lib / ".git").mkdir()
    mods = _list_lean_modules_under(lib, rel_prefix="Demo")
    assert any(m.startswith("Demo") for m in mods)

    dest = tmp_path / "ephemeral"
    dest.mkdir()
    (dest / "LpeExtract").mkdir()
    _write_ephemeral_lakefile(dest, target_name="Demo", target_path=tmp_path)
    assert (dest / "lakefile.toml").is_file()
    _write_aggregator(dest, ("Demo.A", "Demo.B"))
    assert (dest / "LpeExtract" / "Aggregator.lean").is_file()
