"""Hermetic read-only checks for GitHub identity, head pins and duplicate comments."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
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
    "delivery/ship.sh",
]
FAKE_GH = """#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
if args[:2] == ['auth', 'status']:
    sys.exit(0)
if args[:2] == ['api', 'user']:
    print(os.getenv('TEST_ACCOUNT', 'fraware'))
    sys.exit(0)
if args and args[0] == 'api' and len(args) > 1:
    path = args[1]
    if '/pulls/' in path:
        if args[-1] == '.state':
            print('open')
            sys.exit(0)
        if args[-1] == '.head.sha':
            if '/leanVM/' in path:
                print(os.getenv('TEST_VM_SHA', '4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d'))
            else:
                print('e8f9c29da3c2b725b988ed85dac8dce3d89d0012')
            sys.exit(0)
    if '/issues/533/comments' in path:
        print('<!-- leanvm-pr533-two-folds-reviewed-20261013-v1 -->')
        sys.exit(0)
print('BLOCKED MOCK ACTION', file=sys.stderr)
sys.exit(77)
"""

class GithubReadGuards(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        for rel in FILES:
            dest = self.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dest)
        binary = self.root / "bin"
        binary.mkdir()
        gh = binary / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)
        self.env = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]}

    def run_command(self, *args, extra=None):
        return subprocess.run(["bash", "delivery/ship.sh", *args],
                              cwd=self.root,
                              env={**self.env, **(extra or {})},
                              capture_output=True, text=True, timeout=15)

    def test_status_checks_pinned_heads(self):
        r = self.run_command("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("No review was posted", r.stdout)

    def test_wrong_identity_blocks_before_post(self):
        r = self.run_command("publish", "leanvm", extra={"TEST_ACCOUNT": "another-account"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Expected GitHub account", r.stderr)

    def test_moved_upstream_head_blocks_before_post(self):
        r = self.run_command("publish", "leanvm", extra={"TEST_VM_SHA": "f" * 40})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("moved", r.stderr)

    def test_existing_review_marker_blocks_duplicates(self):
        r = self.run_command("publish", "leanvm")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("No duplicate created", r.stdout)

if __name__ == "__main__":
    unittest.main()
