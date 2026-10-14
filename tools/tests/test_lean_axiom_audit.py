"""Unit regression tests for fail-closed Lean axiom auditing."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lean_axiom_audit import extract_axioms, validate_axioms  # noqa: E402


class StrictAxiomAuditTests(unittest.TestCase):
    def test_approved_flat_axioms(self) -> None:
        report = "'Pkg.thm' depends on axioms: [propext, Classical.choice, Quot.sound]\n"
        self.assertEqual(validate_axioms(report, "Pkg.thm"),
                         frozenset({"propext", "Classical.choice", "Quot.sound"}))

    def test_approved_multiline_axioms(self) -> None:
        report = "'Pkg.thm' depends on axioms: [propext,\n Classical.choice,\n Quot.sound]\n"
        self.assertEqual(len(validate_axioms(report, "Pkg.thm")), 3)

    def test_rejects_sorry(self) -> None:
        report = "'Pkg.thm' depends on axioms: [propext, sorryAx, Quot.sound]\n"
        with self.assertRaisesRegex(ValueError, "sorryAx"):
            validate_axioms(report, "Pkg.thm")

    def test_rejects_native_bv_axiom_even_if_on_second_line(self) -> None:
        report = (
            "'Pkg.thm' depends on axioms: [propext,\n"
            " Classical.choice,\n"
            " Quot.sound,\n"
            " Pkg.thm._native.bv_decide.ax_1_5]\n"
        )
        with self.assertRaisesRegex(ValueError, "native"):
            validate_axioms(report, "Pkg.thm")

    def test_rejects_unrecognized_custom_axiom(self) -> None:
        report = "'Pkg.thm' depends on axioms: [my_unreviewed_axiom]\n"
        with self.assertRaisesRegex(ValueError, "unapproved"):
            validate_axioms(report, "Pkg.thm")

    def test_fails_if_report_missing(self) -> None:
        with self.assertRaisesRegex(ValueError, "found 0"):
            extract_axioms("unrelated output\n", "Pkg.thm")

    def test_fails_if_report_duplicate(self) -> None:
        text = "'Pkg.thm' depends on axioms: [propext]\n"
        with self.assertRaisesRegex(ValueError, "found 2"):
            extract_axioms(text + text, "Pkg.thm")

    def test_fails_if_output_truncated(self) -> None:
        with self.assertRaisesRegex(ValueError, "unterminated"):
            extract_axioms("'Pkg.thm' depends on axioms: [propext,\n", "Pkg.thm")

    def test_fails_if_output_malformed(self) -> None:
        with self.assertRaisesRegex(ValueError, "malformed"):
            extract_axioms("'Pkg.thm' depends on axioms: [propext, ]", "Pkg.thm")


if __name__ == "__main__":
    unittest.main()
