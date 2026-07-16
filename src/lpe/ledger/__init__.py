"""Append-only utility ledger and external seal attestation."""

from lpe.ledger.seal import (
    STORAGE_RECOMMENDATION,
    LedgerSealError,
    default_seal_path,
    is_seal_colocated,
    verify_seal,
    write_seal,
)
from lpe.ledger.store import LedgerAuthError, LedgerIntegrityError, LedgerStore

__all__ = [
    "STORAGE_RECOMMENDATION",
    "LedgerAuthError",
    "LedgerIntegrityError",
    "LedgerSealError",
    "LedgerStore",
    "default_seal_path",
    "is_seal_colocated",
    "verify_seal",
    "write_seal",
]
