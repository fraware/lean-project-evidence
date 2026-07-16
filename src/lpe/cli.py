from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Annotated

import typer

from lpe import __version__
from lpe.contract.loader import load_contract, validate_candidate_obligations
from lpe.contract.migration import (
    apply_contract_migration,
    check_contract_schema_versions,
    dry_run_contract_migration,
)
from lpe.evidence.compiler import (
    HostExecutionRefusedError,
    NetworkPolicyError,
    compile_evidence,
)
from lpe.execution.allowlist import CommandAllowlistError
from lpe.execution.sandbox import DEFAULT_DOCKER_IMAGE, DockerSandboxExecutor
from lpe.gate.month_one import evaluate_month_one_gate, format_gate_report
from lpe.git.diff import GitError
from lpe.github.check import packet_to_github_check, render_check_payload
from lpe.github.submit import (
    GitHubSubmitError,
    parse_owner_repo,
    submit_check_run,
)
from lpe.ledger.store import LedgerAuthError, LedgerIntegrityError, LedgerStore
from lpe.metrics.tppr import compute_tppr
from lpe.models import (
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    CandidateDescriptor,
    ReviewDecision,
    ReviewDecisionValue,
)
from lpe.paths import PathTraversalError
from lpe.reporting.markdown import render_packet
from lpe.review.authority import (
    AuthorityError,
    can_record_acceptance,
    validate_decision_for_risk,
    validate_reviewer_authority,
)
from lpe.review.decisions import record_review_decision

app = typer.Typer(help="Project-grounded evidence for AI-assisted Lean development")
contract_app = typer.Typer(help="Project contract operations")
candidate_app = typer.Typer(help="Candidate operations")
evidence_app = typer.Typer(help="Evidence compiler")
ledger_app = typer.Typer(help="Append-only utility ledger")
tppr_app = typer.Typer(help="Trusted Project Progress Rate")
review_app = typer.Typer(help="Review decision recording")
gate_app = typer.Typer(help="Month-one gate evaluation")
lean_app = typer.Typer(help="Lean toolchain helpers")
github_app = typer.Typer(help="GitHub Check adapters (dry-run by default)")
pilot_app = typer.Typer(
    help=(
        "Durable pilot warehouse (ledger-backed instrumentation; "
        "not §21 / no causal claims)"
    )
)

app.add_typer(contract_app, name="contract")
app.add_typer(candidate_app, name="candidate")
app.add_typer(evidence_app, name="evidence")
app.add_typer(ledger_app, name="ledger")
app.add_typer(tppr_app, name="tppr")
app.add_typer(review_app, name="review")
app.add_typer(gate_app, name="gate")
app.add_typer(lean_app, name="lean")
app.add_typer(github_app, name="github")
app.add_typer(pilot_app, name="pilot")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@app.command()
def doctor(
    ledger: Annotated[
        Path | None,
        typer.Option(
            "--ledger",
            exists=True,
            dir_okay=False,
            help="Optional ledger SQLite path for permission warnings.",
        ),
    ] = None,
) -> None:
    """Report local capabilities without changing the system."""
    image = os.environ.get("LPE_DOCKER_IMAGE", DEFAULT_DOCKER_IMAGE)
    lean_image_hint = None
    if image == DEFAULT_DOCKER_IMAGE or "ubuntu:" in image:
        lean_image_hint = (
            "Default/ubuntu images are not Lean-capable. Set "
            "LPE_DOCKER_IMAGE=lpe-lean:4.14 for typecheck+extract "
            "(see docker/lpe-lean/)."
        )
    status: dict = {
        "lpe_version": __version__,
        "git": shutil.which("git"),
        "lake": shutil.which("lake"),
        "lean": shutil.which("lean"),
        "docker": shutil.which("docker"),
        "docker_sandbox_available": DockerSandboxExecutor.is_available(),
        "docker_image": image,
        "docker_image_lean_capable_hint": lean_image_hint,
        "sqlite_version": sqlite3.sqlite_version,
    }
    if ledger is not None:
        status["ledger"] = _ledger_permission_report(ledger)
    typer.echo(json.dumps(status, indent=2))


def _ledger_permission_report(path: Path) -> dict:
    """Warn when ledger path looks world-writable (POSIX); honest on Windows."""
    import stat

    report: dict = {
        "path": str(path.resolve()),
        "exists": path.is_file(),
        "warnings": [],
        "ok": True,
    }
    if not path.is_file():
        report["ok"] = False
        report["warnings"].append("ledger path is not a file")
        return report

    if os.name == "nt":
        report["platform"] = "windows"
        report["warnings"].append(
            "POSIX world-writable mode bits are not authoritative on Windows; "
            "ensure the ledger directory ACLs restrict write to operators "
            "(docs/25_LEDGER_THREAT_MODEL.md)"
        )
        report["supported_retention"] = (
            "lpe ledger archive --output ARCHIVE.jsonl then verify; "
            "optional fresh lpe ledger init for a new working set"
        )
        return report

    mode = path.stat().st_mode
    parent_mode = path.parent.stat().st_mode
    report["mode"] = oct(stat.S_IMODE(mode))
    report["parent_mode"] = oct(stat.S_IMODE(parent_mode))
    if mode & stat.S_IWOTH:
        report["ok"] = False
        report["warnings"].append(
            "ledger file is world-writable (other write bit set)"
        )
    if parent_mode & stat.S_IWOTH:
        report["ok"] = False
        report["warnings"].append(
            "ledger parent directory is world-writable"
        )
    report["supported_retention"] = (
        "lpe ledger archive --output ARCHIVE.jsonl then verify; "
        "optional fresh lpe ledger init for a new working set"
    )
    return report

@contract_app.command("validate")
def contract_validate(
    project: Annotated[Path, typer.Argument(exists=True, file_okay=False)]
) -> None:
    contract = load_contract(project)
    typer.echo(
        json.dumps(
            {
                "valid": True,
                "project_id": contract.project.project_id,
                "contract_hash": contract.contract_hash,
                "obligation_count": len(contract.obligations.obligations),
            },
            indent=2,
        )
    )


@candidate_app.command("validate")
def candidate_validate(
    candidate_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    project: Annotated[
        Path | None,
        typer.Option("--project", exists=True, file_okay=False),
    ] = None,
) -> None:
    candidate = CandidateDescriptor.model_validate(_read_json(candidate_path))
    if project is not None:
        contract = load_contract(project)
        validate_candidate_obligations(
            contract, candidate.project_id, candidate.obligation_ids
        )
    typer.echo(candidate.model_dump_json(indent=2))


@evidence_app.command("compile")
def evidence_compile(
    project: Annotated[Path, typer.Option("--project", exists=True, file_okay=False)],
    candidate_path: Annotated[
        Path, typer.Option("--candidate", exists=True, dir_okay=False)
    ],
    output: Annotated[Path, typer.Option("--output")],
    skip_build: Annotated[bool, typer.Option("--skip-build")] = False,
    insecure_host_exec: Annotated[
        bool,
        typer.Option(
            "--insecure-host-exec",
            help=(
                "Allow unisolated host subprocess builds when Docker is unavailable "
                "or when explicitly preferring host execution. Not recommended for "
                "untrusted repositories."
            ),
        ),
    ] = False,
    sandbox: Annotated[
        bool,
        typer.Option(
            "--sandbox/--no-sandbox",
            help="Prefer Docker sandbox (default). --no-sandbox requires --insecure-host-exec.",
        ),
    ] = True,
    worktree: Annotated[
        bool,
        typer.Option(
            "--worktree/--no-worktree",
            help=(
                "Execute builds in an isolated git worktree checked out at head_commit "
                "(default: on). Prefer this so Lake artifacts do not mutate the live tree."
            ),
        ),
    ] = True,
    markdown: Annotated[Path | None, typer.Option("--markdown")] = None,
    github_check: Annotated[Path | None, typer.Option("--github-check")] = None,
) -> None:
    candidate = CandidateDescriptor.model_validate(_read_json(candidate_path))
    try:
        packet = compile_evidence(
            project,
            candidate,
            skip_build=skip_build,
            insecure_host_exec=insecure_host_exec,
            use_sandbox=sandbox if sandbox else False,
            use_worktree=worktree and not skip_build,
        )
    except (
        HostExecutionRefusedError,
        NetworkPolicyError,
        CommandAllowlistError,
        GitError,
        PathTraversalError,
    ) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(packet.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if markdown is not None:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(render_packet(packet), encoding="utf-8")
    if github_check is not None:
        check = packet_to_github_check(packet)
        github_check.parent.mkdir(parents=True, exist_ok=True)
        github_check.write_text(json.dumps(render_check_payload(check), indent=2) + "\n", encoding="utf-8")
    typer.echo(str(output))


@ledger_app.command("init")
def ledger_init(path: Annotated[Path, typer.Argument()]) -> None:
    LedgerStore(path).initialize()
    typer.echo(str(path))


@ledger_app.command("append")
def ledger_append(
    path: Annotated[Path, typer.Argument()],
    event_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    project: Annotated[
        Path | None,
        typer.Option(
            "--project",
            exists=True,
            file_okay=False,
            help=(
                "When set, require event.project_id to match the contract "
                "(AUDIT-017). Anonymous actor_id is always rejected."
            ),
        ),
    ] = None,
) -> None:
    from lpe.models import UtilityEvent

    event = UtilityEvent.model_validate(_read_json(event_path))
    if project is not None:
        contract = load_contract(project)
        if event.project_id != contract.project.project_id:
            typer.echo(
                f"event.project_id {event.project_id!r} does not match contract "
                f"{contract.project.project_id!r}",
                err=True,
            )
            raise typer.Exit(code=1)
    try:
        digest = LedgerStore(path).append(event)
    except LedgerAuthError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(digest)


@ledger_app.command("verify")
def ledger_verify(path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    LedgerStore(path).verify()
    typer.echo("valid")


@ledger_app.command("export")
def ledger_export(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output")],
    verify: Annotated[
        bool,
        typer.Option(
            "--verify/--no-verify",
            help="After export, re-verify the JSONL hash chain (default: on).",
        ),
    ] = True,
) -> None:
    store = LedgerStore(path)
    store.export_jsonl(output)
    if verify:
        try:
            count = LedgerStore.verify_exported_jsonl(output)
        except LedgerIntegrityError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"{output} ({count} events, chain verified)")
    else:
        typer.echo(str(output))


@ledger_app.command("archive")
def ledger_archive(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help="Verified JSONL archive path (must not be the live SQLite file).",
        ),
    ],
) -> None:
    """Verify live ledger, write verified JSONL archive; never rewrite the chain.

    Retention/compaction prototype: archive is the offline audit artifact.
    To shrink the working set, ``lpe ledger init`` a fresh SQLite path and keep
    the JSONL. See docs/06_UTILITY_LEDGER_SPEC.md (retention) and
    docs/25_LEDGER_THREAT_MODEL.md.
    """
    store = LedgerStore(path)
    try:
        result = store.archive_verified_jsonl(output)
    except LedgerIntegrityError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "events": result["events"],
                "archive": result["archive"],
                "live_ledger": result["live_ledger"],
                "live_unchanged": True,
                "next_steps": [
                    "Retain the verified JSONL as the offline audit artifact.",
                    "Do not DELETE/UPDATE events in the live SQLite file.",
                    (
                        "Optional fresh working set: "
                        f"{result['fresh_ledger_hint']}"
                    ),
                ],
            },
            indent=2,
        )
    )


@contract_app.command("schema-check")
def contract_schema_check(
    project: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
) -> None:
    """Detect schema_version values; refuse unknown; print supported bump path."""
    try:
        report = check_contract_schema_versions(project)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "schema_versions": report["versions"],
                "supported": sorted(SUPPORTED_SCHEMA_VERSIONS),
                "current": SCHEMA_VERSION,
                "bump_path": (
                    "See docs/18_CONTRACT_MIGRATION.md: bump SCHEMA_VERSION and "
                    "SUPPORTED_SCHEMA_VERSIONS together, export schemas, migrate "
                    "examples, then re-run pytest."
                ),
            },
            indent=2,
        )
    )


@contract_app.command("migrate-dry-run")
def contract_migrate_dry_run(
    project: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    target: Annotated[
        str | None,
        typer.Option(
            "--to",
            help="Target schema_version (default: current SCHEMA_VERSION).",
        ),
    ] = None,
) -> None:
    """Plan a contract schema_version rewrite without mutating files."""
    try:
        report = dry_run_contract_migration(project, target_version=target)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(report, indent=2))
    if not report.get("ok"):
        raise typer.Exit(code=1)


@contract_app.command("migrate")
def contract_migrate(
    project: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    target: Annotated[
        str | None,
        typer.Option(
            "--to",
            help="Target schema_version (default: current SCHEMA_VERSION).",
        ),
    ] = None,
    write: Annotated[
        bool,
        typer.Option(
            "--write/--dry-run",
            help="Apply rewrite (default: dry-run only).",
        ),
    ] = False,
) -> None:
    """Versioned contract schema rewrite (refuse-unknown; opt-in --write)."""
    try:
        report = apply_contract_migration(
            project, target_version=target, write=write
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(report, indent=2))
    if not report.get("ok"):
        raise typer.Exit(code=1)


@github_app.command("submit-check")
def github_submit_check(
    packet_path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, help="Evidence packet JSON."),
    ],
    repo: Annotated[
        str,
        typer.Option("--repo", help="GitHub owner/repo slug."),
    ],
    post: Annotated[
        bool,
        typer.Option(
            "--post/--dry-run",
            help="POST via gh api (default: dry-run plan only).",
        ),
    ] = False,
    escalate_as: Annotated[
        str,
        typer.Option(
            "--escalate-as",
            help="ESCALATE conclusion: failure|neutral|action_required.",
        ),
    ] = "failure",
) -> None:
    """Adapt a packet to a Checks API payload and optionally POST via gh.

    Default is dry-run: prints argv + payload without calling GitHub.
    """
    from lpe.models import EvidencePacket

    if escalate_as not in {"failure", "neutral", "action_required"}:
        typer.echo(
            "escalate-as must be failure, neutral, or action_required",
            err=True,
        )
        raise typer.Exit(code=1)
    try:
        owner, name = parse_owner_repo(repo)
        packet = EvidencePacket.model_validate(_read_json(packet_path))
        check = packet_to_github_check(packet, escalate_as=escalate_as)  # type: ignore[arg-type]
        payload = render_check_payload(check)
        result = submit_check_run(payload, owner=owner, repo=name, post=post)
    except (GitHubSubmitError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(result.to_dict(), indent=2))

@tppr_app.command("compute")
def tppr_compute(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    project_id: Annotated[str, typer.Option("--project-id")],
) -> None:
    store = LedgerStore(path)
    store.verify()
    report = compute_tppr(store.events(project_id), project_id)
    typer.echo(report.model_dump_json(indent=2))


@review_app.command("record")
def review_record(
    project: Annotated[Path, typer.Option("--project", exists=True, file_okay=False)],
    decision_path: Annotated[Path, typer.Option("--decision", exists=True, dir_okay=False)],
    ledger: Annotated[Path, typer.Option("--ledger")],
    risk_class: Annotated[str, typer.Option("--risk-class")],
    obligation_ids: Annotated[
        str | None,
        typer.Option(
            "--obligation-ids",
            help="Comma-separated obligation ids for TPPR ACCEPT credit (optional).",
        ),
    ] = None,
) -> None:
    from lpe.models import RiskClass

    contract = load_contract(project)
    decision = ReviewDecision.model_validate(_read_json(decision_path))
    risk = RiskClass(risk_class)
    try:
        validate_reviewer_authority(
            contract,
            reviewer_id=decision.reviewer_id,
            reviewer_roles=decision.reviewer_roles,
            risk_class=risk,
        )
        validate_decision_for_risk(decision, risk)
        if (
            decision.decision is ReviewDecisionValue.ACCEPT
            and not can_record_acceptance(risk)
        ):
            raise AuthorityError(
                f"{risk.value} ACCEPT cannot be recorded via lpe review record "
                "(ADR 0003: no R3/R4 auto-accept; multi-authority acceptance is not "
                "implemented yet). Record REJECT/REQUEST_REPAIR, or use an authorized "
                "offline process."
            )
    except AuthorityError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    obl_list = (
        [part.strip() for part in obligation_ids.split(",") if part.strip()]
        if obligation_ids
        else None
    )
    digest = record_review_decision(
        ledger,
        decision,
        project_id=contract.project.project_id,
        obligation_ids=obl_list,
    )
    typer.echo(digest)


@gate_app.command("month-one")
def gate_month_one(
    repo: Annotated[
        Path | None,
        typer.Option("--repo", exists=True, file_okay=False),
    ] = None,
) -> None:
    report = evaluate_month_one_gate(repo)
    typer.echo(format_gate_report(report))
    if not report.all_passed:
        raise typer.Exit(code=1)


@lean_app.command("extract")
def lean_extract(
    repo: Annotated[
        Path,
        typer.Option("--repo", exists=True, file_okay=False),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force/--no-force",
            help="Re-run lake exe lpe_extract even when a complete JSON already exists.",
        ),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write extraction JSON summary here (default: stdout only).",
        ),
    ] = None,
) -> None:
    """Produce or load ``.lpe/lean-extraction.json`` via the toolchain helper.

    Wraps ``try_run_lake_extract`` / adaptive extract. Never invents
    ``complete: true`` without Lake output or a valid committed artifact.
    """
    from lpe.lean.extractor import extract_lean_repository
    from lpe.lean.toolchain import try_run_lake_extract

    lake_result = try_run_lake_extract(repo, force=force)
    result = lake_result or extract_lean_repository(repo, run_toolchain=not force)
    payload = result.to_dict()
    summary = {
        "extractor": result.extractor,
        "complete": result.complete,
        "extraction_schema_version": getattr(
            result, "extraction_schema_version", "1.0"
        ),
        "declaration_count": len(result.declarations),
        "declaration_edge_count": len(result.effective_declaration_edges()),
        "import_edge_count": len(result.import_edges),
        "errors": result.errors,
        "notes": result.notes,
        "artifact": str((repo / ".lpe" / "lean-extraction.json").resolve()),
    }
    typer.echo(json.dumps(summary, indent=2))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        typer.echo(str(output))
    if result.errors and not result.complete:
        raise typer.Exit(code=1)


@pilot_app.command("record")
def pilot_record(
    ledger: Annotated[Path, typer.Option("--ledger", help="Utility ledger SQLite path")],
    project_id: Annotated[str, typer.Option("--project-id")],
    actor: Annotated[
        str,
        typer.Option(
            "--actor",
            help="Non-anonymous actor_id (ledger auth fail-closed).",
        ),
    ],
    kind: Annotated[
        str,
        typer.Option(
            "--kind",
            help=(
                "Record kind: candidate | expert-time | packet-automated | "
                "overhead | outcome"
            ),
        ),
    ],
    candidate_id: Annotated[
        str | None,
        typer.Option("--candidate-id", help="Artifact / candidate id"),
    ] = None,
    condition_tag: Annotated[
        str | None,
        typer.Option("--condition-tag"),
    ] = None,
    obligation_ids: Annotated[
        str | None,
        typer.Option(
            "--obligation-ids",
            help="Comma-separated obligation ids (kind=candidate).",
        ),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", help="Expert-time category (kind=expert-time)."),
    ] = None,
    minutes: Annotated[
        float | None,
        typer.Option("--minutes", help="Expert-time minutes (kind=expert-time)."),
    ] = None,
    recommendation: Annotated[
        str | None,
        typer.Option("--recommendation", help="Packet recommendation (kind=packet-automated)."),
    ] = None,
    risk_class: Annotated[
        str | None,
        typer.Option("--risk-class", help="Risk class (kind=packet-automated)."),
    ] = None,
    decision: Annotated[
        str | None,
        typer.Option("--decision", help="Pilot outcome decision (kind=outcome)."),
    ] = None,
    baseline_minutes: Annotated[
        float | None,
        typer.Option("--baseline-minutes", help="Overhead baseline (kind=overhead)."),
    ] = None,
    instrumented_minutes: Annotated[
        float | None,
        typer.Option(
            "--instrumented-minutes",
            help="Overhead instrumented wall (kind=overhead).",
        ),
    ] = None,
    payload_path: Annotated[
        Path | None,
        typer.Option(
            "--payload",
            exists=True,
            dir_okay=False,
            help="Optional JSON overrides merged into the record.",
        ),
    ] = None,
) -> None:
    """Append a durable pilot warehouse event to the utility ledger."""
    from lpe.pilot.overhead import OverheadReport
    from lpe.pilot.warehouse import PilotWarehouse

    extras = _read_json(payload_path) if payload_path is not None else {}
    store = LedgerStore(ledger)
    try:
        warehouse = PilotWarehouse(store, actor_id=actor, project_id=project_id)
    except LedgerAuthError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    kind_norm = kind.strip().lower().replace("_", "-")
    try:
        if kind_norm == "candidate":
            cid = candidate_id or extras.get("candidate_id")
            tag = condition_tag or extras.get("condition_tag")
            obl = obligation_ids or extras.get("obligation_ids")
            if not cid or not tag:
                raise ValueError("--candidate-id and --condition-tag are required")
            if isinstance(obl, str):
                obl_list = [x.strip() for x in obl.split(",") if x.strip()]
            elif isinstance(obl, list):
                obl_list = [str(x) for x in obl]
            else:
                obl_list = []
            result = warehouse.register_candidate(
                candidate_id=str(cid),
                obligation_ids=obl_list,
                condition_tag=str(tag),
                packet_automated=bool(extras.get("packet_automated", False)),
                reproduction_exact=extras.get("reproduction_exact"),
            )
        elif kind_norm == "expert-time":
            cid = candidate_id or extras.get("candidate_id")
            tag = condition_tag or extras.get("condition_tag")
            cat = category or extras.get("category")
            mins = minutes if minutes is not None else extras.get("minutes")
            if not cid or not tag or not cat or mins is None:
                raise ValueError(
                    "--candidate-id, --condition-tag, --category, and --minutes "
                    "are required"
                )
            result = warehouse.record_expert_time(
                candidate_id=str(cid),
                category=str(cat),
                minutes=float(mins),
                condition_tag=str(tag),
            )
        elif kind_norm in {"packet-automated", "automated"}:
            cid = candidate_id or extras.get("candidate_id")
            tag = condition_tag or extras.get("condition_tag")
            if not cid or not tag:
                raise ValueError("--candidate-id and --condition-tag are required")
            result = warehouse.mark_packet_automated(
                candidate_id=str(cid),
                condition_tag=str(tag),
                recommendation=recommendation or extras.get("recommendation"),
                risk_class=risk_class or extras.get("risk_class"),
                hard_gate_passed=extras.get("hard_gate_passed"),
            )
        elif kind_norm == "overhead":
            base = (
                baseline_minutes
                if baseline_minutes is not None
                else extras.get("baseline_minutes")
            )
            inst = (
                instrumented_minutes
                if instrumented_minutes is not None
                else extras.get("instrumented_minutes")
            )
            if base is None or inst is None:
                raise ValueError(
                    "--baseline-minutes and --instrumented-minutes are required"
                )
            report = OverheadReport.compute(
                baseline_minutes=float(base),
                instrumented_minutes=float(inst),
            )
            result = warehouse.record_overhead_snapshot(
                artifact_id=str(
                    candidate_id or extras.get("candidate_id") or "pilot-overhead"
                ),
                report=report,
                condition_tag=condition_tag or extras.get("condition_tag"),
                note=extras.get("note"),
            )
        elif kind_norm == "outcome":
            cid = candidate_id or extras.get("candidate_id")
            tag = condition_tag or extras.get("condition_tag")
            dec = decision or extras.get("decision")
            if not cid or not tag or not dec:
                raise ValueError(
                    "--candidate-id, --condition-tag, and --decision are required"
                )
            result = warehouse.record_outcome(
                candidate_id=str(cid),
                condition_tag=str(tag),
                decision=str(dec),
                reproduction_exact=extras.get("reproduction_exact"),
                notes=extras.get("notes"),
            )
        else:
            raise ValueError(
                f"unknown --kind {kind!r}; expected candidate|expert-time|"
                "packet-automated|overhead|outcome"
            )
    except (LedgerAuthError, LedgerIntegrityError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(
        json.dumps(
            {
                "event_id": result.event_id,
                "event_hash": result.event_hash,
                "event_type": result.event_type.value,
                "durable": True,
                "section_21_cleared": False,
                "causal_claims": False,
            },
            indent=2,
        )
    )


@pilot_app.command("summary")
def pilot_summary(
    ledger: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    project_id: Annotated[str, typer.Option("--project-id")],
    format: Annotated[
        str,
        typer.Option("--format", help="json | markdown | both"),
    ] = "json",
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write report(s) here (file for json/markdown; dir for both).",
        ),
    ] = None,
    include_non_pilot: Annotated[
        bool,
        typer.Option(
            "--include-non-pilot/--pilot-only",
            help="Include non-warehouse project events in aggregations.",
        ),
    ] = False,
) -> None:
    """Aggregate durable pilot metrics from the utility ledger (not in-memory)."""
    from lpe.pilot.report import (
        render_summary_json,
        render_summary_markdown,
        write_summary_reports,
    )
    from lpe.pilot.summary import summarize_pilot

    store = LedgerStore(ledger)
    try:
        store.verify()
    except LedgerIntegrityError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    summary = summarize_pilot(
        store,
        project_id=project_id,
        pilot_events_only=not include_non_pilot,
    )
    fmt = format.strip().lower()
    if fmt == "json":
        text = render_summary_json(summary)
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
            typer.echo(str(output))
        else:
            typer.echo(text, nl=False)
    elif fmt == "markdown":
        text = render_summary_markdown(summary)
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
            typer.echo(str(output))
        else:
            typer.echo(text)
    elif fmt == "both":
        out_dir = output or Path("pilot_summary_out")
        json_path, md_path = write_summary_reports(summary, out_dir)
        typer.echo(json.dumps({"json": str(json_path), "markdown": str(md_path)}, indent=2))
    else:
        typer.echo(f"unknown --format {format!r}; expected json|markdown|both", err=True)
        raise typer.Exit(code=1)


@pilot_app.command("dry-run")
def pilot_dry_run(
    project: Annotated[Path, typer.Option("--project", exists=True, file_okay=False)],
    work_dir: Annotated[
        Path,
        typer.Option("--work-dir", help="Working directory for packets/reports."),
    ],
    repository_root: Annotated[
        Path | None,
        typer.Option(
            "--repository-root",
            exists=True,
            file_okay=False,
            help="Repo root containing examples/candidates (default: cwd).",
        ),
    ] = None,
    ledger: Annotated[
        Path | None,
        typer.Option("--ledger", help="Ledger path (default: work-dir/pilot-dry-run.sqlite3)."),
    ] = None,
    actor: Annotated[
        str,
        typer.Option("--actor", help="Non-anonymous pilot operator identity."),
    ] = "pilot-dry-run-operator",
) -> None:
    """Frozen corpus dry-run: durable warehouse events + summary reports.

    Instrumentation only — does not clear §21 or authorize causal claims.
    """
    from lpe.pilot.dry_run import run_frozen_corpus_dry_run

    root = repository_root or Path.cwd()
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = run_frozen_corpus_dry_run(
            example_project=project,
            repository_root=root,
            work_dir=work_dir,
            ledger_path=ledger,
            actor_id=actor,
        )
    except (LedgerAuthError, LedgerIntegrityError, RuntimeError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(
        json.dumps(
            {
                "corpus_size": result.corpus_size,
                "project_id": result.project_id,
                "ledger": str(result.ledger_path),
                "report_json": str(result.report_json),
                "report_md": str(result.report_md),
                "summary_json": str(result.summary_json),
                "summary_md": str(result.summary_md),
                "automation_rate": result.automation_rate,
                "overhead_within_budget": result.overhead_within_budget,
                "section_21_cleared": False,
                "causal_claims": False,
                "durable": True,
            },
            indent=2,
        )
    )


@pilot_app.command("init-partner")
def pilot_init_partner(
    dir: Annotated[
        Path,
        typer.Option("--dir", help="Partner working directory to create or validate."),
    ],
    project_id: Annotated[
        str,
        typer.Option("--project-id", help="Suggested project_id for ledger events."),
    ] = "partner-project",
    ledger_name: Annotated[
        str,
        typer.Option("--ledger-name", help="SQLite filename under ledger/."),
    ] = "partner-pilot.sqlite3",
    validate: Annotated[
        bool,
        typer.Option(
            "--validate/--create",
            help="Validate an existing scaffold instead of creating one.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Allow scaffolding into a non-empty directory."),
    ] = False,
) -> None:
    """Scaffold or validate a partner shadow-pilot working directory.

    Ready to instrument — not ready to claim §21 / causal utility.
    """
    from lpe.pilot.partner_scaffold import init_partner_pilot, validate_partner_scaffold

    if validate:
        result = validate_partner_scaffold(dir)
        payload = {
            "ok": result.ok,
            "root": str(result.root),
            "missing": list(result.missing),
            "errors": list(result.errors),
            "condition_tags": list(result.condition_tags),
            "analysis_plan_status": result.analysis_plan_status,
            "section_21_cleared": False,
            "ready_to_instrument": result.ready_to_instrument,
            "ready_to_claim": False,
        }
        typer.echo(json.dumps(payload, indent=2))
        if not result.ok:
            raise typer.Exit(code=1)
        return

    try:
        created = init_partner_pilot(
            dir,
            project_id=project_id,
            ledger_name=ledger_name,
            force=force,
        )
    except FileExistsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    check = validate_partner_scaffold(created.root)
    typer.echo(
        json.dumps(
            {
                "root": str(created.root),
                "ledger_path": str(created.ledger_path),
                "scaffold_version": created.scaffold_version,
                "validated": check.ok,
                "condition_tags": list(check.condition_tags),
                "analysis_plan_status": check.analysis_plan_status,
                "section_21_cleared": False,
                "causal_claims": False,
                "ready_to_instrument": check.ok,
                "ready_to_claim": False,
            },
            indent=2,
        )
    )
    if not check.ok:
        typer.echo(
            json.dumps({"missing": list(check.missing), "errors": list(check.errors)}),
            err=True,
        )
        raise typer.Exit(code=1)


@pilot_app.command("overhead")
def pilot_overhead(
    ledger: Annotated[Path, typer.Option("--ledger", help="Utility ledger SQLite path")],
    project_id: Annotated[str, typer.Option("--project-id")],
    actor: Annotated[
        str,
        typer.Option(
            "--actor",
            help="Non-anonymous actor_id (ledger auth fail-closed).",
        ),
    ],
    baseline_minutes: Annotated[
        float,
        typer.Option(
            "--baseline-minutes",
            help="Baseline wall-clock minutes without LPE instrumentation.",
        ),
    ],
    wall_minutes: Annotated[
        float,
        typer.Option(
            "--wall-minutes",
            help=(
                "Instrumented wall-clock minutes (compile/packet/UI). "
                "Not expert review minutes."
            ),
        ),
    ],
    candidate_id: Annotated[
        str | None,
        typer.Option("--candidate-id", help="Optional artifact / candidate id"),
    ] = None,
    condition_tag: Annotated[
        str | None,
        typer.Option("--condition-tag", help="Optional condition tag"),
    ] = None,
    budget_fraction: Annotated[
        float,
        typer.Option("--budget-fraction", help="Overhead budget (default 0.10)."),
    ] = 0.10,
    note: Annotated[
        str | None,
        typer.Option("--note", help="Field note (stored on ledger payload)."),
    ] = None,
    local_log: Annotated[
        Path | None,
        typer.Option(
            "--local-log",
            help="Optional JSONL mirror under the partner working dir.",
        ),
    ] = None,
) -> None:
    """Record field wall-clock instrumentation overhead (not review minutes).

    Appends ``overhead_snapshot`` (excluded from TPPR denominator). Does not
    clear §21 or authorize causal claims.
    """
    from lpe.pilot.field_overhead import record_field_overhead
    from lpe.pilot.warehouse import PilotWarehouse

    store = LedgerStore(ledger)
    try:
        warehouse = PilotWarehouse(store, actor_id=actor, project_id=project_id)
        result, entry = record_field_overhead(
            warehouse,
            baseline_minutes=baseline_minutes,
            wall_minutes=wall_minutes,
            budget_fraction=budget_fraction,
            candidate_id=candidate_id,
            condition_tag=condition_tag,
            note=note,
            local_log=local_log,
        )
    except (LedgerAuthError, LedgerIntegrityError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(
        json.dumps(
            {
                "event_id": result.event_id,
                "event_hash": result.event_hash,
                "event_type": result.event_type.value,
                "category": entry.category,
                "baseline_minutes": entry.baseline_minutes,
                "wall_minutes": entry.wall_minutes,
                "overhead_fraction": entry.overhead_fraction,
                "within_budget": entry.within_budget,
                "is_review_minutes": False,
                "durable": True,
                "section_21_cleared": False,
                "causal_claims": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
