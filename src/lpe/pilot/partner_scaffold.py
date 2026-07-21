"""Partner shadow-pilot working-directory scaffold.

Engineering readiness only: creates ledger path, condition tags, report
templates, and protocol pointers. Does **not** freeze analysis plans, clear
§21, authorize causal claims, or grant R3/R4 ACCEPT (ADR 0003).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Canonical pilot condition tags for partner shadow studies.
PARTNER_CONDITION_TAGS: tuple[str, ...] = ("control", "instrumented", "shadow")

SCAFFOLD_VERSION = "partner.scaffold.v1"
ANALYSIS_PLAN_STATUS_UNFROZEN = "UNFROZEN"
REQUIRED_RELATIVE_PATHS: tuple[str, ...] = (
    "README.md",
    "NON_CLAIMS.md",
    "PROTOCOL_LINKS.md",
    "condition_tags.json",
    "analysis_plan.md",
    "scaffold.json",
    "ledger/.gitkeep",
    "overhead/.gitkeep",
    "reports/pilot_report_template.md",
    "reports/field_log_template.md",
)


@dataclass(frozen=True)
class ScaffoldResult:
    """Paths created by ``init_partner_pilot``."""

    root: Path
    ledger_path: Path
    scaffold_version: str = SCAFFOLD_VERSION
    section_21_cleared: bool = False
    causal_claims: bool = False


@dataclass(frozen=True)
class ScaffoldValidation:
    """Result of validating a partner working directory."""

    ok: bool
    root: Path
    missing: tuple[str, ...]
    errors: tuple[str, ...]
    condition_tags: tuple[str, ...]
    analysis_plan_status: str | None
    section_21_cleared: bool = False
    ready_to_instrument: bool = False
    ready_to_claim: bool = False


def _readme(project_id: str, ledger_name: str) -> str:
    return f"""# Partner shadow-pilot working directory

**Status:** Ready to *instrument* — **not** ready to *claim* causal utility or §21 clearance.

- **Project id (suggested):** `{project_id}`
- **Ledger path:** `ledger/{ledger_name}`
  (created empty; first `lpe pilot record` initializes SQLite)
- **Scaffold:** `{SCAFFOLD_VERSION}`

## Quick start

```bash
# Initialize ledger on first append (or create empty file via ledger init)
lpe ledger init ledger/{ledger_name}

# Record a candidate under one of the three condition tags
lpe pilot record --ledger ledger/{ledger_name} --project-id {project_id} \\
  --actor YOUR_OPERATOR_ID --kind candidate --candidate-id C1 \\
  --condition-tag control --obligation-ids O-01

# Record expert *review* minutes (TPPR denominator categories only)
lpe pilot record --ledger ledger/{ledger_name} --project-id {project_id} \\
  --actor YOUR_OPERATOR_ID --kind expert-time --candidate-id C1 \\
  --condition-tag control --category review --minutes 15

# Record *instrumentation wall-clock* overhead separately (not review minutes)
lpe pilot overhead --ledger ledger/{ledger_name} --project-id {project_id} \\
  --actor YOUR_OPERATOR_ID --baseline-minutes 60 --wall-minutes 65 \\
  --note "packet compile + UI wall clock"

# Aggregate software metrics only
lpe pilot summary ledger/{ledger_name} --project-id {project_id} \\
  --format both --output ./reports/out
```

## Required reading

- [docs/24_PARTNER_PILOT_READY.md](../../docs/24_PARTNER_PILOT_READY.md) (from repo root)
- [docs/pilot_study_protocol.md](../../docs/pilot_study_protocol.md)
- [docs/pilot_analysis_plan_template.md](../../docs/pilot_analysis_plan_template.md)
- [docs/pilot_dry_run.md](../../docs/pilot_dry_run.md)
- [docs/adr/0003-human-authority.md](../../docs/adr/0003-human-authority.md)

See `PROTOCOL_LINKS.md` and `NON_CLAIMS.md` in this directory.
"""


def _non_claims() -> str:
    from lpe.honesty.non_claims import NON_CLAIMS_MARKDOWN

    return (
        NON_CLAIMS_MARKDOWN + "\nCopy this block into any external report until the analysis plan "
        "is frozen and domain-lead + research-lead gates clear.\n"
    )


def _protocol_links() -> str:
    return """# Protocol document links

Paths are relative to the **repository root** (not this working directory).

| Document | Path | Role |
| --- | --- | --- |
| Partner readiness checklist | `docs/24_PARTNER_PILOT_READY.md` | Operational go / no-go |
| Study protocol template | `docs/pilot_study_protocol.md` | Shadow-pilot design |
| Analysis plan template | `docs/pilot_analysis_plan_template.md` | Preregistration fields |
| Report template | `docs/pilot_report_template.md` | Software vs causal split |
| Dry-run honesty | `docs/pilot_dry_run.md` | Instrumentation-only dry-run |
| Human authority | `docs/adr/0003-human-authority.md` | No R3/R4 auto-accept |
| Explicit non-claims | `docs/28_NON_CLAIMS.md` | Canonical anti-oversell list |
| Ledger durability | `docs/adr/0004-append-only-ledger.md` | Append-only events |
| Lean image | `docker/lpe-lean/README.md` | `lpe-lean:4.14` sandbox |
| Scientific gate | `docs/ENGINEERING_SPEC.md` §21 | Research clearance (not claimed) |

Validate this scaffold:

```bash
lpe pilot init-partner --validate --dir .
```
"""


def _condition_tags_json() -> str:
    payload = {
        "schema": "partner.condition_tags.v1",
        "section_21_cleared": False,
        "description": (
            "Three review conditions for partner shadow pilots. "
            "Tag every candidate with exactly one condition_tag."
        ),
        "conditions": [
            {
                "tag": "control",
                "label": "Control review",
                "packet_visible_to_reviewer": False,
                "lpe_runs": False,
                "notes": "Usual human review without an LPE evidence packet.",
            },
            {
                "tag": "instrumented",
                "label": "Instrumented review",
                "packet_visible_to_reviewer": True,
                "lpe_runs": True,
                "notes": "Human review with LPE evidence packet visible.",
            },
            {
                "tag": "shadow",
                "label": "Shadow compile",
                "packet_visible_to_reviewer": False,
                "lpe_runs": True,
                "notes": (
                    "LPE compiles a packet for instrumentation/overhead, but the "
                    "reviewer does not see it (shadow mode)."
                ),
            },
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def _analysis_plan_stub(project_id: str) -> str:
    return f"""# Partner analysis plan (working copy)

**Status: {ANALYSIS_PLAN_STATUS_UNFROZEN}**

> Do not treat this file as preregistration until a signed, dated freeze replaces
> `{ANALYSIS_PLAN_STATUS_UNFROZEN}` with `FROZEN` and an archive copy is stored.

Copy fields from `docs/pilot_analysis_plan_template.md` (repository root).

## Identity

- Partner / site:
- Project id: `{project_id}`
- Domain lead:
- Research lead contact:
- Freeze date: _(empty while UNFROZEN)_
- Signature / acknowledgment: _(empty while UNFROZEN)_

## Conditions (must match `condition_tags.json`)

- [ ] `control`
- [ ] `instrumented`
- [ ] `shadow`

## Gates (targets; not yet claimed)

- Packet automation ≥ 80%
- Exact-environment reproduction ≥ 90% (selected cases)
- Instrumentation overhead < 10% of expert time
- Reviewer comprehension (qualitative)

## TPPR proxy

- Primary descriptive metric: TPPR from utility ledger export
- Inferential tests: **none until frozen and approved**

## Exclusions

- `overhead_snapshot` events (wall-clock instrumentation) — excluded from TPPR denominator
- Anonymous actors — fail closed
- R3/R4 ACCEPT via automation — refused (ADR 0003)

## Held-out set

- Definition: _(required before freeze)_
- Size / selection rule: _(required before freeze)_
"""


def _field_log_template() -> str:
    return """# Field log template

Use one row (or ledger append) per candidate. Keep **review minutes** and
**instrumentation wall-clock** in separate columns / commands.

| Date | Candidate | Condition | Obligation IDs | Review minutes |
| Wall overhead baseline | Wall overhead instrumented | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | control / instrumented / shadow | | review / repair / ... | | | |

Commands:

```bash
# Review minutes → TPPR categories
lpe pilot record --kind expert-time --category review --minutes N ...

# Wall-clock instrumentation → overhead_snapshot (not TPPR denominator)
lpe pilot overhead --baseline-minutes B --wall-minutes W ...
```
"""


def init_partner_pilot(
    root: Path,
    *,
    project_id: str = "partner-project",
    ledger_name: str = "partner-pilot.sqlite3",
    force: bool = False,
) -> ScaffoldResult:
    """Create a partner working directory for shadow-pilot instrumentation."""
    root = root.resolve()
    if root.exists() and any(root.iterdir()) and not force:
        raise FileExistsError(
            f"refusing to scaffold non-empty directory {root}; pass force=True "
            "or choose an empty path"
        )
    root.mkdir(parents=True, exist_ok=True)

    ledger_dir = root / "ledger"
    overhead_dir = root / "overhead"
    reports_dir = root / "reports"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    overhead_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    (ledger_dir / ".gitkeep").write_text("", encoding="utf-8")
    (overhead_dir / ".gitkeep").write_text("", encoding="utf-8")

    (root / "README.md").write_text(_readme(project_id, ledger_name), encoding="utf-8")
    (root / "NON_CLAIMS.md").write_text(_non_claims(), encoding="utf-8")
    (root / "PROTOCOL_LINKS.md").write_text(_protocol_links(), encoding="utf-8")
    (root / "condition_tags.json").write_text(_condition_tags_json(), encoding="utf-8")
    (root / "analysis_plan.md").write_text(_analysis_plan_stub(project_id), encoding="utf-8")
    (reports_dir / "field_log_template.md").write_text(_field_log_template(), encoding="utf-8")

    # Prefer copying the canonical report template when the repo layout is known.
    report_src = _find_repo_doc("docs/pilot_report_template.md")
    report_dst = reports_dir / "pilot_report_template.md"
    if report_src is not None:
        report_dst.write_text(report_src.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        report_dst.write_text(
            "# Pilot report template\n\nSee repository `docs/pilot_report_template.md`.\n",
            encoding="utf-8",
        )

    meta = {
        "scaffold_version": SCAFFOLD_VERSION,
        "project_id": project_id,
        "ledger_relative": f"ledger/{ledger_name}",
        "condition_tags": list(PARTNER_CONDITION_TAGS),
        "section_21_cleared": False,
        "causal_claims": False,
        "ready_to_instrument": True,
        "ready_to_claim": False,
        "analysis_plan_status": ANALYSIS_PLAN_STATUS_UNFROZEN,
    }
    (root / "scaffold.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # Do not pre-create an empty .sqlite3 file (invalid DB). First
    # ``lpe ledger init`` / ``lpe pilot record`` creates the store.
    ledger_path = ledger_dir / ledger_name
    return ScaffoldResult(root=root, ledger_path=ledger_path)


def _find_repo_doc(relative: str) -> Path | None:
    """Locate a repo doc when running from a checkout."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / relative
        if candidate.is_file():
            return candidate
    return None


def validate_partner_scaffold(root: Path) -> ScaffoldValidation:
    """Validate that a partner working directory has the expected kit."""
    root = root.resolve()
    missing: list[str] = []
    errors: list[str] = []

    if not root.is_dir():
        return ScaffoldValidation(
            ok=False,
            root=root,
            missing=tuple(REQUIRED_RELATIVE_PATHS),
            errors=(f"not a directory: {root}",),
            condition_tags=(),
            analysis_plan_status=None,
            ready_to_instrument=False,
            ready_to_claim=False,
        )

    for rel in REQUIRED_RELATIVE_PATHS:
        if not (root / rel).exists():
            missing.append(rel)

    tags: list[str] = []
    tags_path = root / "condition_tags.json"
    if tags_path.is_file():
        try:
            data = json.loads(tags_path.read_text(encoding="utf-8"))
            conditions = data.get("conditions") or []
            tags = [str(c.get("tag")) for c in conditions if isinstance(c, dict)]
            for required in PARTNER_CONDITION_TAGS:
                if required not in tags:
                    errors.append(f"condition_tags.json missing tag {required!r}")
            if data.get("section_21_cleared") is True:
                errors.append("condition_tags.json must not claim section_21_cleared=true")
        except (json.JSONDecodeError, TypeError, AttributeError) as exc:
            errors.append(f"condition_tags.json invalid: {exc}")
    else:
        errors.append("condition_tags.json missing")

    plan_status: str | None = None
    plan_path = root / "analysis_plan.md"
    if plan_path.is_file():
        text = plan_path.read_text(encoding="utf-8")
        status_line = next(
            (line.strip() for line in text.splitlines() if line.strip().startswith("**Status:")),
            "",
        )
        if ANALYSIS_PLAN_STATUS_UNFROZEN in status_line:
            plan_status = ANALYSIS_PLAN_STATUS_UNFROZEN
        elif "FROZEN" in status_line:
            plan_status = "FROZEN"
        else:
            errors.append(
                f"analysis_plan.md must declare **Status: {ANALYSIS_PLAN_STATUS_UNFROZEN}** "
                "or **Status: FROZEN**"
            )
            plan_status = None
    else:
        errors.append("analysis_plan.md missing")

    non_claims = root / "NON_CLAIMS.md"
    if non_claims.is_file():
        nc = non_claims.read_text(encoding="utf-8")
        if "§21" not in nc and "section 21" not in nc.lower():
            errors.append("NON_CLAIMS.md should mention §21 non-clearance")
    else:
        errors.append("NON_CLAIMS.md missing")

    ok = not missing and not errors
    return ScaffoldValidation(
        ok=ok,
        root=root,
        missing=tuple(missing),
        errors=tuple(errors),
        condition_tags=tuple(tags),
        analysis_plan_status=plan_status,
        section_21_cleared=False,
        ready_to_instrument=ok,
        ready_to_claim=False,
    )
