from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lpe.ledger.events import UtilityEventV2
from lpe.models import (
    SCHEMA_VERSION,
    CandidateDescriptor,
    EvidencePacket,
    FixtureSuite,
    ObligationsFile,
    PoliciesFile,
    ProjectConfig,
    ProjectContract,
    ReviewDecision,
    ReviewFile,
    SuccessorSuite,
    TerminologyFile,
    TPPRReport,
    UtilityEvent,
)
from lpe.review.conflicts import ReviewerConflictDeclaration
from lpe.review.models import ReviewAttestationV2

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = {
    "project-config.schema.json": ProjectConfig,
    "terminology.schema.json": TerminologyFile,
    "obligations.schema.json": ObligationsFile,
    "policies.schema.json": PoliciesFile,
    "review.schema.json": ReviewFile,
    "project-contract.schema.json": ProjectContract,
    "candidate.schema.json": CandidateDescriptor,
    "evidence-packet.schema.json": EvidencePacket,
    "review-decision.schema.json": ReviewDecision,
    "review-attestation.schema.json": ReviewAttestationV2,
    "reviewer-conflict.schema.json": ReviewerConflictDeclaration,
    "utility-event.schema.json": UtilityEvent,
    "utility-event-v2.schema.json": UtilityEventV2,
    "tppr-report.schema.json": TPPRReport,
    "fixture-suite.schema.json": FixtureSuite,
    "successor-suite.schema.json": SuccessorSuite,
}


def _render(filename: str, model: type) -> str:
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://schemas.example.org/lpe/{SCHEMA_VERSION}/{filename}"
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export or check LPE JSON schemas")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if on-disk schemas differ from models (schema drift CI)",
    )
    args = parser.parse_args(argv)
    drift: list[str] = []
    for filename, model in SCHEMAS.items():
        rendered = _render(filename, model)
        path = ROOT / "schemas" / filename
        if args.check:
            if not path.is_file():
                drift.append(f"missing: {filename}")
                continue
            existing = path.read_text(encoding="utf-8")
            if existing != rendered:
                drift.append(f"drift: {filename}")
        else:
            path.write_text(rendered, encoding="utf-8")
    if args.check and drift:
        print("schema drift detected:", file=sys.stderr)
        for item in drift:
            print(f"  - {item}", file=sys.stderr)
        print("run: python scripts/export_schemas.py", file=sys.stderr)
        return 1
    if args.check:
        print(f"schemas ok ({len(SCHEMAS)} files, version {SCHEMA_VERSION})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
