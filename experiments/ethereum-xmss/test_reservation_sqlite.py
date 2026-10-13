"""SQLite schedule reproducer for the reservation pattern in leanSpec PR #1204.

Uses the PR's two-step read-then-write shape and its (validator_index, role)
schema; does not import leanSpec or execute its Python service.
"""
import shutil
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

SCHEMA = """CREATE TABLE signing_records (
    validator_index INTEGER NOT NULL,
    key_role TEXT NOT NULL,
    last_signed_slot INTEGER NOT NULL,
    PRIMARY KEY (validator_index, key_role)
)"""

UPSERT = """INSERT INTO signing_records (validator_index, key_role, last_signed_slot)
VALUES (?, ?, ?)
ON CONFLICT(validator_index, key_role) DO UPDATE SET
    last_signed_slot=excluded.last_signed_slot
WHERE signing_records.last_signed_slot < excluded.last_signed_slot"""

KEY_UPSERT = """INSERT INTO by_key (key_id, last_signed_slot) VALUES (?, ?)
ON CONFLICT(key_id) DO UPDATE SET
    last_signed_slot=excluded.last_signed_slot
WHERE by_key.last_signed_slot < excluded.last_signed_slot"""


def connect(db):
    con = sqlite3.connect(db, isolation_level=None, timeout=10)
    con.execute("PRAGMA busy_timeout = 10000")
    return con


def last(con, identity=(0, "proposal")):
    row = con.execute(
        "SELECT last_signed_slot FROM signing_records WHERE validator_index=? AND key_role=?",
        identity,
    ).fetchone()
    return None if row is None else row[0]


def separate_write(con, slot, identity=(0, "proposal")):
    # Equivalent to the PR's unconditional INSERT OR REPLACE after its separate read.
    con.execute("BEGIN IMMEDIATE")
    try:
        con.execute(
            "INSERT OR REPLACE INTO signing_records "
            "(validator_index, key_role, last_signed_slot) VALUES (?, ?, ?)",
            (*identity, slot),
        )
        con.commit()
    except BaseException:
        con.rollback()
        raise


def claim(con, slot, identity=(0, "proposal")):
    return con.execute(UPSERT, (*identity, slot)).rowcount == 1


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "reserve.db"
        with connect(self.db) as con:
            con.execute(SCHEMA)
            con.execute(
                "CREATE TABLE by_key "
                "(key_id BLOB PRIMARY KEY NOT NULL, last_signed_slot INTEGER NOT NULL)"
            )

    def tearDown(self):
        self.tmp.cleanup()

    def test_separated_read_write_allows_two_claims_same_slot(self):
        barrier = threading.Barrier(2)
        successes, errors = [], []

        def worker():
            con = connect(self.db)
            try:
                previous = last(con)
                barrier.wait(timeout=5)
                if previous is None or previous < 5:
                    separate_write(con, 5)
                    successes.append(True)
            except Exception as e:
                errors.append(e)
            finally:
                con.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)
        self.assertFalse(errors, errors)
        self.assertEqual(successes, [True, True])

    def test_separated_read_write_can_reduce_high_water_mark(self):
        with connect(self.db) as low, connect(self.db) as high:
            self.assertIsNone(last(low))
            self.assertIsNone(last(high))
            separate_write(high, 8)
            separate_write(low, 5)
        with connect(self.db) as con:
            self.assertEqual(last(con), 5)

    def test_atomic_upsert_allows_one_of_two_same_slot_claims(self):
        barrier = threading.Barrier(2)
        decisions, errors = [], []

        def worker():
            con = connect(self.db)
            try:
                barrier.wait(timeout=5)
                decisions.append(claim(con, 5))
            except Exception as e:
                errors.append(e)
            finally:
                con.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)
        self.assertFalse(errors, errors)
        self.assertEqual(sorted(decisions), [False, True])

    def test_atomic_upsert_preserves_high_water(self):
        with connect(self.db) as con:
            self.assertTrue(claim(con, 8))
            self.assertFalse(claim(con, 5))
            self.assertFalse(claim(con, 8))
            self.assertEqual(last(con), 8)

    def test_role_scoped_index_allows_secret_alias(self):
        # This shows a role-alias configuration hazard, not default key generation.
        with connect(self.db) as con:
            self.assertTrue(claim(con, 5, (0, "proposal")))
            self.assertTrue(claim(con, 5, (0, "attestation")))

    def test_canonical_secret_identity_refuses_alias(self):
        key = bytes.fromhex("03" * 32)  # illustrative identity, not a real PRF digest
        with connect(self.db) as con:
            self.assertEqual(con.execute(KEY_UPSERT, (key, 5)).rowcount, 1)
            self.assertEqual(con.execute(KEY_UPSERT, (key, 5)).rowcount, 0)

    def test_atomic_claim_survives_reopen(self):
        with connect(self.db) as con:
            self.assertTrue(claim(con, 5))
        with connect(self.db) as reopened:
            self.assertFalse(claim(reopened, 5))
            self.assertTrue(claim(reopened, 6))

    def test_restoring_stale_backup_reopens_a_committed_slot(self):
        # This is a counterexample to backup rollback safety, not an expected
        # supported operation. A local SQLite file alone cannot prevent it.
        backup = Path(self.tmp.name) / "pre_claim_backup.db"
        shutil.copy2(self.db, backup)

        first = connect(self.db)
        try:
            self.assertTrue(claim(first, 9))
        finally:
            first.close()

        shutil.copy2(backup, self.db)

        reopened = connect(self.db)
        try:
            self.assertTrue(claim(reopened, 9))
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
