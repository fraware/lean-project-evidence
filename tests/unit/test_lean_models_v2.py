"""Unit tests for Lean extraction protocol v2 models (CLOSURE-007)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from lpe.lean.models import (
    EXTRACTION_SCHEMA_V2,
    DeclarationRecord,
    ExtractionCompleteness,
    ExtractionError,
    LeanExtractionResultV2,
    empty_extraction_v2,
    v2_to_legacy_extraction,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "lean-extraction-v2.schema.json"


def test_schema_version_is_2_0() -> None:
    result = empty_extraction_v2(snapshot_fingerprint="abc")
    assert result.schema_version == EXTRACTION_SCHEMA_V2 == "2.0"


def test_completeness_has_no_global_bool() -> None:
    c = ExtractionCompleteness(environment_loaded=True)
    assert not hasattr(c, "complete")
    assert "complete" not in c.model_dump()
    assert c.any_dimension_complete() is True


def test_declaration_record_hashes_type() -> None:
    d = DeclarationRecord(
        fqn="Foo.bar",
        kind="theorem",
        module="Foo",
        type_pretty="Nat",
    )
    assert len(d.type_expr_hash) == 64


def test_result_roundtrip_and_schema() -> None:
    result = LeanExtractionResultV2(
        snapshot_fingerprint="fp",
        lean_version="4.14.0",
        lake_version="5.0.0",
        toolchain_spec="leanprover/lean4:v4.14.0",
        declarations=[
            DeclarationRecord(
                fqn="M.t",
                kind="theorem",
                module="M",
                type_pretty="True",
                type_expr_hash="a" * 64,
            )
        ],
        completeness=ExtractionCompleteness(
            environment_loaded=True,
            declaration_types_complete=True,
            known_limitations=["positions incomplete"],
        ),
    )
    payload = result.to_protocol_dict()
    again = LeanExtractionResultV2.from_protocol_dict(payload)
    assert again.declarations[0].fqn == "M.t"
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)


def test_unsupported_toolchain_flag() -> None:
    result = empty_extraction_v2(
        snapshot_fingerprint="x",
        errors=[
            ExtractionError(
                code="UNSUPPORTED_TOOLCHAIN",
                message="bad",
            )
        ],
    )
    assert result.is_unsupported_toolchain is True
    assert result.has_blocking_errors is True


def test_v2_to_legacy_bridge() -> None:
    result = LeanExtractionResultV2(
        snapshot_fingerprint="fp",
        declarations=[
            DeclarationRecord(
                fqn="M.n",
                kind="definition",
                module="M",
                type_pretty="Nat",
                type_expr_hash="b" * 64,
                public_visibility="public",
            )
        ],
        completeness=ExtractionCompleteness(
            environment_loaded=True,
            declaration_types_complete=True,
        ),
    )
    legacy = v2_to_legacy_extraction(result)
    assert legacy.declarations[0].name == "M.n"
    assert legacy.declarations[0].kind == "def"
    assert legacy.complete is True


@pytest.mark.slow
def test_scale_gate_matrix_loads() -> None:
    """Scale validation projects may be pending; matrix structure must parse."""
    import yaml

    matrix = ROOT / "docs" / "closure" / "compatibility-matrix.yaml"
    data = yaml.safe_load(matrix.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert len(data["projects"]) >= 5
    assert data["unsupported_policy"]["silent_regex_success"] == "forbidden"
