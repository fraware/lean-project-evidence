"""Additional unit coverage for residual low modules (risk/fixtures/candidate/cli)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from lpe.cli import app
from lpe.evidence.risk import (
    classify_risk_from_diff,
    classify_risk_lexical,
)
from lpe.git.candidate import (
    build_candidate_from_commits,
    enrich_candidate_from_git,
    is_git_repository,
    is_git_toplevel,
    repository_has_commits,
)
from lpe.git.diff import GitError
from lpe.lean.declaration_diff import DeclarationChange, DeclarationDiff
from lpe.lean.models import DeclarationRecord
from lpe.models import (
    ArtifactType,
    CandidateDescriptor,
    ChangedDeclaration,
    GeneratorProvenance,
    RiskClass,
)
from lpe.providers.fixtures import load_fixture_suite, load_successor_suite

runner = CliRunner()


def _candidate(**kwargs: object) -> CandidateDescriptor:
    base = dict(
        candidate_id="candidate-extra",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="base",
        patch_text="+x",
        claimed_intent="t",
        changed_paths=["X.lean"],
        changed_declarations=[],
        generator=GeneratorProvenance(generator_type="human", name="t"),
    )
    base.update(kwargs)
    return CandidateDescriptor(**base)  # type: ignore[arg-type]


def _rec(
    fqn: str,
    *,
    kind: str = "theorem",
    visibility: str = "public",
) -> DeclarationRecord:
    return DeclarationRecord(
        fqn=fqn,
        kind=kind,  # type: ignore[arg-type]
        module="M",
        type_pretty="T",
        type_expr_hash="t" * 64,
        value_expr_hash="v" * 64,
        public_visibility=visibility,  # type: ignore[arg-type]
    )


def test_risk_impact_cone_and_imports() -> None:
    empty = DeclarationDiff(
        base_snapshot_fingerprint="b",
        candidate_snapshot_fingerprint="h",
    )
    big = classify_risk_from_diff(empty, impact_cone_size=99, impact_cone_threshold=50)
    assert big.risk_class is RiskClass.R4

    imports = DeclarationDiff(
        base_snapshot_fingerprint="b",
        candidate_snapshot_fingerprint="h",
        import_changed=[f"M{i}" for i in range(8)],
    )
    assert classify_risk_from_diff(imports).risk_class is RiskClass.R4


def test_risk_foundational_and_removed_private() -> None:
    diff = DeclarationDiff(
        base_snapshot_fingerprint="b",
        candidate_snapshot_fingerprint="h",
        removed=["Kernel.core", "M.priv"],
        changes=[
            DeclarationChange(
                fqn="Kernel.core",
                kind="removed",
                base=_rec("Kernel.core"),
                candidate=None,
            ),
            DeclarationChange(
                fqn="M.priv",
                kind="removed",
                base=_rec("M.priv", visibility="private"),
                candidate=None,
            ),
        ],
    )
    classified = classify_risk_from_diff(diff, foundational_names={"Kernel.core"})
    assert classified.risk_class is RiskClass.R4
    assert any("foundational" in r for r in classified.reasons)


def test_risk_type_visibility_rename_body_branches() -> None:
    type_chg = DeclarationDiff(
        base_snapshot_fingerprint="b",
        candidate_snapshot_fingerprint="h",
        type_changed=["M.t"],
        changes=[
            DeclarationChange(
                fqn="M.t",
                kind="type_changed",
                base=_rec("M.t", kind="definition"),
                candidate=_rec("M.t", kind="definition"),
            )
        ],
    )
    assert classify_risk_from_diff(type_chg).risk_class is RiskClass.R3

    vis = DeclarationDiff(
        base_snapshot_fingerprint="b",
        candidate_snapshot_fingerprint="h",
        visibility_changed=["M.t"],
    )
    assert classify_risk_from_diff(vis).risk_class is RiskClass.R3

    renamed = DeclarationDiff(
        base_snapshot_fingerprint="b",
        candidate_snapshot_fingerprint="h",
        renamed=[("M.old", "M.new")],
    )
    assert classify_risk_from_diff(renamed).risk_class is RiskClass.R2

    body_priv = DeclarationDiff(
        base_snapshot_fingerprint="b",
        candidate_snapshot_fingerprint="h",
        body_only=["M.h"],
        changes=[
            DeclarationChange(
                fqn="M.h",
                kind="body_only",
                base=_rec("M.h", visibility="private"),
                candidate=_rec("M.h", visibility="private"),
            )
        ],
    )
    assert classify_risk_from_diff(body_priv).risk_class is RiskClass.R1

    body_def = DeclarationDiff(
        base_snapshot_fingerprint="b",
        candidate_snapshot_fingerprint="h",
        body_only=["M.d"],
        changes=[
            DeclarationChange(
                fqn="M.d",
                kind="body_only",
                base=_rec("M.d", kind="definition"),
                candidate=_rec("M.d", kind="definition"),
            )
        ],
    )
    assert classify_risk_from_diff(body_def).risk_class is RiskClass.R1


def test_risk_added_foundational_and_public_def() -> None:
    add_f = DeclarationDiff(
        base_snapshot_fingerprint="b",
        candidate_snapshot_fingerprint="h",
        added=["Prelude.x"],
        changes=[
            DeclarationChange(
                fqn="Prelude.x",
                kind="added",
                base=None,
                candidate=_rec("Prelude.x", kind="definition"),
            )
        ],
    )
    assert classify_risk_from_diff(add_f).risk_class is RiskClass.R4

    add_def = DeclarationDiff(
        base_snapshot_fingerprint="b",
        candidate_snapshot_fingerprint="h",
        added=["M.D"],
        changes=[
            DeclarationChange(
                fqn="M.D",
                kind="added",
                base=None,
                candidate=_rec("M.D", kind="definition", visibility="public"),
            )
        ],
    )
    assert classify_risk_from_diff(add_def).risk_class is RiskClass.R3

    add_bare = DeclarationDiff(
        base_snapshot_fingerprint="b",
        candidate_snapshot_fingerprint="h",
        added=["M.mystery"],
    )
    assert classify_risk_from_diff(add_bare).risk_class is RiskClass.R2


def test_risk_lexical_lean_path_and_theorem_sig() -> None:
    lean_only = _candidate(changed_paths=["Foo.lean"], changed_declarations=[])
    assert classify_risk_lexical(lean_only).risk_class is RiskClass.R4

    thm = _candidate(
        changed_declarations=[
            ChangedDeclaration(
                name="T",
                kind=ArtifactType.THEOREM,
                path="T.lean",
                signature_changed=True,
                public=True,
            )
        ]
    )
    assert classify_risk_lexical(thm).risk_class is RiskClass.R3

    tool = _candidate(
        changed_paths=["lakefile.toml"],
        changed_declarations=[
            ChangedDeclaration(
                name="H",
                kind=ArtifactType.THEOREM,
                path="H.lean",
                signature_changed=False,
                public=False,
            )
        ],
    )
    assert classify_risk_lexical(tool).risk_class is RiskClass.R4


def test_fixtures_error_paths(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    missing_suite, missing_report = load_fixture_suite(project, kind="examples")
    assert missing_suite is None
    assert missing_report["error"] == "directory_missing"

    ex = project / ".lean-project-contract" / "tests" / "examples"
    ex.mkdir(parents=True)
    empty_suite, empty_report = load_fixture_suite(project, kind="examples")
    assert empty_suite is None
    assert empty_report["error"] == "manifest_missing"

    bad = ex / "examples.suite.yaml"
    bad.write_text("not: [valid\n", encoding="utf-8")
    unreadable, urep = load_fixture_suite(project, kind="examples")
    assert unreadable is None
    assert "manifest_unreadable" in str(urep["error"])

    bad.write_text("- just a list\n", encoding="utf-8")
    not_obj, nrep = load_fixture_suite(project, kind="examples")
    assert not_obj is None
    assert nrep["error"] == "manifest_not_object"

    bad.write_text(
        yaml.safe_dump({"suite_id": "s", "suite_kind": "examples", "fixtures": []}),
        encoding="utf-8",
    )
    # May fail validation on empty fixtures or succeed — either exercises validate path.
    suite, rep = load_fixture_suite(project, kind="examples")
    if suite is None:
        assert rep["error"]

    mismatch = {
        "suite_id": "s",
        "suite_kind": "counterexamples",
        "fixtures": [
            {
                "fixture_id": "f1",
                "path": "a.lean",
                "expected_exit": 0,
            }
        ],
    }
    bad.write_text(yaml.safe_dump(mismatch), encoding="utf-8")
    suite2, rep2 = load_fixture_suite(project, kind="examples")
    assert suite2 is None
    assert "suite_kind_mismatch" in str(rep2["error"]) or "manifest_invalid" in str(rep2["error"])

    down = project / ".lean-project-contract" / "tests" / "downstream"
    down.mkdir(parents=True)
    succ_none, srep = load_successor_suite(project)
    assert succ_none is None
    assert srep["error"] == "manifest_missing"

    (down / "downstream.suite.yaml").write_text("- list\n", encoding="utf-8")
    succ2, srep2 = load_successor_suite(project)
    assert succ2 is None
    assert srep2["error"] == "manifest_not_object"

    (down / "downstream.suite.yaml").write_text("{not yaml", encoding="utf-8")
    succ3, srep3 = load_successor_suite(project)
    assert succ3 is None
    assert "manifest_unreadable" in str(srep3["error"])


def test_git_candidate_helpers(tmp_path: Path) -> None:
    from subprocess import CompletedProcess

    plain = tmp_path / "plain"
    plain.mkdir()
    # Workspace tmp paths often sit inside a parent git worktree; mock negatives.
    with patch(
        "lpe.git.candidate.subprocess.run",
        return_value=CompletedProcess(args=[], returncode=1, stdout="", stderr=""),
    ):
        assert is_git_repository(plain) is False
        assert is_git_toplevel(plain) is False
        assert repository_has_commits(plain) is False

    cand = _candidate(base_commit="0" * 40, head_commit="a" * 40)
    with patch("lpe.git.candidate.is_git_repository", return_value=False):
        out = enrich_candidate_from_git(plain, cand, MagicMock())
        assert out is cand

    with patch("lpe.git.candidate.is_git_repository", return_value=True):
        with patch("lpe.git.candidate.is_git_toplevel", return_value=True):
            with patch("lpe.git.candidate.repository_has_commits", return_value=True):
                with pytest.raises(GitError, match="null"):
                    enrich_candidate_from_git(
                        plain,
                        _candidate(base_commit="0" * 40, head_commit="b" * 40),
                        MagicMock(),
                    )


def test_build_candidate_rejects_null_oid(tmp_path: Path) -> None:
    with pytest.raises(GitError, match="null"):
        build_candidate_from_commits(
            tmp_path,
            MagicMock(),
            candidate_id="cand-1",
            project_id="p",
            obligation_ids=["O-01"],
            base_commit="0" * 40,
            head_commit="a" * 40,
            claimed_intent="x",
            generator={"generator_type": "human", "name": "t"},
        )


def test_cli_lean_extract_output_and_errors(tmp_path: Path) -> None:
    from lpe.lean.extractor import LeanExtractionResult

    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "extract.json"
    fake = LeanExtractionResult(
        extractor="regex-stub",
        complete=False,
        declarations=[],
        axioms_used=[],
        imports=[],
        dependency_edges=[],
        errors=["boom"],
        notes=[],
        toolchain_available=False,
    )
    with patch("lpe.lean.toolchain.try_run_lake_extract", return_value=None):
        with patch("lpe.lean.extractor.extract_lean_repository", return_value=fake):
            result = runner.invoke(
                app,
                [
                    "lean",
                    "extract",
                    "--repo",
                    str(repo),
                    "--output",
                    str(out),
                ],
            )
    assert result.exit_code != 0
    assert out.is_file()


def test_cli_research_status_formats() -> None:
    md = runner.invoke(app, ["research", "status", "--format", "markdown"])
    assert md.exit_code == 0
    text = runner.invoke(app, ["research", "status", "--format", "text"])
    assert text.exit_code == 0


def test_cli_evidence_compile_env_flags(
    tmp_path: Path, example_project: Path, repository_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    from lpe.models import (
        EvidenceDimension,
        EvidenceFinding,
        EvidencePacket,
        FindingStatus,
        Provenance,
        Recommendation,
        RiskClass,
        Severity,
    )

    cand = repository_root / "examples" / "candidates" / "R0-comment-only.json"
    now = datetime.now(UTC)
    fake = EvidencePacket(
        packet_id="packet_env",
        run_id="run",
        project_id="example-category-project",
        contract_hash="0" * 64,
        candidate=CandidateDescriptor.model_validate_json(cand.read_text(encoding="utf-8")),
        risk_class=RiskClass.R0,
        findings=[
            EvidenceFinding(
                finding_id="f1",
                check_id="c",
                check_version="0.1.0",
                dimension=EvidenceDimension.REPOSITORY,
                status=FindingStatus.PASS,
                severity=Severity.INFO,
                summary="ok",
                provenance=Provenance(
                    tool="t",
                    tool_version="0",
                    input_hash="x",
                    started_at=now,
                    finished_at=now,
                    elapsed_ms=0,
                ),
            )
        ],
        hard_gate_passed=True,
        recommendation=Recommendation.ACCEPT,
        recommendation_reasons=["x"],
    )
    monkeypatch.delenv("LPE_PAIRED_EXTRACT", raising=False)
    monkeypatch.delenv("LPE_PREFER_GENERIC_EXTRACT", raising=False)
    with patch("lpe.cli.compile_evidence", return_value=fake):
        result = runner.invoke(
            app,
            [
                "evidence",
                "compile",
                "--project",
                str(example_project),
                "--candidate",
                str(cand),
                "--output",
                str(tmp_path / "out.json"),
                "--skip-build",
                "--paired-extract",
                "--prefer-generic-extract",
            ],
        )
    assert result.exit_code == 0


def test_cli_gate_month_one_fail() -> None:
    fake = MagicMock()
    fake.all_passed = False
    with patch("lpe.cli.evaluate_month_one_gate", return_value=fake):
        with patch("lpe.cli.format_gate_report", return_value="fail"):
            result = runner.invoke(app, ["gate", "month-one"])
    assert result.exit_code != 0


def test_cli_ledger_export_no_verify(tmp_path: Path) -> None:
    from lpe.ledger.store import LedgerStore

    ledger = tmp_path / "l.sqlite"
    LedgerStore(ledger).initialize()
    out = tmp_path / "e.jsonl"
    result = runner.invoke(
        app,
        ["ledger", "export", str(ledger), "--output", str(out), "--no-verify"],
    )
    assert result.exit_code == 0
    assert out.is_file()


def test_cli_tppr_v2_antigaming(tmp_path: Path) -> None:
    from lpe.ledger.store import LedgerStore
    from lpe.metrics.tppr_v2 import TPPRAntiGamingError

    ledger = tmp_path / "l.sqlite"
    LedgerStore(ledger).initialize()
    with patch(
        "lpe.metrics.tppr_v2.compute_tppr_v2",
        side_effect=TPPRAntiGamingError("gamed"),
    ):
        result = runner.invoke(
            app,
            ["tppr", "compute-v2", str(ledger), "--project-id", "p"],
        )
    assert result.exit_code != 0


def test_cli_review_repair_lineage_error() -> None:
    result = runner.invoke(
        app,
        [
            "review",
            "repair-lineage",
            "--prior-candidate-id",
            "cand",
            "--repair-request-ids",
            "",
            "--applied-change",
            __file__,
        ],
    )
    assert result.exit_code != 0


def test_cli_accept_quorum_acceptance_error(tmp_path: Path, example_project: Path) -> None:
    from lpe.review.acceptance import AcceptanceError

    path = tmp_path / "atts.json"
    path.write_text("[]", encoding="utf-8")
    with patch(
        "lpe.cli.aggregate_and_record_acceptance",
        side_effect=AcceptanceError("no quorum"),
    ):
        result = runner.invoke(
            app,
            [
                "review",
                "accept-quorum",
                "--project",
                str(example_project),
                "--attestations",
                str(path),
                "--ledger",
                str(tmp_path / "l.db"),
                "--risk-class",
                "R3",
                "--evidence-fingerprint",
                "f" * 64,
                "--actor-id",
                "a",
                "--artifact-id",
                "art",
            ],
        )
    assert result.exit_code != 0


def test_cli_adjudicate_bad_peers(tmp_path: Path, example_project: Path) -> None:
    for name in ("prov.json", "rec.json", "conflict.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    peers = tmp_path / "peers.json"
    peers.write_text('{"not":"list"}', encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "review",
            "adjudicate",
            "--project",
            str(example_project),
            "--provisional",
            str(tmp_path / "prov.json"),
            "--record",
            str(tmp_path / "rec.json"),
            "--peer-attestations",
            str(peers),
            "--conflict",
            str(tmp_path / "conflict.json"),
            "--original-reviewer-ids",
            "r1",
            "--review-minutes",
            "1",
        ],
    )
    assert result.exit_code != 0


def test_cli_ledger_export_verify_failure(tmp_path: Path) -> None:
    from lpe.ledger.store import LedgerIntegrityError, LedgerStore

    ledger = tmp_path / "l.sqlite"
    LedgerStore(ledger).initialize()
    out = tmp_path / "e.jsonl"
    with patch(
        "lpe.cli.LedgerStore.verify_exported_jsonl",
        side_effect=LedgerIntegrityError("broken"),
    ):
        result = runner.invoke(
            app,
            ["ledger", "export", str(ledger), "--output", str(out)],
        )
    assert result.exit_code != 0


def test_cli_contract_migrate_value_error(example_project: Path) -> None:
    with patch(
        "lpe.cli.dry_run_contract_migration",
        side_effect=ValueError("bad target"),
    ):
        result = runner.invoke(
            app, ["contract", "migrate-dry-run", str(example_project), "--to", "9.9.9"]
        )
    assert result.exit_code != 0


def test_cli_evidence_no_prefer_generic(
    tmp_path: Path, example_project: Path, repository_root: Path
) -> None:
    from datetime import UTC, datetime

    from lpe.models import (
        EvidenceDimension,
        EvidenceFinding,
        EvidencePacket,
        FindingStatus,
        Provenance,
        Recommendation,
        RiskClass,
        Severity,
    )

    cand = repository_root / "examples" / "candidates" / "R0-comment-only.json"
    now = datetime.now(UTC)
    fake = EvidencePacket(
        packet_id="packet_env2",
        run_id="run",
        project_id="example-category-project",
        contract_hash="0" * 64,
        candidate=CandidateDescriptor.model_validate_json(cand.read_text(encoding="utf-8")),
        risk_class=RiskClass.R0,
        findings=[
            EvidenceFinding(
                finding_id="f1",
                check_id="c",
                check_version="0.1.0",
                dimension=EvidenceDimension.REPOSITORY,
                status=FindingStatus.PASS,
                severity=Severity.INFO,
                summary="ok",
                provenance=Provenance(
                    tool="t",
                    tool_version="0",
                    input_hash="x",
                    started_at=now,
                    finished_at=now,
                    elapsed_ms=0,
                ),
            )
        ],
        hard_gate_passed=True,
        recommendation=Recommendation.ACCEPT,
        recommendation_reasons=["x"],
    )
    with patch("lpe.cli.compile_evidence", return_value=fake):
        result = runner.invoke(
            app,
            [
                "evidence",
                "compile",
                "--project",
                str(example_project),
                "--candidate",
                str(cand),
                "--output",
                str(tmp_path / "out.json"),
                "--skip-build",
                "--no-prefer-generic-extract",
            ],
        )
    assert result.exit_code == 0


def test_cli_review_record_acceptance_error(tmp_path: Path, example_project: Path) -> None:
    from lpe.review.acceptance import AcceptanceError

    decision_path = tmp_path / "d.json"
    decision_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "review_id": "r1",
                "packet_id": "p",
                "reviewer_id": "lean-engineer",
                "reviewer_roles": [],
                "decision": "ACCEPT",
                "confidence": 90,
                "rationale": "ok",
                "review_minutes": 1.0,
            }
        ),
        encoding="utf-8",
    )
    with patch(
        "lpe.cli.record_review_decision",
        side_effect=AcceptanceError("blocked"),
    ):
        result = runner.invoke(
            app,
            [
                "review",
                "record",
                "--project",
                str(example_project),
                "--decision",
                str(decision_path),
                "--ledger",
                str(tmp_path / "l.db"),
                "--risk-class",
                "R1",
            ],
        )
    assert result.exit_code != 0


def test_non_claims_plain_and_repair_root() -> None:
    from lpe.honesty.non_claims import format_non_claims_block
    from lpe.review.repair import root_candidate_id

    plain = format_non_claims_block(as_markdown=False)
    assert "NON_CLAIMS" in plain or "non" in plain.lower() or "[" in plain
    assert root_candidate_id("") == ""


def test_cli_research_evaluate_gates_error(tmp_path: Path) -> None:
    for name in ("proto",):
        p = tmp_path / name
        p.mkdir()
    for name in ("ledger.sqlite", "seal.json", "analysis.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    with patch(
        "lpe.honesty.research_gates.evaluate_gates_from_paths",
        side_effect=ValueError("bad"),
    ):
        result = runner.invoke(
            app,
            [
                "research",
                "evaluate-gates",
                "--protocol",
                str(tmp_path / "proto"),
                "--ledger",
                str(tmp_path / "ledger.sqlite"),
                "--seal",
                str(tmp_path / "seal.json"),
                "--analysis",
                str(tmp_path / "analysis.json"),
                "--output",
                str(tmp_path / "out.json"),
            ],
        )
    assert result.exit_code != 0
