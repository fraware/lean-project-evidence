"""
Protection against consuming one validator key twice within a slot.

The signature scheme is a stateful one-time signature indexed by slot.
Signing two different messages under the same key and slot opens two positions
in the same hash chains, which is enough to forge a third signature.
`sign` states that obligation but does not enforce it, so the enforcement lives
here: a record of the highest slot each key has signed, checked before signing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from lean_spec.node.storage import Database, SQLiteDatabase
from lean_spec.spec.forks import Slot, ValidatorIndex

logger = logging.getLogger(__name__)

type SigningRole = Literal["attestation", "proposal"]
"""Which of a validator's two keys a signature consumes.

The roles hold separate keys, so a proposal and an attestation in one slot
consume one slot each rather than colliding.
"""


class SigningProtectionError(Exception):
    """Raised when a signature would consume a slot one of the keys already spent."""


@dataclass(slots=True)
class SigningProtection:
    """
    Enforces at most one signature per validator key per slot.

    A file-backed SQLite database with supported full-sync journaling retains
    committed records across ordinary process restarts. In-memory SQLite and
    process-local records have no such persistence. The `is_durable` flag is a
    conservative configuration indicator, not a filesystem power-loss proof.

    Restoring an older database snapshot can reopen a spent slot. Independent
    databases and signers sharing one secret also defeat local reservations.
    Key custody and backup-rollback prevention are operational obligations.
    """

    database: Database | None = None
    """Store for signing records, or None to keep them in this process only."""

    _slots_in_memory: dict[tuple[ValidatorIndex, SigningRole], Slot] = field(default_factory=dict)
    """Records used while no database is configured."""

    @property
    def is_durable(self) -> bool:
        """
        Report whether SQLite configuration supports local restart persistence.

        Returns False for in-memory and unknown storage implementations.
        This property does not certify power-loss survival or backup integrity.
        """
        return (
            isinstance(self.database, SQLiteDatabase)
            and self.database.has_persistent_signing_storage
        )

    def reserve(self, validator_index: ValidatorIndex, role: SigningRole, slot: Slot) -> None:
        """
        Claim a slot for one of a validator's keys, to be called before it signs.

        Raises `SigningProtectionError` when that key already signed this slot or
        a later one. The claim is stored before the caller signs, so an
        interruption in between forfeits the duty rather than the key.
        """
        if self.database is None:
            last_signed = self._slots_in_memory.get((validator_index, role))
            if last_signed is None or slot > last_signed:
                self._slots_in_memory[(validator_index, role)] = slot
                return
        else:
            # Admission and update are one conditional SQLite statement.
            # Commit before signing so a crash forfeits the duty, not the key.
            with self.database.batch_write():
                admitted = self.database.try_reserve_signing_slot(validator_index, role, slot)
            if admitted:
                return
            last_signed = self.last_signed_slot(validator_index, role)

        raise SigningProtectionError(
            f"validator {validator_index} {role} key last signed slot {last_signed}; "
            f"signing slot {slot} would reuse a one-time key"
        )

    def last_signed_slot(self, validator_index: ValidatorIndex, role: SigningRole) -> Slot | None:
        """Return the highest slot this key has signed, or None if it never signed."""
        if self.database is None:
            return self._slots_in_memory.get((validator_index, role))
        return self.database.get_last_signed_slot(validator_index, role)
