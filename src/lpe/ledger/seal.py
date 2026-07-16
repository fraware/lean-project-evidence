"""External seal / snapshot attestation for ledger state.

A seal is a small JSON manifest written *after* a successful chain verify.
It records tip hashes, event count, and an export content hash so silent
SQLite mutation can be detected **if the seal is stored separately or
read-only**. This is not hardware WORM and does not replace append-only
invariants on the live ledger.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpe import __version__
from lpe.hashing import canonical_json, sha256_text
from lpe.ledger.store import LedgerIntegrityError, LedgerStore

SEAL_SCHEMA_VERSION = "1.0"
SEAL_KIND = "lpe.ledger.seal"
SEAL_ENV_KEY = "LPE_LEDGER_SEAL_KEY"

CUSTODY_CONTENT_HASH = "content_hash_only"
CUSTODY_HMAC = "hmac"

_CONTENT_HASH_NOTE = (
    "Seal uses a content hash only (LPE_LEDGER_SEAL_KEY unset). "
    "This is not cryptographic custody: anyone who can rewrite both the "
    "ledger and this seal can forge a matching snapshot. Store the seal "
    "separately or read-only to detect silent SQLite mutation. Not hardware WORM."
)

_HMAC_NOTE = (
    "Seal includes an HMAC over the manifest (LPE_LEDGER_SEAL_KEY set). "
    "HMAC integrity holds only while the key remains secret and the seal "
    "file is compared against a separately protected copy. Not hardware WORM."
)


class LedgerSealError(RuntimeError):
    """Raised when seal write/verify fails closed."""


STORAGE_RECOMMENDATION = (
    "Store the seal separately from the ledger (or read-only / off-host). "
    "Use `lpe ledger seal --seal <path>` to write to an alternate location and "
    "`lpe ledger verify-seal --seal <path>` to verify from that copy. "
    "Co-located writable seals can be rewritten with a forged ledger. Not hardware WORM."
)


def default_seal_path(ledger_path: Path) -> Path:
    """Default seal location: ``<ledger_dir>/.lpe/ledger.seal.json``."""
    return ledger_path.resolve().parent / ".lpe" / "ledger.seal.json"


def is_seal_colocated(ledger_path: Path, seal_path: Path) -> bool:
    """True when the seal path lives under the ledger file's parent directory.

    Default ``.lpe/ledger.seal.json`` next to the DB is colocated. An alternate
    ``--seal`` path outside that tree is treated as separately stored.
    """
    ledger_parent = ledger_path.resolve().parent
    try:
        seal_path.resolve().relative_to(ledger_parent)
    except ValueError:
        return False
    return True


def _seal_key_from_env() -> bytes | None:
    raw = os.environ.get(SEAL_ENV_KEY)
    if raw is None:
        return None
    if not raw.strip():
        raise LedgerSealError(
            f"{SEAL_ENV_KEY} is set but empty; refuse seal (fail closed)"
        )
    return raw.encode("utf-8")


def snapshot_state(store: LedgerStore) -> dict[str, Any]:
    """Recompute seal-relevant ledger state after an implicit verify caller.

    Returns ``event_count``, ``artifact_tips``, ``global_tip``, and
    ``export_content_hash`` matching ``export_jsonl`` byte layout.
    """
    store.initialize()
    artifact_tips: dict[str, str] = {}
    digest = hashlib.sha256()
    event_count = 0
    global_tip: str | None = None

    with store.connect() as connection:
        rows = connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
        for row in rows:
            record = store._row_to_export_record(row)
            line = json.dumps(record, sort_keys=True) + "\n"
            digest.update(line.encode("utf-8"))
            artifact_id = str(row["artifact_id"])
            event_hash = str(row["event_hash"])
            artifact_tips[artifact_id] = event_hash
            global_tip = event_hash
            event_count += 1

    if event_count == 0:
        global_tip_value = sha256_text(canonical_json({"event_count": 0, "tips": {}}))
    else:
        assert global_tip is not None
        global_tip_value = global_tip

    return {
        "event_count": event_count,
        "artifact_tips": dict(sorted(artifact_tips.items())),
        "global_tip": global_tip_value,
        "export_content_hash": digest.hexdigest(),
    }


def _mac_payload(manifest: dict[str, Any]) -> bytes:
    body = {key: value for key, value in manifest.items() if key != "hmac"}
    return canonical_json(body).encode("utf-8")


def _compute_hmac(manifest: dict[str, Any], key: bytes) -> str:
    return hmac.new(key, _mac_payload(manifest), hashlib.sha256).hexdigest()


def build_seal_manifest(
    store: LedgerStore,
    *,
    sealed_at: datetime | None = None,
    tool_version: str | None = None,
    key: bytes | None = None,
) -> dict[str, Any]:
    """Build a seal dict for the current verified ledger state."""
    state = snapshot_state(store)
    when = sealed_at or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    use_key = key if key is not None else _seal_key_from_env()
    custody = CUSTODY_HMAC if use_key is not None else CUSTODY_CONTENT_HASH
    manifest: dict[str, Any] = {
        "schema_version": SEAL_SCHEMA_VERSION,
        "kind": SEAL_KIND,
        "sealed_at": when.isoformat(),
        "tool_version": tool_version or __version__,
        "ledger_path": str(store.path.resolve()),
        "event_count": state["event_count"],
        "artifact_tips": state["artifact_tips"],
        "global_tip": state["global_tip"],
        "export_content_hash": state["export_content_hash"],
        "custody": custody,
        "custody_note": _HMAC_NOTE if custody == CUSTODY_HMAC else _CONTENT_HASH_NOTE,
        "not_worm": True,
    }
    if use_key is not None:
        manifest["hmac"] = _compute_hmac(manifest, use_key)
    return manifest


def write_seal(
    store: LedgerStore,
    seal_path: Path | None = None,
    *,
    tool_version: str | None = None,
) -> dict[str, Any]:
    """Verify the ledger, then write a seal manifest (fail closed)."""
    try:
        store.verify()
    except LedgerIntegrityError as exc:
        raise LedgerSealError(f"refuse seal: ledger verify failed: {exc}") from exc

    path = seal_path or default_seal_path(store.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_seal_manifest(store, tool_version=tool_version)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    colocated = is_seal_colocated(store.path, path)
    return {
        "seal_path": str(path.resolve()),
        "manifest": manifest,
        "colocated": colocated,
        "storage_recommendation": STORAGE_RECOMMENDATION,
    }


def load_seal(seal_path: Path) -> dict[str, Any]:
    if not seal_path.is_file():
        raise LedgerSealError(f"seal file not found: {seal_path}")
    try:
        raw = json.loads(seal_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LedgerSealError(f"seal file is not valid JSON: {seal_path}") from exc
    if not isinstance(raw, dict):
        raise LedgerSealError("seal root must be a JSON object")
    return raw


def verify_seal(
    store: LedgerStore,
    seal_path: Path | None = None,
    *,
    key: bytes | None = None,
) -> dict[str, Any]:
    """Recompute ledger snapshot and compare against the seal (fail closed)."""
    path = seal_path or default_seal_path(store.path)
    sealed = load_seal(path)

    if sealed.get("kind") != SEAL_KIND:
        raise LedgerSealError(
            f"seal kind mismatch: expected {SEAL_KIND!r}, got {sealed.get('kind')!r}"
        )
    if sealed.get("schema_version") != SEAL_SCHEMA_VERSION:
        raise LedgerSealError(
            f"unsupported seal schema_version {sealed.get('schema_version')!r}; "
            f"supported: {SEAL_SCHEMA_VERSION!r}"
        )

    try:
        store.verify()
    except LedgerIntegrityError as exc:
        raise LedgerSealError(f"ledger verify failed during seal check: {exc}") from exc

    state = snapshot_state(store)
    mismatches: list[str] = []
    if sealed.get("event_count") != state["event_count"]:
        mismatches.append(
            f"event_count: seal={sealed.get('event_count')!r} live={state['event_count']!r}"
        )
    if sealed.get("artifact_tips") != state["artifact_tips"]:
        mismatches.append("artifact_tips mismatch")
    if sealed.get("global_tip") != state["global_tip"]:
        mismatches.append(
            f"global_tip: seal={sealed.get('global_tip')!r} live={state['global_tip']!r}"
        )
    if sealed.get("export_content_hash") != state["export_content_hash"]:
        mismatches.append(
            "export_content_hash mismatch "
            f"(seal={sealed.get('export_content_hash')!r} "
            f"live={state['export_content_hash']!r})"
        )
    if mismatches:
        raise LedgerSealError(
            "seal does not match live ledger: " + "; ".join(mismatches)
        )

    custody = sealed.get("custody")
    use_key = key if key is not None else _seal_key_from_env()

    if custody == CUSTODY_HMAC:
        expected_mac = sealed.get("hmac")
        if not isinstance(expected_mac, str) or not expected_mac:
            raise LedgerSealError("seal custody is hmac but hmac field is missing")
        if use_key is None:
            raise LedgerSealError(
                f"seal requires {SEAL_ENV_KEY} to verify HMAC (fail closed)"
            )
        actual_mac = _compute_hmac(sealed, use_key)
        if not hmac.compare_digest(actual_mac, expected_mac):
            raise LedgerSealError("seal HMAC mismatch (key wrong or seal tampered)")
    elif custody == CUSTODY_CONTENT_HASH:
        if sealed.get("hmac"):
            raise LedgerSealError(
                "seal custody is content_hash_only but hmac field is present"
            )
    else:
        raise LedgerSealError(f"unknown seal custody mode: {custody!r}")

    colocated = is_seal_colocated(store.path, path)
    return {
        "ok": True,
        "seal_path": str(path.resolve()),
        "event_count": state["event_count"],
        "custody": custody,
        "not_worm": True,
        "colocated": colocated,
        "storage_recommendation": STORAGE_RECOMMENDATION,
        "custody_note": sealed.get("custody_note")
        or (_HMAC_NOTE if custody == CUSTODY_HMAC else _CONTENT_HASH_NOTE),
    }
