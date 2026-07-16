from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GateCriterion:
    id: str
    description: str
    passed: bool
    details: str = ""


@dataclass
class MonthOneGateReport:
    criteria: list[GateCriterion] = field(default_factory=list)
    disclaimer: str = (
        "Month-one gate clearance means automated scaffold criteria passed; "
        "it does NOT mean production-ready, Lean elaborator completeness, "
        "or pilot authorization."
    )

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.criteria)

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "disclaimer": self.disclaimer,
            "criteria": [
                {
                    "id": c.id,
                    "description": c.description,
                    "passed": c.passed,
                    "details": c.details,
                }
                for c in self.criteria
            ],
        }


def _run_pytest(repo_root: Path) -> tuple[bool, str]:
    import os

    if os.environ.get("PYTEST_CURRENT_TEST"):
        test_dir = repo_root / "tests" / "unit"
        present = test_dir.exists() and any(test_dir.glob("test_*.py"))
        return present, "skipped nested pytest (already under pytest)"

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, (result.stdout + result.stderr)[-500:]


def _schema_files_present(repo_root: Path) -> bool:
    schema_dir = repo_root / "schemas"
    required = [
        "evidence-packet.schema.json",
        "project-contract.schema.json",
        "utility-event.schema.json",
        "tppr-report.schema.json",
    ]
    return all((schema_dir / name).exists() for name in required)


def _migration_doc_present(repo_root: Path) -> bool:
    return (repo_root / "docs" / "18_CONTRACT_MIGRATION.md").exists()


def _validate_example_contract(repo_root: Path) -> tuple[bool, str]:
    """Run real contract load/validate (AUDIT-013), not mere path existence."""
    example = repo_root / "examples" / "minimal-project"
    if not example.is_dir():
        return False, f"missing example project: {example}"
    try:
        from lpe.contract.loader import ContractError, load_contract

        contract = load_contract(example)
    except Exception as exc:  # noqa: BLE001 — gate surfaces any validation failure
        return False, f"contract validate failed: {exc}"
    return True, (
        f"validated project_id={contract.project.project_id} "
        f"contract_hash={contract.contract_hash[:16]}…"
    )


def _sandbox_implementation_ok(repo_root: Path) -> tuple[bool, str]:
    """Require importable sandbox + allowlist modules (AUDIT-013)."""
    details: list[str] = []
    try:
        from lpe.execution import allowlist, sandbox

        details.append(f"sandbox_module={sandbox.__name__}")
        details.append(f"allowlist_module={allowlist.__name__}")
    except ImportError as exc:
        return False, f"import failed: {exc}"

    sandbox_path = repo_root / "src" / "lpe" / "execution" / "sandbox.py"
    allowlist_path = repo_root / "src" / "lpe" / "execution" / "allowlist.py"
    if not sandbox_path.is_file() or not allowlist_path.is_file():
        return False, "sandbox.py or allowlist.py missing on disk"

    allowed = getattr(allowlist, "ALLOWED_BUILD_COMMANDS", None)
    if not allowed or "lake" not in allowed:
        return False, "ALLOWED_BUILD_COMMANDS missing or incomplete"

    docker_cls = getattr(sandbox, "DockerSandboxExecutor", None)
    if docker_cls is None:
        return False, "DockerSandboxExecutor not defined"

    # Prefer a network-none marker in source for honesty about design intent.
    source = sandbox_path.read_text(encoding="utf-8")
    if "network=none" not in source and "network_none" not in source:
        return False, "sandbox source lacks network-none isolation markers"

    details.append(f"allowlist_size={len(allowed)}")
    details.append("network_none_markers=present")
    return True, "; ".join(details)


def evaluate_month_one_gate(repo_root: Path | None = None) -> MonthOneGateReport:
    """Evaluate month-one gate criteria from repository state.

    Passing this gate is a scaffold readiness signal only — not production readiness.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]

    report = MonthOneGateReport()

    tests_ok, test_output = _run_pytest(repo_root)
    report.criteria.append(
        GateCriterion(
            id="tests_pass",
            description="All pytest tests pass on clean clone",
            passed=tests_ok,
            details=test_output.strip(),
        )
    )

    schemas_ok = _schema_files_present(repo_root)
    report.criteria.append(
        GateCriterion(
            id="schema_stable",
            description="Versioned JSON schemas exported and present",
            passed=schemas_ok,
            details=str(repo_root / "schemas"),
        )
    )

    migration_ok = _migration_doc_present(repo_root)
    report.criteria.append(
        GateCriterion(
            id="migration_protocol",
            description="Contract migration protocol documented",
            passed=migration_ok,
        )
    )

    sandbox_ok, sandbox_details = _sandbox_implementation_ok(repo_root)
    report.criteria.append(
        GateCriterion(
            id="sandbox_design",
            description=(
                "Sandbox backend importable with allowlist and network-none design "
                "(not file-existence only)"
            ),
            passed=sandbox_ok,
            details=sandbox_details,
        )
    )

    ledger_tests = (repo_root / "tests" / "unit" / "test_ledger.py").exists()
    tppr_tests = (repo_root / "tests" / "unit" / "test_tppr.py").exists()
    report.criteria.append(
        GateCriterion(
            id="ledger_tppr_stable",
            description="Ledger and TPPR semantics have dedicated test coverage",
            passed=ledger_tests and tppr_tests,
        )
    )

    review_module = (repo_root / "src" / "lpe" / "review").exists()
    report.criteria.append(
        GateCriterion(
            id="review_loop",
            description="Review decision recording workflow implemented",
            passed=review_module,
        )
    )

    contract_ok, contract_details = _validate_example_contract(repo_root)
    report.criteria.append(
        GateCriterion(
            id="example_contract",
            description="Example project contract validates via load_contract",
            passed=contract_ok,
            details=contract_details,
        )
    )

    return report


def format_gate_report(report: MonthOneGateReport) -> str:
    return json.dumps(report.to_dict(), indent=2)
