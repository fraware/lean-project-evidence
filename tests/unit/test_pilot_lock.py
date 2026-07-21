"""Pilot data lock tests (CLOSURE-029) — previously uncovered module."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lpe.hashing import sha256_file, sha256_value
from lpe.ledger.seal import write_seal
from lpe.ledger.store import LedgerStore
from lpe.models import EventType, UtilityEvent
from lpe.pilot.lock import (
    DataLockError,
    DataLockRecord,
    perform_data_lock,
    require_locked_for_analysis,
    require_new_analysis_version_after_correction,
)
from lpe.pilot.protocol import freeze_protocol, write_example_bundle

DIGEST = "sha256:" + ("a" * 64)
NOW = datetime(2026, 7, 21, tzinfo=UTC)


def _seed_ledger(path: Path) -> LedgerStore:
    store = LedgerStore(path)
    store.append(
        UtilityEvent(
            event_id="e1",
            event_type=EventType.CANDIDATE_REGISTERED,
            project_id="project",
            artifact_id="artifact",
            obligation_id="O-01",
            occurred_at=NOW,
            actor_id="tester",
            payload={"seed": True},
        )
    )
    return store


def _assignment_plan(path: Path) -> Path:
    body = {
        "protocol_id": "proto.example.v1",
        "assignments": [{"candidate_id": "c01", "condition": "control"}],
    }
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return path


def test_data_lock_happy_path_off_host_seal(tmp_path: Path) -> None:
    proto = write_example_bundle(tmp_path / "pilot-protocol")
    freeze_protocol(proto)
    assign = _assignment_plan(tmp_path / "assignment.json")
    ledger_dir = tmp_path / "ledger_host"
    ledger_dir.mkdir()
    ledger = ledger_dir / "ledger.sqlite3"
    store = _seed_ledger(ledger)
    # Off-host: seal must not live under the ledger file's parent directory.
    seal_path = tmp_path / "offhost" / "ledger.seal.json"
    seal_path.parent.mkdir()
    write_seal(store, seal_path)

    episodes = ["ep-01", "ep-02"]
    record = perform_data_lock(
        protocol_bundle=proto,
        ledger_path=ledger,
        seal_path=seal_path,
        assignment_plan_path=assign,
        analysis_image_digest=DIGEST,
        expected_episode_ids=episodes,
        completed_episode_ids=episodes,
        attestation_complete=True,
        exclusions_resolved=True,
        locked_at=NOW,
        output_path=tmp_path / "data-lock.json",
    )
    assert record.protocol_hash
    assert record.data_lock_hash
    assert record.analysis_image_digest == DIGEST
    assert (tmp_path / "data-lock.json").is_file()
    loaded = require_locked_for_analysis(tmp_path / "data-lock.json")
    assert loaded.lock_id == record.lock_id


def test_data_lock_refuses_colocated_seal(tmp_path: Path) -> None:
    proto = write_example_bundle(tmp_path / "pilot-protocol")
    freeze_protocol(proto)
    assign = _assignment_plan(tmp_path / "assignment.json")
    ledger = tmp_path / "ledger.sqlite3"
    store = _seed_ledger(ledger)
    result = write_seal(store)  # default colocated under ledger parent
    seal_path = Path(result["seal_path"])

    with pytest.raises(DataLockError, match="co-located"):
        perform_data_lock(
            protocol_bundle=proto,
            ledger_path=ledger,
            seal_path=seal_path,
            assignment_plan_path=assign,
            analysis_image_digest=DIGEST,
            expected_episode_ids=["ep-01"],
            completed_episode_ids=["ep-01"],
            attestation_complete=True,
            exclusions_resolved=True,
        )


def test_data_lock_refuses_incomplete_and_tag_digest(tmp_path: Path) -> None:
    proto = write_example_bundle(tmp_path / "pilot-protocol")
    freeze_protocol(proto)
    assign = _assignment_plan(tmp_path / "assignment.json")
    ledger_dir = tmp_path / "ledger_host"
    ledger_dir.mkdir()
    ledger = ledger_dir / "ledger.sqlite3"
    store = _seed_ledger(ledger)
    seal_path = tmp_path / "offhost" / "seal.json"
    seal_path.parent.mkdir()
    write_seal(store, seal_path)

    with pytest.raises(DataLockError, match="incomplete episodes"):
        perform_data_lock(
            protocol_bundle=proto,
            ledger_path=ledger,
            seal_path=seal_path,
            assignment_plan_path=assign,
            analysis_image_digest=DIGEST,
            expected_episode_ids=["ep-01", "ep-02"],
            completed_episode_ids=["ep-01"],
            attestation_complete=True,
            exclusions_resolved=True,
        )

    with pytest.raises(DataLockError, match="digest"):
        perform_data_lock(
            protocol_bundle=proto,
            ledger_path=ledger,
            seal_path=seal_path,
            assignment_plan_path=assign,
            analysis_image_digest="latest",
            expected_episode_ids=["ep-01"],
            completed_episode_ids=["ep-01"],
            attestation_complete=True,
            exclusions_resolved=True,
        )

    with pytest.raises(DataLockError, match="attestations incomplete"):
        perform_data_lock(
            protocol_bundle=proto,
            ledger_path=ledger,
            seal_path=seal_path,
            assignment_plan_path=assign,
            analysis_image_digest=DIGEST,
            expected_episode_ids=["ep-01"],
            completed_episode_ids=["ep-01"],
            attestation_complete=False,
            exclusions_resolved=True,
        )


def test_data_lock_held_out_mismatch(tmp_path: Path) -> None:
    proto = write_example_bundle(tmp_path / "pilot-protocol")
    freeze_protocol(proto)
    assign = _assignment_plan(tmp_path / "assignment.json")
    ledger_dir = tmp_path / "ledger_host"
    ledger_dir.mkdir()
    ledger = ledger_dir / "ledger.sqlite3"
    store = _seed_ledger(ledger)
    seal_path = tmp_path / "offhost" / "seal.json"
    seal_path.parent.mkdir()
    write_seal(store, seal_path)
    alt_held = tmp_path / "other-held-out.json"
    alt_held.write_text('{"held_out_ids": ["mutated"], "note": "wrong"}\n', encoding="utf-8")

    with pytest.raises(DataLockError, match="held-out"):
        perform_data_lock(
            protocol_bundle=proto,
            ledger_path=ledger,
            seal_path=seal_path,
            assignment_plan_path=assign,
            analysis_image_digest=DIGEST,
            expected_episode_ids=["ep-01"],
            completed_episode_ids=["ep-01"],
            attestation_complete=True,
            exclusions_resolved=True,
            held_out_set_path=alt_held,
        )


def test_require_locked_and_correction_versioning(tmp_path: Path) -> None:
    with pytest.raises(DataLockError, match="missing"):
        require_locked_for_analysis(tmp_path / "nope.json")

    record = DataLockRecord(
        lock_id="lock-test",
        protocol_id="proto",
        protocol_hash=sha256_value({"p": 1}),
        data_lock_hash=sha256_value({"d": 1}),
        ledger_export_hash=sha256_value({"e": 1}),
        seal_hash=sha256_value({"s": 1}),
        held_out_set_hash=sha256_value({"h": 1}),
        analysis_image_digest=DIGEST,
        assignment_plan_hash=sha256_value({"a": 1}),
        exclusions_resolved=True,
        locked_at=NOW,
    )
    assert require_locked_for_analysis(record).lock_id == "lock-test"

    with pytest.raises(DataLockError, match="corrections required"):
        require_new_analysis_version_after_correction(
            record, correction_event_ids=[], new_analysis_version="analysis.v2"
        )
    with pytest.raises(DataLockError, match="must differ"):
        require_new_analysis_version_after_correction(
            record,
            correction_event_ids=["corr-1"],
            new_analysis_version="analysis.v1",
        )
    advanced = require_new_analysis_version_after_correction(
        record,
        correction_event_ids=["corr-1"],
        new_analysis_version="analysis.v2",
    )
    assert advanced["new_analysis_version"] == "analysis.v2"
    assert advanced["prior_data_lock_hash"] == record.data_lock_hash


def test_data_lock_record_rejects_tag_digest() -> None:
    with pytest.raises(ValueError, match="concrete content digest"):
        DataLockRecord(
            lock_id="lock-bad",
            protocol_id="proto",
            protocol_hash="p",
            data_lock_hash="d",
            ledger_export_hash="e",
            seal_hash="s",
            held_out_set_hash="h",
            analysis_image_digest="local",
            assignment_plan_hash="a",
            exclusions_resolved=True,
            locked_at=NOW,
        )


def test_assignment_plan_hash_recorded(tmp_path: Path) -> None:
    proto = write_example_bundle(tmp_path / "pilot-protocol")
    freeze_protocol(proto)
    assign = _assignment_plan(tmp_path / "assignment.json")
    expected_assign_hash = sha256_file(assign)
    ledger_dir = tmp_path / "ledger_host"
    ledger_dir.mkdir()
    ledger = ledger_dir / "ledger.sqlite3"
    store = _seed_ledger(ledger)
    seal_path = tmp_path / "offhost" / "seal.json"
    seal_path.parent.mkdir()
    write_seal(store, seal_path)
    record = perform_data_lock(
        protocol_bundle=proto,
        ledger_path=ledger,
        seal_path=seal_path,
        assignment_plan_path=assign,
        analysis_image_digest=DIGEST,
        expected_episode_ids=["ep-01"],
        completed_episode_ids=["ep-01"],
        attestation_complete=True,
        exclusions_resolved=True,
        locked_at=NOW,
    )
    assert record.assignment_plan_hash == expected_assign_hash
