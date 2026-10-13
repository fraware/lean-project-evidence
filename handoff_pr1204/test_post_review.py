"""Offline process tests for the account-authorized PR #1204 review helper.

All calls to GitHub CLI and curl are replaced by local mock executables.
The tests DO NOT submit any public comments.
"""

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "handoff_pr1204" / "post_review.sh"
NOTE = ROOT / "handoff_pr1204" / "REVIEW_NOTE.md"


class PublishReviewContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        binaries = self.root / "bin"
        binaries.mkdir()

        gh = binaries / "gh"
        gh.write_text(
            "#!/usr/bin/env python3\n"
            + textwrap.dedent(
                """
                import os
                import sys

                argv = sys.argv[1:]
                if argv[:2] == ["auth", "status"]:
                    sys.exit(0)
                if argv[:2] == ["api", "user"]:
                    print(os.environ["MOCK_ACCOUNT"])
                    sys.exit(0)
                if argv[0] == "api" and "pulls/1204" in argv[1]:
                    if argv[-1] == ".head.sha":
                        print(os.environ["MOCK_HEAD"])
                    elif argv[-1] == ".state":
                        print(os.environ["MOCK_STATE"])
                    else:
                        sys.exit(2)
                    sys.exit(0)
                if argv[0] == "api" and "issues/1204/comments" in argv[1]:
                    if os.environ.get("MOCK_COMMENTS_FAIL") == "1":
                        sys.exit(8)
                    print(os.environ.get("MOCK_OLD_REVIEW", ""))
                    sys.exit(0)
                if argv[:2] == ["pr", "comment"]:
                    if argv[2] != "1204" or "--body-file" not in argv:
                        sys.exit(2)
                    body_file = argv[argv.index("--body-file") + 1]
                    with open(body_file, encoding="utf-8") as source:
                        content = source.read()
                    with open(os.environ["MOCK_COMMENT_LOG"], "w", encoding="utf-8") as out:
                        out.write(content)
                    sys.exit(0)
                sys.exit(3)
                """
            )
        )
        curl = binaries / "curl"
        curl.write_text(
            "#!/usr/bin/env python3\n"
            + textwrap.dedent(
                """
                import os
                import shutil
                import sys

                args = sys.argv[1:]
                if "--output" not in args:
                    sys.exit(2)
                destination = args[args.index("--output") + 1]
                shutil.copyfile(os.environ["MOCK_NOTE"], destination)
                if os.environ.get("MOCK_TAMPER") == "1":
                    with open(destination, "a", encoding="utf-8") as f:
                        f.write("tampered\\n")
                """
            )
        )
        for path in (gh, curl):
            path.chmod(0o755)

        self.log = self.root / "posted.md"
        self.env = {
            **os.environ,
            "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
            "MOCK_ACCOUNT": "fraware",
            "MOCK_HEAD": "e8f9c29da3c2b725b988ed85dac8dce3d89d0012",
            "MOCK_STATE": "open",
            "MOCK_NOTE": str(NOTE),
            "MOCK_COMMENT_LOG": str(self.log),
            "MOCK_OLD_REVIEW": "",
        }

    def run_script(self):
        return subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=self.root,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=12,
            check=False,
        )

    def test_correct_evidence_posts_one_comment(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.log.exists())
        self.assertIn("2,964", self.log.read_text())

    def test_wrong_account_fails_before_posting(self):
        self.env["MOCK_ACCOUNT"] = "somebody-else"
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected account", result.stderr)
        self.assertFalse(self.log.exists())

    def test_updated_pr_head_fails_before_posting(self):
        self.env["MOCK_HEAD"] = "deadbeef"
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PR head changed", result.stderr)
        self.assertFalse(self.log.exists())

    def test_closed_pr_fails_before_posting(self):
        self.env["MOCK_STATE"] = "closed"
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no longer open", result.stderr)
        self.assertFalse(self.log.exists())

    def test_matching_comment_fails_closed_without_duplicate(self):
        self.env["MOCK_OLD_REVIEW"] = "fraware-xmss-atomic-review-v1-e8f9c29"
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No duplicate", result.stdout)
        self.assertFalse(self.log.exists())

    def test_comment_history_read_failure_blocks_publication(self):
        self.env["MOCK_COMMENTS_FAIL"] = "1"
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unable to verify existing PR comments", result.stderr)
        self.assertFalse(self.log.exists())

    def test_tampered_review_rejected(self):
        self.env["MOCK_TAMPER"] = "1"
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pinned evidence", result.stderr)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
