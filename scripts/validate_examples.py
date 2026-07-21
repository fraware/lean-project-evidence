from __future__ import annotations

import json
from pathlib import Path

from lpe.contract.loader import load_contract, validate_candidate_obligations
from lpe.models import CandidateDescriptor

ROOT = Path(__file__).resolve().parents[1]
project = ROOT / "examples" / "minimal-project"
contract = load_contract(project)
candidate_path = ROOT / "examples" / "candidates" / "R3-definition-change.json"
candidate = CandidateDescriptor.model_validate(
    json.loads(candidate_path.read_text(encoding="utf-8"))
)
validate_candidate_obligations(contract, candidate.project_id, candidate.obligation_ids)
print(contract.contract_hash)
