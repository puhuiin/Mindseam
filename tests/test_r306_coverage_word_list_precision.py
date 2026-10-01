# -*- coding: utf-8 -*-
"""Round 306 guards: COVERAGE word list is precise and the operator
branch accepts ASCII two-char comparisons.

The old list included ordinary-prose words ("all", "line", "file",
"module", ...) so "the line was verified by tests" scanned as COVERED.
The operator branch used [<=] (one character) and missed "n <= 6".
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam
from _controller_helper import invoke_cli


class CoverageWordListPrecisionTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])

    def _ship(self, body):
        import os
        out = os.path.join(self.workspace, "out.txt")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(body)
        return invoke_cli(self.workspace, ["ship", out])

    def test_common_words_no_longer_count_as_coverage(self):
        for phrase in ("verified by tests",
                       "the line was verified by tests",
                       "ok line verified by tests",
                       "verified by tests. see the file.",
                       "verified by tests. all good.",
                       "tested the files",
                       "this line is verified",
                       "verified working"):
            hits = mindseam.CLAIM.search(phrase)
            cov = mindseam.COVERAGE.search(phrase)
            self.assertTrue(hits, phrase)
            self.assertIsNone(cov, phrase)

    def test_ascii_operator_now_matches(self):
        for phrase in ("brute force, n <= 6",
                       "brute force, n >= 1",
                       "brute force, n < 6",
                       "brute force, n ≤ 6",
                       "brute force, n = 6"):
            self.assertTrue(mindseam.COVERAGE.search(phrase), phrase)

    def test_real_coverage_still_counts(self):
        for phrase in ("brute force, n <= 6, including empty and maximum",
                       "proven for all cases",
                       "tested on Windows and Linux",
                       "validated the inputs and samples",
                       "random checks across boundaries"):
            self.assertTrue(mindseam.COVERAGE.search(phrase), phrase)

    def test_ship_fires_on_uncov_claim(self):
        r = self._ship("the line was verified by tests\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("verification covered", r.stdout)

    def test_ship_clean_on_cov_claim(self):
        r = self._ship("brute force, n <= 6, including all cases\n")
        self.assertNotIn("verification covered", r.stdout)

    def test_ship_clean_on_no_claim(self):
        r = self._ship("a normal sentence with no claim\n")
        self.assertNotIn("verification covered", r.stdout)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("coverage-word-list-precision", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "coverage-word-list-precision")
        self.assertEqual(entry["since"], "r306")
        self.assertIn("COVERAGE", entry["summary"])


if __name__ == "__main__":
    unittest.main()
