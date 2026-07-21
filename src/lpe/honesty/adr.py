"""ADR 0003 (human authority) doctor / check surface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lpe.models import RiskClass
from lpe.review.authority import can_record_acceptance

ADR_0003_PATH = Path("docs/adr/0003-human-authority.md")


def adr_0003_status(*, repository_root: Path | None = None) -> dict[str, Any]:
    """Confirm ADR 0003 enforcement is active (R3/R4 auto-accept refused)."""
    root = repository_root or Path.cwd()
    adr_path = root / ADR_0003_PATH
    r3_ok = can_record_acceptance(RiskClass.R3) is False
    r4_ok = can_record_acceptance(RiskClass.R4) is False
    r0_ok = can_record_acceptance(RiskClass.R0) is True
    active = r3_ok and r4_ok and r0_ok
    return {
        "adr": "0003",
        "title": "Human authority for high-risk semantics",
        "active": active,
        "path": str(ADR_0003_PATH.as_posix()),
        "path_exists": adr_path.is_file(),
        "can_record_acceptance": {
            "R0": can_record_acceptance(RiskClass.R0),
            "R1": can_record_acceptance(RiskClass.R1),
            "R2": can_record_acceptance(RiskClass.R2),
            "R3": can_record_acceptance(RiskClass.R3),
            "R4": can_record_acceptance(RiskClass.R4),
        },
        "enforcement": (
            "lpe review record raises AuthorityError for R3/R4 ACCEPT; "
            "R3/R4 human acceptance only via quorum (lpe review accept-quorum); "
            "auto-accept for R3/R4 remains impossible; "
            "evidence gates force ESCALATE for R3/R4 even when hard checks PASS"
        ),
    }
