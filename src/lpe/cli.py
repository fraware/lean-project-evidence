from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Annotated, Any

import typer

from lpe import __version__
from lpe.contract.loader import load_contract, validate_candidate_obligations
from lpe.contract.migration import (
    apply_contract_migration,
    check_contract_schema_versions,
    dry_run_contract_migration,
)
from lpe.evidence.compiler import compile_evidence
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
from lpe.ids import new_id
from lpe.ledger.seal import (
    STORAGE_RECOMMENDATION,
    LedgerSealError,
    default_seal_path,
    is_seal_colocated,
    verify_seal,
    write_seal,
)
from lpe.ledger.store import (
    LedgerAuthError,
    LedgerIntegrityError,
    LedgerStore,
    LedgerTransitionError,
)
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
from lpe.review.acceptance import AcceptanceError, aggregate_and_record_acceptance
from lpe.review.adjudication import (
    ADJUDICATOR_ROLE,
    AdjudicationError,
    AdjudicationRecord,
    ProvisionalJudgment,
    auditable_lineage,
    build_adjudication_attestation,
    reveal_peer_attestations,
    validate_adjudicator,
)
from lpe.review.authority import (
    AuthorityError,
    can_record_acceptance,
    validate_decision_for_risk,
    validate_reviewer_authority,
)
from lpe.review.conflicts import (
    ConflictError,
    ReviewerConflictDeclaration,
    require_eligible_for_primary_attestation,
)
from lpe.review.decisions import record_attestation_event, record_review_decision
from lpe.review.models import ReviewAttestationV2
from lpe.review.repair import (
    RepairError,
    build_repair_lineage,
    repair_completed_event,
    repair_requested_event,
)
from lpe.workspace.manager import HostExecutionRefusedError, NetworkPolicyError

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
    help=("Durable pilot warehouse (ledger-backed instrumentation; not §21 / no causal claims)")
)
research_app = typer.Typer(
    help=("Research gate status (M6/M7 / EPIC-039/040 blocked until §21; no training entrypoints)")
)
routing_app = typer.Typer(help="M6 routing (BLOCKED until §21 — exits non-zero)")

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
app.add_typer(research_app, name="research")
app.add_typer(routing_app, name="routing")


def _refuse_pilot_oversell_options(
    *,
    claim_section_21: bool = False,
    claim_causal: bool = False,
    claim_mathlib: bool = False,
) -> None:
    """Fail closed if CLI flags imply §21 / causal / Mathlib clearance."""
    from lpe.honesty.non_claims import OversellClaimError, refuse_oversell_flags

    try:
        refuse_oversell_flags(
            claim_section_21=claim_section_21,
            section_21_cleared=claim_section_21,
            claim_causal=claim_causal,
            causal_claims=claim_causal,
            claim_mathlib=claim_mathlib,
            mathlib_complete=claim_mathlib,
        )
    except OversellClaimError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


_PILOT_OVERSELL_FLAG_HELP = "FORBIDDEN: implies §21 / causal clearance. Always refused (exit 1)."


def _read_json(path: Path) -> Any:
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
    repo: Annotated[
        Path | None,
        typer.Option(
            "--repo",
            exists=True,
            file_okay=False,
            help="Optional Lean repo for extractor artifact detection.",
        ),
    ] = None,
) -> None:
    """Report local capabilities without changing the system."""
    from lpe.honesty.adr import adr_0003_status
    from lpe.honesty.lean_status import lean_extractor_status
    from lpe.honesty.non_claims import NON_CLAIMS_DOC_PATH, non_claims_payload
    from lpe.honesty.research_gates import research_status_payload

    image = os.environ.get("LPE_DOCKER_IMAGE", DEFAULT_DOCKER_IMAGE)
    lean_image_hint = None
    if image == DEFAULT_DOCKER_IMAGE or "ubuntu:" in image:
        lean_image_hint = (
            "Default/ubuntu images are not Lean-capable. Set "
            "LPE_DOCKER_IMAGE=lpe-lean:4.14 for typecheck+extract "
            "(see docker/lpe-lean/)."
        )
    lean_status = lean_extractor_status(repo)
    adr = adr_0003_status()
    status: dict[str, Any] = {
        "lpe_version": __version__,
        "git": shutil.which("git"),
        "lake": shutil.which("lake"),
        "lean": shutil.which("lean"),
        "docker": shutil.which("docker"),
        "docker_sandbox_available": DockerSandboxExecutor.is_available(),
        "docker_image": image,
        "docker_image_lean_capable_hint": lean_image_hint,
        "sqlite_version": sqlite3.sqlite_version,
        "lean_extractor": lean_status,
        "adr_0003": adr,
        "research_gates": research_status_payload(),
        "NON_CLAIMS": non_claims_payload(),
        "non_claims_doc": NON_CLAIMS_DOC_PATH,
    }
    if ledger is not None:
        status["ledger"] = _ledger_permission_report(ledger)
    typer.echo(json.dumps(status, indent=2))
    if not adr.get("active"):
        typer.echo("ADR 0003 enforcement inactive — unexpected", err=True)
        raise typer.Exit(code=1)


def _ledger_permission_report(path: Path) -> dict[str, Any]:
    """Warn when ledger path looks world-writable (POSIX); honest on Windows."""
    import stat

    report: dict[str, Any] = {
        "path": str(path.resolve()),
        "exists": path.is_file(),
        "warnings": [],
        "ok": True,
    }
    if not path.is_file():
        report["ok"] = False
        report["warnings"].append("ledger path is not a file")
        return report

    seal_path = default_seal_path(path)
    report["seal_path"] = str(seal_path)
    report["seal_exists"] = seal_path.is_file()
    report["seal_colocated"] = is_seal_colocated(path, seal_path) if seal_path.is_file() else None
    report["seal_storage_recommendation"] = STORAGE_RECOMMENDATION
    if not seal_path.is_file():
        report["warnings"].append(
            "no ledger seal found; run `lpe ledger seal --seal <off-host-path>` "
            "(or default then copy) and store the seal separately or read-only. "
            "Seal detects silent SQLite mutation only if the seal is protected; "
            "not hardware WORM (docs/LEDGER_AND_TPPR.md)"
        )
    elif is_seal_colocated(path, seal_path):
        report["warnings"].append(
            "ledger seal is co-located with the ledger directory; prefer "
            "`lpe ledger seal --seal <separate-path>` and verify with "
            "`lpe ledger verify-seal --seal <separate-path>` from read-only/"
            "off-host storage (docs/LEDGER_AND_TPPR.md)"
        )

    if os.name == "nt":
        report["platform"] = "windows"
        report["warnings"].append(
            "POSIX world-writable mode bits are not authoritative on Windows; "
            "ensure the ledger directory ACLs restrict write to operators "
            "(docs/LEDGER_AND_TPPR.md)"
        )
        report["supported_retention"] = (
            "lpe ledger archive --output ARCHIVE.jsonl then verify; "
            "optional fresh lpe ledger init for a new working set"
        )
        report["supported_seal"] = (
            "lpe ledger seal [--seal PATH] / lpe ledger verify-seal [--seal PATH]; "
            "prefer separate storage; optional LPE_LEDGER_SEAL_KEY HMAC (not WORM)"
        )
        return report

    mode = path.stat().st_mode
    parent_mode = path.parent.stat().st_mode
    report["mode"] = oct(stat.S_IMODE(mode))
    report["parent_mode"] = oct(stat.S_IMODE(parent_mode))
    if mode & stat.S_IWOTH:
        report["ok"] = False
        report["warnings"].append("ledger file is world-writable (other write bit set)")
    if parent_mode & stat.S_IWOTH:
        report["ok"] = False
        report["warnings"].append("ledger parent directory is world-writable")
    report["supported_retention"] = (
        "lpe ledger archive --output ARCHIVE.jsonl then verify; "
        "optional fresh lpe ledger init for a new working set"
    )
    report["supported_seal"] = (
        "lpe ledger seal [--seal PATH] / lpe ledger verify-seal [--seal PATH]; "
        "prefer separate storage; optional LPE_LEDGER_SEAL_KEY HMAC (not WORM)"
    )
    return report


@contract_app.command("validate")
def contract_validate(
    project: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
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
        validate_candidate_obligations(contract, candidate.project_id, candidate.obligation_ids)
    typer.echo(candidate.model_dump_json(indent=2))


@evidence_app.command("compile")
def evidence_compile(
    project: Annotated[Path, typer.Option("--project", exists=True, file_okay=False)],
    candidate_path: Annotated[Path, typer.Option("--candidate", exists=True, dir_okay=False)],
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
    paired_extract: Annotated[
        bool,
        typer.Option(
            "--paired-extract/--no-paired-extract",
            help=(
                "Run live elaborator-backed base+candidate extract (2x Lake). "
                "Default off — dry-run fingerprints still run. "
                "Equivalent to LPE_PAIRED_EXTRACT=1 when enabled."
            ),
        ),
    ] = False,
    prefer_generic_extract: Annotated[
        bool | None,
        typer.Option(
            "--prefer-generic-extract/--no-prefer-generic-extract",
            help=(
                "Prefer injected generic extract when Lake is available and the "
                "project has no lpe_extract target (default auto). "
                "Sets LPE_PREFER_GENERIC_EXTRACT for this invocation."
            ),
        ),
    ] = None,
    markdown: Annotated[Path | None, typer.Option("--markdown")] = None,
    github_check: Annotated[Path | None, typer.Option("--github-check")] = None,
) -> None:
    if paired_extract:
        os.environ["LPE_PAIRED_EXTRACT"] = "1"
    if prefer_generic_extract is True:
        os.environ["LPE_PREFER_GENERIC_EXTRACT"] = "1"
    elif prefer_generic_extract is False:
        os.environ["LPE_PREFER_GENERIC_EXTRACT"] = "0"
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
        github_check.write_text(
            json.dumps(render_check_payload(check), indent=2) + "\n",
            encoding="utf-8",
        )
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
    the JSONL. See docs/LEDGER_AND_TPPR.md (retention and threat model).
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
                    (f"Optional fresh working set: {result['fresh_ledger_hint']}"),
                ],
            },
            indent=2,
        )
    )


@ledger_app.command("seal")
def ledger_seal(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    seal: Annotated[
        Path | None,
        typer.Option(
            "--seal",
            help=(
                "Seal manifest path (default: <ledger_dir>/.lpe/ledger.seal.json). "
                "Prefer a path outside the ledger directory for separate storage."
            ),
        ),
    ] = None,
) -> None:
    """Verify the live chain, then write an external seal snapshot.

    Optional HMAC when ``LPE_LEDGER_SEAL_KEY`` is set. Detects silent SQLite
    mutation only if the seal is stored separately or read-only. Not WORM.
    """
    store = LedgerStore(path)
    try:
        result = write_seal(store, seal)
    except (LedgerIntegrityError, LedgerSealError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    manifest = result["manifest"]
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "seal_path": result["seal_path"],
                "event_count": manifest["event_count"],
                "global_tip": manifest["global_tip"],
                "export_content_hash": manifest["export_content_hash"],
                "custody": manifest["custody"],
                "not_worm": True,
                "colocated": result["colocated"],
                "storage_recommendation": result["storage_recommendation"],
                "custody_note": manifest["custody_note"],
            },
            indent=2,
        )
    )


@ledger_app.command("verify-seal")
def ledger_verify_seal(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    seal: Annotated[
        Path | None,
        typer.Option(
            "--seal",
            help=(
                "Seal manifest path to verify against (default: "
                "<ledger_dir>/.lpe/ledger.seal.json). Use the same alternate "
                "path written by `lpe ledger seal --seal`."
            ),
        ),
    ] = None,
) -> None:
    """Recompute live ledger state and compare against a seal file (fail closed)."""
    store = LedgerStore(path)
    try:
        result = verify_seal(store, seal)
    except (LedgerIntegrityError, LedgerSealError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(result, indent=2))


@ledger_app.command("migrate")
def ledger_migrate(
    source: Annotated[
        Path,
        typer.Option("--source", exists=True, dir_okay=False, help="Source 0.1 ledger"),
    ],
    target: Annotated[
        Path,
        typer.Option("--target", help="Target 0.2 ledger path (must not exist)"),
    ],
    mapping_report: Annotated[
        Path,
        typer.Option("--mapping-report", help="JSON report accounting for every source event"),
    ],
    source_seal: Annotated[
        Path | None,
        typer.Option("--source-seal", help="Optional seal path for source ledger"),
    ] = None,
    target_seal: Annotated[
        Path | None,
        typer.Option("--target-seal", help="Optional seal path for target ledger"),
    ] = None,
) -> None:
    """Migrate ledger 0.1→0.2 with typed legacy wrappers; verify and reseal both."""
    from lpe.ledger.migration import LedgerMigrationError, migrate_ledger

    try:
        report = migrate_ledger(
            source,
            target,
            mapping_report,
            source_seal=source_seal,
            target_seal=target_seal,
        )
    except (LedgerMigrationError, LedgerIntegrityError, LedgerSealError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "source_event_count": report["source_event_count"],
                "target_event_count": report["target_event_count"],
                "mapping_report": str(mapping_report),
                "source_seal_path": report["source_seal_path"],
                "target_seal_path": report["target_seal_path"],
                "invented_acceptance": False,
                "invented_persistence": False,
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
                    "See docs/CONTRACT.md (migration protocol): bump SCHEMA_VERSION and "
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
        report = apply_contract_migration(project, target_version=target, write=write)
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
            help=(
                "ESCALATE conclusion: failure|neutral|action_required "
                "(default failure = required-check fail-closed)."
            ),
        ),
    ] = "failure",
) -> None:
    """Adapt a packet to a Checks API payload and optionally POST via gh.

    Default is dry-run: prints exact ``gh api`` argv + JSON payload plan
    without calling GitHub. Use ``--post`` only after inspecting the plan.
    ESCALATE defaults to conclusion ``failure`` (fail-closed for required checks).
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
    # Dry-run and POST both emit the full plan (argv, payload, command_preview).
    typer.echo(json.dumps(result.to_dict(), indent=2))


@tppr_app.command("compute")
def tppr_compute(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    project_id: Annotated[str, typer.Option("--project-id")],
) -> None:
    """Legacy TPPR v1 over dict payloads (kept until ledger migration complete)."""
    store = LedgerStore(path)
    store.verify()
    report = compute_tppr(store.events(project_id), project_id)
    typer.echo(report.model_dump_json(indent=2))


@tppr_app.command("compute-v2")
def tppr_compute_v2(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    project_id: Annotated[str, typer.Option("--project-id")],
    include_retrospective: Annotated[
        bool,
        typer.Option(
            "--include-retrospective",
            help="Include retrospective estimates in primary TPPR (protocol opt-in).",
        ),
    ] = False,
) -> None:
    """TPPR v2 audit report over typed UtilityEventV2 records (CLOSURE-025)."""
    from lpe.ledger.events import UtilityEventV2
    from lpe.metrics.tppr_v2 import TPPRAntiGamingError, compute_tppr_v2

    store = LedgerStore(path)
    store.verify()
    typed: list[UtilityEventV2] = []
    for event in store.events(project_id):
        try:
            typed.append(UtilityEventV2.model_validate(event.model_dump(mode="json")))
        except Exception:
            # Legacy v1 events: wrap as unresolved for audit counting.
            from lpe.ledger.events import (
                EventTypeV2,
                LegacyUnresolvedPayload,
            )

            typed.append(
                UtilityEventV2(
                    event_id=event.event_id,
                    event_type=EventTypeV2.LEGACY_UNRESOLVED,
                    project_id=event.project_id,
                    artifact_id=event.artifact_id,
                    actor_id=event.actor_id,
                    obligation_ids=([event.obligation_id] if event.obligation_id else []),
                    occurred_at=event.occurred_at,
                    payload=LegacyUnresolvedPayload(
                        legacy_event_type=event.event_type.value,
                        legacy_payload=dict(event.payload),
                    ),
                )
            )
    try:
        report = compute_tppr_v2(
            typed,
            project_id,
            include_retrospective_in_primary=include_retrospective,
        )
    except TPPRAntiGamingError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
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
    packet: Annotated[
        Path | None,
        typer.Option(
            "--packet",
            exists=True,
            dir_okay=False,
            help=(
                "Optional evidence packet JSON; cross-links evidence_fingerprint "
                "into the ledger review payload."
            ),
        ),
    ] = None,
) -> None:
    from lpe.models import EvidencePacket, RiskClass

    contract = load_contract(project)
    decision = ReviewDecision.model_validate(_read_json(decision_path))
    risk = RiskClass(risk_class)
    fingerprint: str | None = None
    if packet is not None:
        evidence = EvidencePacket.model_validate(_read_json(packet))
        if evidence.packet_id != decision.packet_id:
            typer.echo(
                "packet_id mismatch between --packet and decision "
                f"({evidence.packet_id!r} vs {decision.packet_id!r})",
                err=True,
            )
            raise typer.Exit(code=1)
        fingerprint = evidence.evidence_fingerprint
    try:
        validate_reviewer_authority(
            contract,
            reviewer_id=decision.reviewer_id,
            reviewer_roles=decision.reviewer_roles,
            risk_class=risk,
        )
        validate_decision_for_risk(decision, risk)
        if decision.decision is ReviewDecisionValue.ACCEPT and not can_record_acceptance(risk):
            raise AuthorityError(
                f"{risk.value} ACCEPT cannot be recorded via lpe review record "
                "(ADR 0003: no R3/R4 auto-accept; single-reviewer ACCEPT refused). "
                "Record dimension attestations with `lpe review attest`, then "
                "`lpe review accept-quorum`."
            )
    except AuthorityError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    obl_list = (
        [part.strip() for part in obligation_ids.split(",") if part.strip()]
        if obligation_ids
        else None
    )
    try:
        digest = record_review_decision(
            ledger,
            decision,
            project_id=contract.project.project_id,
            obligation_ids=obl_list,
            evidence_fingerprint=fingerprint,
            risk_class=risk,
        )
    except AcceptanceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(digest)


@review_app.command("attest")
def review_attest(
    project: Annotated[Path, typer.Option("--project", exists=True, file_okay=False)],
    attestation_path: Annotated[Path, typer.Option("--attestation", exists=True, dir_okay=False)],
    conflict_path: Annotated[Path, typer.Option("--conflict", exists=True, dir_okay=False)],
    ledger: Annotated[Path, typer.Option("--ledger")],
    risk_class: Annotated[str, typer.Option("--risk-class")],
    obligation_ids: Annotated[
        str | None,
        typer.Option("--obligation-ids", help="Comma-separated obligation ids."),
    ] = None,
) -> None:
    """Record a single-dimension review attestation (eligibility fail-closed)."""
    from lpe.models import RiskClass

    contract = load_contract(project)
    attestation = ReviewAttestationV2.model_validate(_read_json(attestation_path))
    conflict = ReviewerConflictDeclaration.model_validate(_read_json(conflict_path))
    risk = RiskClass(risk_class)
    try:
        if conflict.reviewer_id != attestation.reviewer_id:
            raise ConflictError("conflict reviewer_id must match attestation reviewer_id")
        conflict_hash = require_eligible_for_primary_attestation(conflict)
        if attestation.conflict_declaration_hash != conflict_hash:
            raise ConflictError("attestation conflict_declaration_hash does not match declaration")
        validate_reviewer_authority(
            contract,
            reviewer_id=attestation.reviewer_id,
            risk_class=risk,
        )
    except (AuthorityError, ConflictError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    store = LedgerStore(ledger)
    if not ledger.exists():
        store.initialize()
    obl_list = (
        [part.strip() for part in obligation_ids.split(",") if part.strip()]
        if obligation_ids
        else None
    )
    try:
        digest = record_attestation_event(
            store,
            attestation,
            project_id=contract.project.project_id,
            obligation_ids=obl_list,
        )
    except Exception as exc:  # lifecycle / integrity
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(digest)


@review_app.command("accept-quorum")
def review_accept_quorum(
    project: Annotated[Path, typer.Option("--project", exists=True, file_okay=False)],
    attestations_path: Annotated[
        Path,
        typer.Option(
            "--attestations",
            exists=True,
            dir_okay=False,
            help="JSON array of ReviewAttestationV2 objects",
        ),
    ],
    ledger: Annotated[Path, typer.Option("--ledger")],
    risk_class: Annotated[str, typer.Option("--risk-class")],
    evidence_fingerprint: Annotated[str, typer.Option("--evidence-fingerprint")],
    actor_id: Annotated[str, typer.Option("--actor-id")],
    artifact_id: Annotated[str, typer.Option("--artifact-id")],
    obligation_ids: Annotated[
        str | None,
        typer.Option("--obligation-ids", help="Comma-separated obligation ids."),
    ] = None,
) -> None:
    """Aggregate ARTIFACT_ACCEPTED only when R1-R4 quorum is satisfied.

    R3/R4 require distinct reviewers; auto-accept remains impossible (ADR 0003).
    """
    from lpe.models import RiskClass

    contract = load_contract(project)
    raw = _read_json(attestations_path)
    if not isinstance(raw, list):
        typer.echo("--attestations must be a JSON array", err=True)
        raise typer.Exit(code=1)
    attestations = [ReviewAttestationV2.model_validate(item) for item in raw]
    risk = RiskClass(risk_class)
    obl_list = (
        [part.strip() for part in obligation_ids.split(",") if part.strip()]
        if obligation_ids
        else None
    )
    try:
        digest = aggregate_and_record_acceptance(
            ledger,
            project_id=contract.project.project_id,
            artifact_id=artifact_id,
            actor_id=actor_id,
            risk_class=risk,
            attestations=attestations,
            evidence_fingerprint=evidence_fingerprint,
            obligation_ids=obl_list,
        )
    except AcceptanceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(digest)


@review_app.command("repair-lineage")
def review_repair_lineage(
    prior_candidate_id: Annotated[str, typer.Option("--prior-candidate-id")],
    repair_request_ids: Annotated[
        str,
        typer.Option(
            "--repair-request-ids",
            help="Comma-separated repair request ids (at least one).",
        ),
    ],
    applied_change: Annotated[
        Path,
        typer.Option(
            "--applied-change",
            exists=True,
            dir_okay=False,
            help="File whose contents are hashed as the applied repair change.",
        ),
    ],
    new_evidence_fingerprint: Annotated[
        str | None,
        typer.Option("--new-evidence-fingerprint"),
    ] = None,
) -> None:
    """Compute the next repair candidate id and lineage JSON (CLOSURE-024)."""
    req_ids = [part.strip() for part in repair_request_ids.split(",") if part.strip()]
    try:
        lineage = build_repair_lineage(
            prior_candidate_id=prior_candidate_id,
            repair_request_ids=req_ids,
            applied_change=applied_change.read_bytes(),
            new_evidence_fingerprint=new_evidence_fingerprint,
        )
    except RepairError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                "root_candidate_id": lineage.root_candidate_id,
                "prior_candidate_id": lineage.prior_candidate_id,
                "new_candidate_id": lineage.new_candidate_id,
                "repair_sequence": lineage.repair_sequence,
                "repair_request_ids": list(lineage.repair_request_ids),
                "applied_change_hash": lineage.applied_change_hash,
                "new_evidence_fingerprint": lineage.new_evidence_fingerprint,
                "note": "Prior attestations do not transfer to the repaired candidate.",
            },
            indent=2,
        )
    )


@review_app.command("repair-request")
def review_repair_request(
    project: Annotated[Path, typer.Option("--project", exists=True, file_okay=False)],
    ledger: Annotated[Path, typer.Option("--ledger")],
    artifact_id: Annotated[str, typer.Option("--artifact-id")],
    actor_id: Annotated[str, typer.Option("--actor-id")],
    candidate_id: Annotated[str, typer.Option("--candidate-id")],
    rationale: Annotated[str, typer.Option("--rationale")],
    attestations_path: Annotated[
        Path,
        typer.Option(
            "--attestations",
            exists=True,
            dir_okay=False,
            help="JSON array of ReviewAttestationV2 that requested repair.",
        ),
    ],
    repair_request_id: Annotated[
        str | None,
        typer.Option("--repair-request-id", help="Defaults to a generated id."),
    ] = None,
    required_change: Annotated[str | None, typer.Option("--required-change")] = None,
    obligation_ids: Annotated[
        str | None,
        typer.Option("--obligation-ids", help="Comma-separated obligation ids."),
    ] = None,
) -> None:
    """Append a typed REPAIR_REQUESTED ledger event (CLOSURE-024)."""
    contract = load_contract(project)
    raw = _read_json(attestations_path)
    if not isinstance(raw, list):
        typer.echo("--attestations must be a JSON array", err=True)
        raise typer.Exit(code=1)
    attestations = [ReviewAttestationV2.model_validate(item) for item in raw]
    store = LedgerStore(ledger)
    if not ledger.exists():
        store.initialize()
    obl_list = (
        [part.strip() for part in obligation_ids.split(",") if part.strip()]
        if obligation_ids
        else None
    )
    rid = repair_request_id or new_id("repair")
    event = repair_requested_event(
        event_id=new_id("evt"),
        project_id=contract.project.project_id,
        artifact_id=artifact_id,
        actor_id=actor_id,
        repair_request_id=rid,
        candidate_id=candidate_id,
        attestations=attestations,
        rationale=rationale,
        required_change=required_change,
        obligation_ids=obl_list,
    )
    try:
        digest = store.append_v2(event)
    except (LedgerTransitionError, LedgerIntegrityError, LedgerAuthError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                "event_hash": digest,
                "repair_request_id": rid,
                "event_id": event.event_id,
            },
            indent=2,
        )
    )


@review_app.command("repair-complete")
def review_repair_complete(
    project: Annotated[Path, typer.Option("--project", exists=True, file_okay=False)],
    ledger: Annotated[Path, typer.Option("--ledger")],
    artifact_id: Annotated[str, typer.Option("--artifact-id")],
    actor_id: Annotated[str, typer.Option("--actor-id")],
    prior_candidate_id: Annotated[str, typer.Option("--prior-candidate-id")],
    repair_request_ids: Annotated[
        str,
        typer.Option("--repair-request-ids", help="Comma-separated repair request ids."),
    ],
    applied_change: Annotated[
        Path,
        typer.Option("--applied-change", exists=True, dir_okay=False),
    ],
    new_evidence_fingerprint: Annotated[
        str | None,
        typer.Option("--new-evidence-fingerprint"),
    ] = None,
    obligation_ids: Annotated[
        str | None,
        typer.Option("--obligation-ids"),
    ] = None,
) -> None:
    """Append REPAIR_COMPLETED and emit the new candidate lineage (CLOSURE-024)."""
    contract = load_contract(project)
    req_ids = [part.strip() for part in repair_request_ids.split(",") if part.strip()]
    try:
        lineage = build_repair_lineage(
            prior_candidate_id=prior_candidate_id,
            repair_request_ids=req_ids,
            applied_change=applied_change.read_bytes(),
            new_evidence_fingerprint=new_evidence_fingerprint,
        )
    except RepairError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    store = LedgerStore(ledger)
    if not ledger.exists():
        store.initialize()
    obl_list = (
        [part.strip() for part in obligation_ids.split(",") if part.strip()]
        if obligation_ids
        else None
    )
    event = repair_completed_event(
        event_id=new_id("evt"),
        project_id=contract.project.project_id,
        artifact_id=artifact_id,
        actor_id=actor_id,
        lineage=lineage,
        obligation_ids=obl_list,
    )
    try:
        digest = store.append_v2(event)
    except (LedgerTransitionError, LedgerIntegrityError, LedgerAuthError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                "event_hash": digest,
                "new_candidate_id": lineage.new_candidate_id,
                "prior_candidate_id": lineage.prior_candidate_id,
                "applied_change_hash": lineage.applied_change_hash,
                "attestations_transfer": False,
            },
            indent=2,
        )
    )


@review_app.command("adjudicate")
def review_adjudicate(
    project: Annotated[Path, typer.Option("--project", exists=True, file_okay=False)],
    provisional_path: Annotated[
        Path,
        typer.Option("--provisional", exists=True, dir_okay=False),
    ],
    record_path: Annotated[
        Path,
        typer.Option("--record", exists=True, dir_okay=False),
    ],
    peer_attestations_path: Annotated[
        Path,
        typer.Option("--peer-attestations", exists=True, dir_okay=False),
    ],
    conflict_path: Annotated[
        Path,
        typer.Option("--conflict", exists=True, dir_okay=False),
    ],
    original_reviewer_ids: Annotated[
        str,
        typer.Option(
            "--original-reviewer-ids",
            help="Comma-separated original reviewer ids (adjudicator must not be among them).",
        ),
    ],
    review_minutes: Annotated[float, typer.Option("--review-minutes")],
    adjudicator_roles: Annotated[
        str,
        typer.Option(
            "--adjudicator-roles",
            help=f"Comma-separated roles; must include {ADJUDICATOR_ROLE}.",
        ),
    ] = ADJUDICATOR_ROLE,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write adjudication attestation JSON here."),
    ] = None,
) -> None:
    """Validate adjudication lineage and emit an ADJUDICATION attestation (CLOSURE-024)."""
    load_contract(project)  # ensure project loads; authority checked via roles
    provisional = ProvisionalJudgment.model_validate(_read_json(provisional_path))
    record = AdjudicationRecord.model_validate(_read_json(record_path))
    peers_raw = _read_json(peer_attestations_path)
    if not isinstance(peers_raw, list):
        typer.echo("--peer-attestations must be a JSON array", err=True)
        raise typer.Exit(code=1)
    peers = [ReviewAttestationV2.model_validate(item) for item in peers_raw]
    conflict = ReviewerConflictDeclaration.model_validate(_read_json(conflict_path))
    roles = [part.strip() for part in adjudicator_roles.split(",") if part.strip()]
    originals = [part.strip() for part in original_reviewer_ids.split(",") if part.strip()]
    try:
        if conflict.reviewer_id != record.adjudicator_id:
            raise AdjudicationError(
                "conflict reviewer_id must match adjudication record adjudicator_id"
            )
        conflict_hash = validate_adjudicator(
            adjudicator_id=record.adjudicator_id,
            adjudicator_roles=roles,
            original_reviewer_ids=originals,
            conflict=conflict,
        )
        if record.conflict_declaration_hash != conflict_hash:
            raise AdjudicationError("record conflict_declaration_hash does not match declaration")
        if provisional.judgment_id != record.provisional_judgment_id:
            raise AdjudicationError("provisional judgment id mismatch with record")
        revealed = reveal_peer_attestations(provisional, peers)
        lineage = auditable_lineage(
            provisional=revealed,
            record=record,
            peer_attestations=peers,
        )
        attestation = build_adjudication_attestation(
            record,
            review_minutes=review_minutes,
        )
    except AdjudicationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    payload = {
        "lineage": lineage,
        "attestation": attestation.model_dump(mode="json"),
    }
    text = json.dumps(payload, indent=2)
    if output is not None:
        output.write_text(text + "\n", encoding="utf-8")
    typer.echo(text)


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
        "extraction_schema_version": getattr(result, "extraction_schema_version", "1.0"),
        "declaration_count": len(result.declarations),
        "declaration_edge_count": len(result.effective_declaration_edges()),
        "import_edge_count": len(result.import_edges),
        "errors": result.errors,
        "notes": result.notes,
        "artifact": str((repo / ".lpe" / "lean-extraction.json").resolve()),
        "mathlib_scale": False,
        "note": ("not Mathlib-scale; toolchain completeness is project/fixture scope only"),
    }
    typer.echo(json.dumps(summary, indent=2))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        typer.echo(str(output))
    if result.errors and not result.complete:
        raise typer.Exit(code=1)


@lean_app.command("status")
def lean_status(
    repo: Annotated[
        Path | None,
        typer.Option(
            "--repo",
            exists=True,
            file_okay=False,
            help="Optional Lean repo for artifact detection.",
        ),
    ] = None,
) -> None:
    """Print extractor mode (toolchain vs regex-stub) and Mathlib-scale warning."""
    from lpe.honesty.lean_status import lean_extractor_status

    status = lean_extractor_status(repo)
    typer.echo(json.dumps(status, indent=2))
    for warning in status.get("warnings") or []:
        typer.echo(f"warning: {warning}", err=True)


@research_app.command("status")
def research_status(
    format: Annotated[
        str,
        typer.Option("--format", help="json | markdown | text"),
    ] = "json",
) -> None:
    """Print the M6-M7 / EPIC-039/040 / section 21 research gate matrix."""
    from lpe.honesty.research_gates import (
        format_research_status,
        research_status_payload,
    )

    fmt = format.strip().lower()
    if fmt == "json":
        typer.echo(json.dumps(research_status_payload(), indent=2))
    elif fmt == "markdown":
        typer.echo(format_research_status(as_markdown=True))
    elif fmt == "text":
        typer.echo(format_research_status(as_markdown=False))
    else:
        typer.echo(f"unknown --format {format!r}", err=True)
        raise typer.Exit(code=1)


@routing_app.callback(invoke_without_command=True)
def routing_blocked(
    ctx: typer.Context,
) -> None:
    """EPIC-039 blocked until §21 — no learned routing CLI."""
    from lpe.honesty.research_gates import ResearchGateBlocked, refuse_research_entrypoint

    # Allow `--help` without failing.
    if ctx.invoked_subcommand is not None:
        return
    try:
        refuse_research_entrypoint("routing")
    except ResearchGateBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@routing_app.command("train")
def routing_train() -> None:
    """Blocked: M6 training does not exist until §21."""
    from lpe.honesty.research_gates import ResearchGateBlocked, refuse_research_entrypoint

    try:
        refuse_research_entrypoint("routing.train")
    except ResearchGateBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@research_app.command("train")
def research_train() -> None:
    """Blocked: no M6/M7 training entrypoint until §21."""
    from lpe.honesty.research_gates import ResearchGateBlocked, refuse_research_entrypoint

    try:
        refuse_research_entrypoint("train")
    except ResearchGateBlocked as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@research_app.command("evaluate-gates")
def research_evaluate_gates(
    protocol: Annotated[
        Path,
        typer.Option("--protocol", exists=True, help="Protocol bundle dir or protocol.yaml"),
    ],
    ledger: Annotated[Path, typer.Option("--ledger", exists=True, dir_okay=False)],
    seal: Annotated[Path, typer.Option("--seal", exists=True, dir_okay=False)],
    analysis: Annotated[Path, typer.Option("--analysis", exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", help="section21-gates.json path")],
    observables: Annotated[
        Path | None,
        typer.Option(
            "--observables",
            exists=True,
            dir_okay=False,
            help="Optional JSON with overhead/comprehension/sufficiency fields",
        ),
    ] = None,
) -> None:
    """Fail-closed §21 shadow-pilot gate evaluator (CLOSURE-030)."""
    from lpe.honesty.research_gates import evaluate_gates_from_paths

    try:
        report = evaluate_gates_from_paths(
            protocol_path=protocol,
            ledger_path=ledger,
            seal_path=seal,
            analysis_path=analysis,
            output_path=output,
            observables_path=observables,
        )
    except Exception as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "output": str(output),
                "shadow_pilot_passed": report.shadow_pilot_passed,
                "learned_routing_authorized": report.learned_routing_authorized,
                "synthesis_authorized": report.synthesis_authorized,
                "blocking_reasons": report.blocking_reasons,
                "report_hash": report.report_hash,
            },
            indent=2,
        )
    )
    if not report.shadow_pilot_passed:
        raise typer.Exit(code=2)


@pilot_app.command("protocol-init")
def pilot_protocol_init(
    root: Annotated[Path, typer.Argument(help="Directory for pilot-protocol/")],
    project_id: Annotated[str, typer.Option("--project-id")] = "example-partner",
) -> None:
    """Write a complete non-blank example protocol bundle (synthetic; not a live study)."""
    from lpe.pilot.protocol import write_example_bundle

    path = write_example_bundle(root, project_id=project_id)
    typer.echo(json.dumps({"ok": True, "root": str(path), "live_partner": False}, indent=2))


@pilot_app.command("protocol-validate")
def pilot_protocol_validate(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
) -> None:
    """Validate every protocol file; refuse blanks."""
    from lpe.pilot.protocol import ProtocolError, validate_bundle_dir

    try:
        bundle = validate_bundle_dir(root)
    except ProtocolError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "protocol_id": bundle.protocol.protocol_id,
                "protocol_hash": bundle.protocol_hash,
                "component_hashes": bundle.component_hashes,
            },
            indent=2,
        )
    )


@pilot_app.command("comprehension-score")
def pilot_comprehension_score(
    protocol_root: Annotated[Path, typer.Option("--protocol", exists=True, file_okay=False)],
    cases_path: Annotated[Path, typer.Option("--cases", exists=True, dir_okay=False)],
    attempt_path: Annotated[Path, typer.Option("--attempt", exists=True, dir_okay=False)],
    reviewer_id: Annotated[str, typer.Option("--reviewer-id")],
    output: Annotated[Path, typer.Option("--output")],
    prior_failures: Annotated[int, typer.Option("--prior-failures")] = 0,
) -> None:
    """Score one reviewer comprehension attempt (CLOSURE-028)."""
    from lpe.pilot.comprehension import (
        CalibrationCase,
        ComprehensionAttempt,
        ComprehensionError,
        score_comprehension,
    )
    from lpe.pilot.protocol import ProtocolError, validate_bundle_dir

    try:
        bundle = validate_bundle_dir(protocol_root)
        cases_raw = _read_json(cases_path)
        attempt_raw = _read_json(attempt_path)
        cases = [CalibrationCase.model_validate(c) for c in cases_raw]
        attempt = ComprehensionAttempt.model_validate(attempt_raw)
        result = score_comprehension(
            reviewer_id=reviewer_id,
            config=bundle.comprehension,
            cases=cases,
            attempt=attempt,
            prior_failures=prior_failures,
        )
    except (ComprehensionError, ProtocolError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "passed": result.passed,
                "excluded_from_primary": result.excluded_from_primary,
                "result_hash": result.result_hash,
                "output": str(output),
            },
            indent=2,
        )
    )


@pilot_app.command("freeze-protocol")
def pilot_freeze_protocol(
    protocol_dir: Annotated[
        Path,
        typer.Option("--protocol-dir", exists=True, file_okay=False),
    ],
) -> None:
    """Validate and freeze a machine-readable pilot protocol bundle."""
    from lpe.pilot.protocol import ProtocolError, freeze_protocol

    try:
        bundle = freeze_protocol(protocol_dir)
    except ProtocolError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "freeze_id": bundle.freeze_id,
                "protocol_id": bundle.protocol.protocol_id,
                "protocol_hash": bundle.protocol_hash,
                "section_21_cleared": False,
                "causal_claims": False,
            },
            indent=2,
        )
    )


@pilot_app.command("assign")
def pilot_assign(
    protocol_dir: Annotated[
        Path,
        typer.Option("--protocol-dir", exists=True, file_okay=False),
    ],
    episodes: Annotated[
        Path,
        typer.Option("--episodes", exists=True, dir_okay=False, help="JSON list of EpisodeSpec"),
    ],
    seed: Annotated[str, typer.Option("--seed", help="Randomization seed plaintext")],
    output: Annotated[Path, typer.Option("--output", help="Assignment manifest JSON")],
) -> None:
    """Deterministic blocked 2:2:1 condition assignment (HMAC-SHA256)."""
    from lpe.pilot.assignment import AssignmentError, EpisodeSpec, assign_conditions
    from lpe.pilot.protocol import ProtocolError, verify_freeze

    try:
        bundle = verify_freeze(protocol_dir)
        raw = _read_json(episodes)
        if not isinstance(raw, list):
            raise AssignmentError("--episodes must be a JSON array")
        specs = [EpisodeSpec.model_validate(item) for item in raw]
        manifest = assign_conditions(
            protocol_id=bundle.protocol.protocol_id,
            config=bundle.assignment,
            episodes=specs,
            roster=bundle.roster,
            seed_plaintext=seed,
        )
    except (ProtocolError, AssignmentError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "assignment_id": manifest.assignment_id,
                "manifest_hash": manifest.manifest_hash,
                "quotas": manifest.quotas,
                "output": str(output),
            },
            indent=2,
        )
    )


@pilot_app.command("lock")
def pilot_lock(
    protocol_dir: Annotated[
        Path,
        typer.Option("--protocol-dir", exists=True, file_okay=False),
    ],
    ledger: Annotated[Path, typer.Option("--ledger", exists=True, dir_okay=False)],
    seal: Annotated[Path, typer.Option("--seal", exists=True, dir_okay=False)],
    assignment: Annotated[
        Path,
        typer.Option("--assignment", exists=True, dir_okay=False),
    ],
    analysis_image_digest: Annotated[str, typer.Option("--analysis-image-digest")],
    expected_episodes: Annotated[
        str,
        typer.Option("--expected-episodes", help="Comma-separated episode IDs"),
    ],
    completed_episodes: Annotated[
        str,
        typer.Option("--completed-episodes", help="Comma-separated episode IDs"),
    ],
    output: Annotated[Path, typer.Option("--output")],
    attestation_complete: Annotated[
        bool,
        typer.Option("--attestation-complete/--attestation-incomplete"),
    ] = False,
    exclusions_resolved: Annotated[
        bool,
        typer.Option("--exclusions-resolved/--exclusions-open"),
    ] = False,
) -> None:
    """Data lock: verify protocol, ledger, seal, held-out, assignment, image."""
    from lpe.pilot.lock import DataLockError, perform_data_lock

    expected = [x.strip() for x in expected_episodes.split(",") if x.strip()]
    completed = [x.strip() for x in completed_episodes.split(",") if x.strip()]
    try:
        record = perform_data_lock(
            protocol_bundle=protocol_dir,
            ledger_path=ledger,
            seal_path=seal,
            assignment_plan_path=assignment,
            analysis_image_digest=analysis_image_digest,
            expected_episode_ids=expected,
            completed_episode_ids=completed,
            attestation_complete=attestation_complete,
            exclusions_resolved=exclusions_resolved,
            output_path=output,
        )
    except DataLockError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(record.model_dump_json(indent=2))


@pilot_app.command("analyze")
def pilot_analyze(
    protocol_id: Annotated[str, typer.Option("--protocol-id")],
    data_lock_hash: Annotated[str, typer.Option("--data-lock-hash")],
    episodes: Annotated[
        Path,
        typer.Option("--episodes", exists=True, dir_okay=False),
    ],
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    """Descriptive pilot analysis (does not claim causal utility)."""
    from lpe.pilot.analysis import AnalysisError, PilotEpisodeRecord, analyze_pilot

    try:
        raw = _read_json(episodes)
        if not isinstance(raw, list):
            raise AnalysisError("--episodes must be a JSON array")
        records = [PilotEpisodeRecord.model_validate(item) for item in raw]
        report = analyze_pilot(
            protocol_id=protocol_id,
            data_lock_hash=data_lock_hash,
            episodes=records,
        )
    except (AnalysisError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "analysis_hash": report.analysis_hash,
                "episode_count": sum(s.count for s in report.by_condition),
                "output": str(output),
                "section_21_cleared": False,
                "causal_claims": False,
            },
            indent=2,
        )
    )


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
            help=("Record kind: candidate | expert-time | packet-automated | overhead | outcome"),
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
                    "--candidate-id, --condition-tag, --category, and --minutes are required"
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
                evidence_fingerprint=extras.get("evidence_fingerprint"),
                packet_id=extras.get("packet_id"),
            )
        elif kind_norm == "overhead":
            base = (
                baseline_minutes if baseline_minutes is not None else extras.get("baseline_minutes")
            )
            inst = (
                instrumented_minutes
                if instrumented_minutes is not None
                else extras.get("instrumented_minutes")
            )
            if base is None or inst is None:
                raise ValueError("--baseline-minutes and --instrumented-minutes are required")
            report = OverheadReport.compute(
                baseline_minutes=float(base),
                instrumented_minutes=float(inst),
            )
            result = warehouse.record_overhead_snapshot(
                artifact_id=str(candidate_id or extras.get("candidate_id") or "pilot-overhead"),
                report=report,
                condition_tag=condition_tag or extras.get("condition_tag"),
                note=extras.get("note"),
            )
        elif kind_norm == "outcome":
            cid = candidate_id or extras.get("candidate_id")
            tag = condition_tag or extras.get("condition_tag")
            dec = decision or extras.get("decision")
            if not cid or not tag or not dec:
                raise ValueError("--candidate-id, --condition-tag, and --decision are required")
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
    claim_section_21: Annotated[
        bool,
        typer.Option(
            "--claim-section-21",
            help=_PILOT_OVERSELL_FLAG_HELP,
            hidden=True,
        ),
    ] = False,
    claim_causal: Annotated[
        bool,
        typer.Option(
            "--claim-causal",
            help=_PILOT_OVERSELL_FLAG_HELP,
            hidden=True,
        ),
    ] = False,
) -> None:
    """Aggregate durable pilot metrics from the utility ledger (not in-memory).

    Always emits a NON_CLAIMS block. Software metrics ≠ causal / §21 clearance.
    """
    from lpe.honesty.non_claims import OversellClaimError, non_claims_payload
    from lpe.pilot.report import (
        render_summary_json,
        render_summary_markdown,
        write_summary_reports,
    )
    from lpe.pilot.summary import summarize_pilot

    _refuse_pilot_oversell_options(
        claim_section_21=claim_section_21,
        claim_causal=claim_causal,
    )

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
    try:
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
            typer.echo(
                json.dumps(
                    {
                        "json": str(json_path),
                        "markdown": str(md_path),
                        "NON_CLAIMS": non_claims_payload(),
                        "section_21_cleared": False,
                        "causal_claims": False,
                    },
                    indent=2,
                )
            )
        else:
            typer.echo(f"unknown --format {format!r}; expected json|markdown|both", err=True)
            raise typer.Exit(code=1)
    except OversellClaimError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


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
    claim_section_21: Annotated[
        bool,
        typer.Option(
            "--claim-section-21",
            help=_PILOT_OVERSELL_FLAG_HELP,
            hidden=True,
        ),
    ] = False,
    claim_causal: Annotated[
        bool,
        typer.Option(
            "--claim-causal",
            help=_PILOT_OVERSELL_FLAG_HELP,
            hidden=True,
        ),
    ] = False,
) -> None:
    """Frozen corpus dry-run: durable warehouse events + summary reports.

    Instrumentation only — does not clear §21 or authorize causal claims.
    Always emits a NON_CLAIMS block (software metrics ≠ causal).
    """
    from lpe.honesty.non_claims import non_claims_payload
    from lpe.pilot.dry_run import run_frozen_corpus_dry_run

    _refuse_pilot_oversell_options(
        claim_section_21=claim_section_21,
        claim_causal=claim_causal,
    )

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
                "NON_CLAIMS": non_claims_payload(),
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
                "Instrumented wall-clock minutes (compile/packet/UI). Not expert review minutes."
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
