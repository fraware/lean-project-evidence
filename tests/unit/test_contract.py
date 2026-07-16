from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from lpe.contract.loader import ContractError, load_contract, validate_candidate_obligations


def test_example_contract_loads(example_project: Path) -> None:
    contract = load_contract(example_project)
    assert contract.project.project_id == "example-category-project"
    assert len(contract.contract_hash) == 64
    assert {o.obligation_id for o in contract.obligations.obligations} == {
        "O-01",
        "O-02",
        "O-03",
    }


def test_example_contract_hash_is_stable(example_project: Path) -> None:
    first = load_contract(example_project).contract_hash
    second = load_contract(example_project).contract_hash
    assert first == second


def test_candidate_obligations_validate(example_project: Path) -> None:
    contract = load_contract(example_project)
    validate_candidate_obligations(contract, "example-category-project", ["O-01"])


def test_candidate_obligations_reject_duplicates(example_project: Path) -> None:
    contract = load_contract(example_project)
    with pytest.raises(ContractError, match="duplicate obligation IDs"):
        validate_candidate_obligations(
            contract, "example-category-project", ["O-01", "O-01"]
        )


@pytest.mark.parametrize(
    ("fixture_name", "expected_message"),
    [
        ("cyclic-obligations", "cycle"),
        ("unknown-downstream", "unknown downstream"),
        ("unsupported-schema-version", "unsupported schema_version"),
        ("missing-review-role", "missing required roles"),
        ("empty-intent", "intent document must not be empty"),
    ],
)
def test_negative_contract_fixtures(
    repository_root: Path, fixture_name: str, expected_message: str
) -> None:
    fixture_root = repository_root / "tests" / "fixtures" / "contracts" / fixture_name
    with pytest.raises(ContractError, match=expected_message):
        load_contract(fixture_root)


def test_incomplete_contract_reports_missing_files(tmp_path: Path, example_project: Path) -> None:
    project = tmp_path / "broken-project"
    shutil.copytree(example_project / ".lean-project-contract", project / ".lean-project-contract")
    (project / ".lean-project-contract" / "review.yaml").unlink()
    with pytest.raises(ContractError, match="missing files"):
        load_contract(project)
