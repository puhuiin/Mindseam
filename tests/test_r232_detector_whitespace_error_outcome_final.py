# -*- coding: utf-8 -*-
"""Round 232 guards: the remaining error/outcome truthiness sites strip.

r229 fixed error_recovery_speed, outcome_completeness, and
evidence_weight. A grep of ``get("error")`` / ``get("outcome")``
still found truthiness in resolution_rate, knowledge_retention,
risk-error correlation, verification_completion,
error_recovery_depth, error_focus, and the fusion err windows —
whitespace-only error/outcome still counted as events.
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


class DetectorWhitespaceErrorOutcomeFinalTests(unittest.TestCase):

    def test_resolution_rate_ignores_whitespace_outcome(self):
        hist = [_row(i, outcome="  ") for i in range(1, 5)]
        self.assertEqual(mindseam.resolution_rate(hist), 0.0)

    def test_resolution_rate_still_sees_real_outcome(self):
        hist = [_row(i, outcome="ok") for i in range(1, 5)]
        self.assertEqual(mindseam.resolution_rate(hist), 1.0)

    def test_knowledge_retention_ignores_whitespace_error(self):
        hist = [_row(i, error="   ") for i in range(1, 7)]
        self.assertEqual(mindseam.knowledge_retention(hist), 100)

    def test_incomplete_verification_ignores_whitespace_outcome(self):
        # verified>0 with only a whitespace outcome → not complete → 0.
        hist = [_row(i, verified=1, outcome="  ") for i in range(1, 5)]
        self.assertEqual(mindseam.incomplete_verification(hist), 0)

    def test_incomplete_verification_still_sees_real_outcome(self):
        hist = [_row(i, verified=1, outcome="ok") for i in range(1, 5)]
        self.assertEqual(mindseam.incomplete_verification(hist), 100)

    def test_error_focus_ignores_whitespace_error(self):
        hist = [_row(i, error="   ") for i in range(1, 5)]
        self.assertEqual(mindseam.error_focus(hist), 100)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("detector-whitespace-error-outcome-final", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "detector-whitespace-error-outcome-final")
        self.assertEqual(entry["since"], "r232")
        self.assertIn("resolution_rate", entry["summary"])
        self.assertIn("r229", entry["summary"])


if __name__ == "__main__":
    unittest.main()
