# -*- coding: utf-8 -*-
"""Round 229 guards: detectors strip whitespace-only error/outcome.

r228 added ``_row_next``. The same truthiness shape sat on error
and outcome:

    error="   ", 4 rows  -> error_recovery_speed 0 (unrecovered)
    error="",    4 rows  -> error_recovery_speed 100 (no errors)
    outcome="  ", 4 rows -> outcome_completeness 100 (all documented)
    outcome="",  4 rows  -> outcome_completeness 0 (none documented)

r229 adds ``_row_error`` / ``_row_outcome`` and routes
error_recovery_speed, outcome_completeness, and evidence_weight
through them.
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


class DetectorWhitespaceErrorOutcomeTests(unittest.TestCase):

    def test_helpers_strip(self):
        self.assertEqual(mindseam._row_error({"error": "  e  "}), "e")
        self.assertEqual(mindseam._row_error({"error": "   "}), "")
        self.assertEqual(mindseam._row_outcome({"outcome": " ok "}), "ok")
        self.assertEqual(mindseam._row_outcome({"outcome": "\t"}), "")
        self.assertEqual(mindseam._row_error({}), "")
        self.assertEqual(mindseam._row_outcome({}), "")

    def test_error_recovery_ignores_whitespace_error(self):
        hist = [_row(i, error="   ") for i in range(1, 5)]
        self.assertEqual(mindseam.error_recovery_speed(hist), 100)

    def test_error_recovery_still_sees_real_error(self):
        hist = [_row(i, error="db: timeout") for i in range(1, 5)]
        self.assertLess(mindseam.error_recovery_speed(hist), 100)

    def test_outcome_completeness_ignores_whitespace_outcome(self):
        hist = [_row(i, outcome="  ") for i in range(1, 5)]
        self.assertEqual(mindseam.outcome_completeness(hist), 0)

    def test_outcome_completeness_still_sees_real_outcome(self):
        hist = [_row(i, outcome="ok") for i in range(1, 5)]
        self.assertEqual(mindseam.outcome_completeness(hist), 100)

    def test_evidence_weight_ignores_whitespace_error(self):
        # Blanks are not errors, so the no-error bonus still applies.
        hist = [_row(i, error="  ", verified=1, outcome="ok")
                for i in range(1, 5)]
        w_ws = mindseam.evidence_weight(hist)
        hist_clean = [_row(i, verified=1, outcome="ok")
                      for i in range(1, 5)]
        self.assertEqual(w_ws, mindseam.evidence_weight(hist_clean))

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("detector-whitespace-error-outcome", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "detector-whitespace-error-outcome")
        self.assertEqual(entry["since"], "r229")
        self.assertIn("_row_error", entry["summary"])
        self.assertIn("r228", entry["summary"])


if __name__ == "__main__":
    unittest.main()
