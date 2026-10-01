# -*- coding: utf-8 -*-
"""Round 318 guards: clean_scalar and claim_without_coverage tolerate
malformed values.

clean_scalar crashed on non-strings (in / .strip()); claim_without_coverage
crashed on non-lists and non-string lines.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


class ScalarHelpersTypeGuardTests(unittest.TestCase):

    def test_clean_scalar_nonstring_refused(self):
        for v in (5, [], {}, True, b"x", 3.14):
            val, err = mindseam.clean_scalar(v)
            self.assertIsNone(val)
            self.assertIn("string", err)

    def test_clean_scalar_none_still_no_value(self):
        val, err = mindseam.clean_scalar(None)
        self.assertIsNone(val)
        self.assertIsNone(err)

    def test_clean_scalar_strings_unchanged(self):
        self.assertEqual(mindseam.clean_scalar("ok"), ("ok", None))
        self.assertEqual(mindseam.clean_scalar(""),
                         (None, "must not be empty"))
        self.assertEqual(mindseam.clean_scalar("  "),
                         (None, "must not be empty"))
        self.assertEqual(mindseam.clean_scalar("a\nb"),
                         (None, "must be one line"))
        self.assertEqual(mindseam.clean_scalar("a\rb"),
                         (None, "must be one line"))

    def test_claim_nonlist_returns_none(self):
        self.assertIsNone(mindseam.claim_without_coverage(5))
        self.assertIsNone(mindseam.claim_without_coverage(None))
        self.assertIsNone(mindseam.claim_without_coverage({}))

    def test_claim_nonstring_lines_skipped(self):
        self.assertIsNone(mindseam.claim_without_coverage([1, 2]))
        self.assertIsNone(mindseam.claim_without_coverage([None, []]))

    def test_claim_strings_unchanged(self):
        # An uncovered claim fires; a covered claim does not.
        self.assertEqual(
            mindseam.claim_without_coverage(["verified working"]), 1)
        self.assertIsNone(mindseam.claim_without_coverage(
            ["verified by brute force, n <= 6, including all cases"]))
        self.assertIsNone(mindseam.claim_without_coverage([]))

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("scalar-helpers-type-guard", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "scalar-helpers-type-guard")
        self.assertEqual(entry["since"], "r318")
        self.assertIn("clean_scalar", entry["summary"])


if __name__ == "__main__":
    unittest.main()
