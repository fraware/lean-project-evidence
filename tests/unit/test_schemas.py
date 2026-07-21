from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from lpe.models import (
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    CandidateDescriptor,
    EvidencePacket,
    ObligationsFile,
    ProjectConfig,
    ProjectContract,
    ReviewDecision,
    RepositoryConfig,
    TPPRReport,
    TerminologyFile,
    UtilityEvent,
    VersionedStrictModel,
    parse_schema_version,
    validate_supported_schema_version,
)

VERSIONED_MODELS: tuple[type[VersionedStrictModel], ...] = (
    ProjectConfig,
    TerminologyFile,
    ObligationsFile,
    ProjectContract,
    CandidateDescriptor,
    EvidencePacket,
    ReviewDecision,
    UtilityEvent,
    TPPRReport,
)


def test_exported_schemas_are_valid(repository_root: Path) -> None:
    schema_dir = repository_root / "schemas"
    schemas = sorted(schema_dir.glob("*.schema.json"))
    assert schemas
    for path in schemas:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)


def test_exported_schemas_match_models(repository_root: Path) -> None:
    script = repository_root / "scripts" / "export_schemas.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.returncode == 0
    schema_dir = repository_root / "schemas"
    for path in sorted(schema_dir.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("model_cls", VERSIONED_MODELS)
def test_versioned_models_reject_unknown_fields(model_cls: type[VersionedStrictModel]) -> None:
    payload = model_cls.model_json_schema()
    required = set(payload.get("required", []))
    properties = payload.get("properties", {})
    minimal = {key: _minimal_value(properties[key]) for key in required if key in properties}
    minimal["unexpected_field"] = "not allowed"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model_cls.model_validate(minimal)


def _minimal_value(schema: dict) -> object:
    if "default" in schema:
        return schema["default"]
    schema_type = schema.get("type")
    if schema_type == "string":
        if schema.get("format") == "date-time":
            return "2026-01-01T00:00:00+00:00"
        return "example"
    if schema_type == "integer":
        return schema.get("minimum", 1)
    if schema_type == "number":
        return 1.0
    if schema_type == "boolean":
        return True
    if schema_type == "array":
        return []
    if schema_type == "object":
        return {}
    if "anyOf" in schema:
        return _minimal_value(schema["anyOf"][0])
    if "$ref" in schema:
        return {}
    raise AssertionError(f"unsupported schema fragment: {schema}")


def test_project_config_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProjectConfig.model_validate(
            {
                "schema_version": SCHEMA_VERSION,
                "project_id": "example-project",
                "title": "Example",
                "repository": {
                    "remote": "https://example.org/repo.git",
                },
                "rogue": True,
            }
        )


def test_parse_schema_version_accepts_semver() -> None:
    assert parse_schema_version("0.1.0") == (0, 1, 0)
    assert parse_schema_version("12.34.56") == (12, 34, 56)


@pytest.mark.parametrize(
    "version",
    ["0.1", "v0.1.0", "0.1.0-beta", "latest"],
)
def test_parse_schema_version_rejects_invalid(version: str) -> None:
    with pytest.raises(ValueError, match="semantic"):
        parse_schema_version(version)


def test_validate_supported_schema_version_accepts_current() -> None:
    assert validate_supported_schema_version(SCHEMA_VERSION) == SCHEMA_VERSION


def test_validate_supported_schema_version_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unsupported schema_version"):
        validate_supported_schema_version("9.9.9")


def test_supported_schema_versions_contains_current() -> None:
    assert SCHEMA_VERSION in SUPPORTED_SCHEMA_VERSIONS


def test_project_config_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ValidationError, match="unsupported schema_version"):
        ProjectConfig.model_validate(
            {
                "schema_version": "9.9.9",
                "project_id": "example-project",
                "title": "Example",
                "repository": RepositoryConfig(remote="https://example.org/repo.git").model_dump(),
            }
        )


def test_schema_version_policy_is_documented_in_engineering_spec(repository_root: Path) -> None:
    spec = (repository_root / "docs" / "ENGINEERING_SPEC.md").read_text(encoding="utf-8")
    assert "schema_version" in spec
    assert "semantic versions" in spec
