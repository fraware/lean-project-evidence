from __future__ import annotations

import json
from pathlib import Path

from lpe.models import (
    CandidateDescriptor,
    EvidencePacket,
    ObligationsFile,
    PoliciesFile,
    ProjectConfig,
    ProjectContract,
    ReviewDecision,
    ReviewFile,
    TPPRReport,
    TerminologyFile,
    UtilityEvent,
)

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
    "utility-event.schema.json": UtilityEvent,
    "tppr-report.schema.json": TPPRReport,
}

for filename, model in SCHEMAS.items():
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://schemas.example.org/lpe/0.1.0/{filename}"
    (ROOT / "schemas" / filename).write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
