"""Offline, no-publication tests of the upstream delivery wrapper."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
ARTIFACTS = [
    "handoff_leanvm_533/README.md",
    "handoff_leanvm_533/REVIEW_NOTE.md",
    "handoff_leanvm_533/both-folds.patch",
    "handoff_leanvm_533/publish_review.sh",
    "handoff_pr1204/CLAIMS.md",
    "handoff_pr1204/README.md",
    "handoff_pr1204/REVIEW_NOTE.md",
    "handoff_pr1204/THREAT_MODEL.md",
    "handoff_pr1204/post_review.sh",
    "handoff_pr1204/pr1204-atomic-reservation.patch",
    "handoff_pr1204/test_post_review.py",
]

class OfflineDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        for rel in ["delivery/ship.sh", *ARTIFACTS]:
            dest = self.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SOURCE / rel, dest)

    def run_action(self, *args):
        return subprocess.run(
            ["bash", "delivery/ship.sh", *args],
            cwd=self.root, capture_output=True, text=True, timeout=15,
        )

    def test_verified_package(self):
        result = self.run_action("verify")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("11 source-pinned", result.stdout)

    def test_default_is_read_only(self):
        result = self.run_action()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No GitHub write", result.stdout)

    def test_tampering_fails_closed(self):
        with (self.root / "handoff_leanvm_533/REVIEW_NOTE.md").open("a") as fh:
            fh.write("\nmodified\n")
        result = self.run_action("verify")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Modified/unverified file", result.stderr)

    def test_unauthorized_action_fails(self):
        result = self.run_action("upload")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown action", result.stderr)

    def test_publish_requires_target(self):
        result = self.run_action("publish")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Select exactly one PR", result.stderr)

    def test_publish_rejects_extra_arguments(self):
        result = self.run_action("publish", "leanvm", "extra")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unexpected argument", result.stderr)

if __name__ == "__main__":
    unittest.main()
