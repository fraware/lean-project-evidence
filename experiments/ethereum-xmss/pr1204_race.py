"""Reproduce the TOCTOU signing reservation race using actual leanSpec PR #1204.

Pinned PR head: e8f9c29da3c2b725b988ed85dac8dce3d89d0012.
Adapter implements the subset of the database protocol invoked by SigningProtection;
it uses the same signing_records schema and INSERT OR REPLACE as the PR.
This is an instrumented adversarial execution, not an exploit of a running validator.
"""
from contextlib import contextmanager
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from lean_spec.node.validator.signing_protection import SigningProtection
from lean_spec.spec.forks import Slot, ValidatorIndex

SCHEMA = """CREATE TABLE signing_records (
    validator_index INTEGER NOT NULL,
    key_role TEXT NOT NULL,
    last_signed_slot INTEGER NOT NULL,
    PRIMARY KEY (validator_index, key_role)
)"""


class StorageAdapter:
    def __init__(self, path, barrier=None, release_gate=None):
        self.con = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.con.execute("PRAGMA busy_timeout=10000")
        self.barrier = barrier
        self.release_gate = release_gate

    def get_last_signed_slot(self, validator_index, key_role):
        row = self.con.execute(
            "SELECT last_signed_slot FROM signing_records "
            "WHERE validator_index=? AND key_role=?",
            (int(validator_index), key_role),
        ).fetchone()
        if self.barrier:
            self.barrier.wait(timeout=15)
        if self.release_gate:
            if not self.release_gate.wait(timeout=15):
                raise TimeoutError("waiting for higher-slot claim")
        return None if row is None else Slot(row[0])

    def put_last_signed_slot(self, validator_index, key_role, slot):
        self.con.execute(
            "INSERT OR REPLACE INTO signing_records "
            "(validator_index, key_role, last_signed_slot) VALUES (?, ?, ?)",
            (int(validator_index), key_role, int(slot)),
        )

    @contextmanager
    def batch_write(self):
        self.con.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.con.commit()
        except BaseException:
            self.con.rollback()
            raise

    def close(self):
        self.con.close()


class ActualSigningProtectionRace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "reserve.sqlite"
        con = sqlite3.connect(self.path)
        con.execute(SCHEMA)
        con.commit()
        con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_concurrent_claims_same_identity_slot_both_return_success(self):
        barrier = threading.Barrier(2)
        succeeded, errors = [], []

        def run():
            adapter = StorageAdapter(self.path, barrier=barrier)
            try:
                SigningProtection(database=adapter).reserve(
                    ValidatorIndex(0), "proposal", Slot(5)
                )
                succeeded.append(True)
            except BaseException as err:
                errors.append(repr(err))
            finally:
                adapter.close()

        workers = [threading.Thread(target=run) for _ in range(2)]
        for w in workers:
            w.start()
        for w in workers:
            w.join(timeout=20)
        self.assertFalse(any(w.is_alive() for w in workers))
        self.assertEqual(errors, [])
        # Both calls succeeded for the exact same validator-role-slot.
        self.assertEqual(succeeded, [True, True])

    def test_stale_lower_claim_overwrites_higher_claim(self):
        barrier = threading.Barrier(2)
        higher_committed = threading.Event()
        errors = []

        def run(slot):
            adapter = StorageAdapter(
                self.path,
                barrier=barrier,
                release_gate=higher_committed if slot == 5 else None,
            )
            try:
                SigningProtection(database=adapter).reserve(
                    ValidatorIndex(0), "proposal", Slot(slot)
                )
                if slot == 8:
                    higher_committed.set()
            except BaseException as err:
                errors.append(repr(err))
            finally:
                adapter.close()

        workers = [
            threading.Thread(target=run, args=(5,)),
            threading.Thread(target=run, args=(8,)),
        ]
        for w in workers:
            w.start()
        for w in workers:
            w.join(timeout=20)
        self.assertFalse(any(w.is_alive() for w in workers))
        self.assertEqual(errors, [])
        con = sqlite3.connect(self.path)
        row = con.execute("SELECT last_signed_slot FROM signing_records").fetchone()
        con.close()
        self.assertEqual(row, (5,))  # Violates intended monotone high-water mark.


if __name__ == "__main__":
    unittest.main(verbosity=2)
