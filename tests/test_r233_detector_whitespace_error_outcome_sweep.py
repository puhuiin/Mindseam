# -*- coding: utf-8 -*-
"""Round 233 guards: the last error/outcome truthiness sites strip.

r229 and r232 each closed part of the family. A final grep of
``get("error")`` / ``get("outcome")`` found truthiness still live
in confidence_calibration_error, evidence_ratio, tension_resolution,
thread_management resolution, outcome_reliability, lean-reasoning
delivery, confidence_verification_alignment, thread_abandonment,
error_recovery_depth, and the fusion err_recoverable / thread_evt4
paths.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _row(i, **kw):
    base = {
        "t": i, "next": "build: x", "verified": 0, "open": 0,
        "marker": "DONE", "confidence": "strong",
        "verifier": "pytest", "risk": "low",
        "error": "", "outcome": "", "extra_steps": 0,
    }
    base.update(kw)
    return base


class DetectorWhitespaceErrorOutcomeSweepTests(unittest.TestCase):

    def test_evidence_rate_ignores_whitespace(self):
        # The 0.0-1.0 evidence-producing rate (name is the
        # private-style helper at the evidence_ratio site).
        hist = [_row(i, error="  ", outcome="  ") for i in range(1, 5)]
        run = hist[-3:]
        rate = sum(1 for h in run
                   if h.get("verified", 0) > 0
                   or mindseam._row_outcome(h) or mindseam._row_error(h)
                   ) / float(len(run))
        self.assertEqual(rate, 0.0)

    def test_evidence_rate_still_sees_real(self):
        hist = [_row(i, outcome="ok") for i in range(1, 5)]
        run = hist[-3:]
        rate = sum(1 for h in run
                   if h.get("verified", 0) > 0
                   or mindseam._row_outcome(h) or mindseam._row_error(h)
                   ) / float(len(run))
        self.assertEqual(rate, 1.0)

    def test_tension_resolution_ignores_whitespace_error(self):
        # Real next + no real error vs real error: blanks must not
        # add tension beyond the stall that the repeated next causes.
        blanks = [_row(i, error="   ") for i in range(1, 5)]
        real = [_row(i, error="db: timeout") for i in range(1, 5)]
        self.assertGreaterEqual(
            mindseam.tension_resolution(blanks),
            mindseam.tension_resolution(real))

    def test_thread_management_resolution_ignores_whitespace_outcome(self):
        # Real next, no real outcome → unresolved (0), same as empty
        # outcome. Whitespace outcome must not count as resolved.
        blanks = [_row(i, outcome="  ") for i in range(1, 5)]
        empty = [_row(i, outcome="") for i in range(1, 5)]
        self.assertEqual(mindseam.thread_management(blanks),
                         mindseam.thread_management(empty))
        self.assertEqual(mindseam.thread_management(blanks), 0)

    def test_error_recovery_depth_ignores_whitespace_error(self):
        hist = [_row(i, error="   ") for i in range(1, 7)]
        self.assertEqual(mindseam.error_recovery_depth(hist), 100)

    def test_thread_abandonment_ignores_whitespace_error(self):
        hist = [_row(i, error="  ") for i in range(1, 5)]
        self.assertEqual(mindseam.thread_abandonment(hist), 100)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("detector-whitespace-error-outcome-sweep", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "detector-whitespace-error-outcome-sweep")
        self.assertEqual(entry["since"], "r233")
        self.assertIn("evidence_ratio", entry["summary"])
        self.assertIn("r229", entry["summary"])


if __name__ == "__main__":
    unittest.main()
