"""Historical packet load: save packet JSON, reload/validate after simulated time.

Packets are never rewritten (``docs/CONTRACT.md``). This drill
proves that a committed-on-disk evidence packet still validates against the
current ``EvidencePacket`` model and exported JSON Schema after a delay.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from lpe.evidence.compiler import compile_evidence
from lpe.models import CandidateDescriptor, EvidencePacket, SCHEMA_VERSION


@pytest.mark.longevity
def test_historical_packet_reload_validates_after_delay(
    example_project: Path,
    example_candidate: CandidateDescriptor,
    repository_root: Path,
    tmp_path: Path,
) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    assert packet.schema_version == SCHEMA_VERSION

    archive = tmp_path / "historical" / "packet-v0.1.0.json"
    archive.parent.mkdir(parents=True, exist_ok=True)
    raw = json.loads(packet.model_dump_json())
    archive.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Simulate "time passed" without mutating the on-disk artifact.
    time.sleep(0.05)
    reloaded = json.loads(archive.read_text(encoding="utf-8"))

    model = EvidencePacket.model_validate(reloaded)
    assert model.packet_id == packet.packet_id
    assert model.schema_version == SCHEMA_VERSION
    assert model.hard_gate_passed is packet.hard_gate_passed

    schema = json.loads(
        (repository_root / "schemas" / "evidence-packet.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(reloaded)


@pytest.mark.longevity
def test_golden_skip_build_packets_remain_schema_valid(
    example_project: Path,
    repository_root: Path,
    tmp_path: Path,
) -> None:
    """Compile a small matrix, archive, then batch-reload against schema."""
    schema = json.loads(
        (repository_root / "schemas" / "evidence-packet.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    candidates_dir = repository_root / "examples" / "candidates"
    archive_dir = tmp_path / "packet-archive"
    archive_dir.mkdir()

    for path in sorted(candidates_dir.glob("R*.json")):
        candidate = CandidateDescriptor.model_validate(json.loads(path.read_text(encoding="utf-8")))
        packet = compile_evidence(example_project, candidate, skip_build=True)
        out = archive_dir / f"{path.stem}.json"
        out.write_text(packet.model_dump_json(indent=2), encoding="utf-8")

    for archived in sorted(archive_dir.glob("*.json")):
        payload = json.loads(archived.read_text(encoding="utf-8"))
        EvidencePacket.model_validate(payload)
        validator.validate(payload)
