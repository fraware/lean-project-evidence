from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from lpe.hashing import sha256_value
from lpe.models import (
    ObligationsFile,
    PoliciesFile,
    ProjectConfig,
    ProjectContract,
    ReviewFile,
    TerminologyFile,
    validate_supported_schema_version,
)


class ContractError(ValueError):
    """Raised when a project contract fails structural or semantic validation."""


CONTRACT_FILES = (
    "project.yaml",
    "terminology.yaml",
    "obligations.yaml",
    "policies.yaml",
    "review.yaml",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ContractError(f"missing contract file: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ContractError(f"contract file must contain an object: {path}")
    return raw


def _validate_contract_schema_version(raw: dict[str, Any], path: Path) -> None:
    version = raw.get("schema_version")
    if version is None:
        raise ContractError(f"missing schema_version in {path}")
    if not isinstance(version, str):
        raise ContractError(f"schema_version must be a string in {path}")
    try:
        validate_supported_schema_version(version)
    except ValueError as exc:
        raise ContractError(str(exc)) from exc


def contract_directory(project_path: Path) -> Path:
    candidate = project_path / ".lean-project-contract"
    return candidate if candidate.exists() else project_path


def load_contract(project_path: Path) -> ProjectContract:
    directory = contract_directory(project_path.resolve())
    missing = [name for name in CONTRACT_FILES if not (directory / name).exists()]
    if missing:
        raise ContractError(
            f"incomplete contract in {directory}; missing files: {', '.join(missing)}"
        )

    project_raw = _load_yaml(directory / "project.yaml")
    terminology_raw = _load_yaml(directory / "terminology.yaml")
    obligations_raw = _load_yaml(directory / "obligations.yaml")
    policies_raw = _load_yaml(directory / "policies.yaml")
    review_raw = _load_yaml(directory / "review.yaml")

    for filename, raw in (
        ("project.yaml", project_raw),
        ("terminology.yaml", terminology_raw),
        ("obligations.yaml", obligations_raw),
        ("policies.yaml", policies_raw),
        ("review.yaml", review_raw),
    ):
        _validate_contract_schema_version(raw, directory / filename)

    try:
        project = ProjectConfig.model_validate(project_raw)
        terminology = TerminologyFile.model_validate(terminology_raw)
        obligations = ObligationsFile.model_validate(obligations_raw)
        policies = PoliciesFile.model_validate(policies_raw)
        review = ReviewFile.model_validate(review_raw)
    except ValueError as exc:
        raise ContractError(str(exc)) from exc

    intent_path = directory / "intent" / "project.md"
    if not intent_path.exists():
        raise ContractError(f"missing intent document: {intent_path}")
    intent = intent_path.read_text(encoding="utf-8").strip()
    if not intent:
        raise ContractError("intent document must not be empty")

    _validate_review_authorities(review, policies)

    unhashed = {
        "project": project.model_dump(mode="json"),
        "intent_markdown": intent,
        "terminology": terminology.model_dump(mode="json"),
        "obligations": obligations.model_dump(mode="json"),
        "policies": policies.model_dump(mode="json"),
        "review": review.model_dump(mode="json"),
    }
    return ProjectContract(
        project=project,
        intent_markdown=intent,
        terminology=terminology,
        obligations=obligations,
        policies=policies,
        review=review,
        contract_hash=sha256_value(unhashed),
    )


def _validate_review_authorities(review: ReviewFile, policies: PoliciesFile) -> None:
    configured_roles = {role for authority in review.authorities for role in authority.roles}
    missing_by_risk: list[str] = []
    for risk_class, rule in policies.risk_rules.items():
        if not rule.require_human_acceptance:
            continue
        for role in rule.required_roles:
            if role not in configured_roles:
                missing_by_risk.append(f"{risk_class.value}:{role}")
    if missing_by_risk:
        raise ContractError(
            "review authorities missing required roles from policies: "
            + ", ".join(sorted(missing_by_risk))
        )


def validate_candidate_obligations(
    contract: ProjectContract, project_id: str, obligation_ids: list[str]
) -> None:
    if project_id != contract.project.project_id:
        raise ContractError(
            f"candidate project_id {project_id!r} does not match {contract.project.project_id!r}"
        )
    known = {o.obligation_id for o in contract.obligations.obligations}
    unknown = set(obligation_ids) - known
    if unknown:
        raise ContractError(f"unknown obligation IDs: {sorted(unknown)}")
    if len(obligation_ids) != len(set(obligation_ids)):
        raise ContractError("duplicate obligation IDs in candidate")
