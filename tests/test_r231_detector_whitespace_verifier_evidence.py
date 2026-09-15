# -*- coding: utf-8 -*-
"""Round 231 guards: remaining verifier-set and evidence detectors strip.

r230 fixed observations / assess_risk / ship. The verifier-set and
evidence detectors still used truthiness: a whitespace-only verifier
counted as a unique name (verifier_count, diversity), as evidence of
sincerity (verification_sincerity, coverage), and as "has a verifier"
(freshness). Whitespace confidence counted as a tagged step
(confidence_presence). r231 routes them through the r229/r230
helpers.
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
        "verifier": "", "risk": "low",
        "error": "", "outcome": "ok", "extra_steps": 0,
    }
    base.update(kw)
    return base


class DetectorWhitespaceVerifierEvidenceTests(unittest.TestCase):

    def test_verification_depth_ignores_whitespace(self):
        hist = [_row(i, verifier="   ") for i in range(1, 5)]
        self.assertEqual(mindseam.verification_depth(hist), 0)

    def test_verification_depth_still_counts_real(self):
        hist = [_row(i, verifier="pytest") for i in range(1, 5)]
        self.assertEqual(mindseam.verification_depth(hist), 1)

    def test_evidence_weight_ignores_whitespace_verifier(self):
        hist = [_row(i, verifier="  ", verified=1, outcome="ok")
                for i in range(1, 5)]
        w_ws = mindseam.evidence_weight(hist)
        hist_clean = [_row(i, verified=1, outcome="ok")
                      for i in range(1, 5)]
        self.assertEqual(w_ws, mindseam.evidence_weight(hist_clean))

    def test_confidence_presence_ignores_whitespace(self):
        hist = [_row(i, confidence="  ") for i in range(1, 5)]
        self.assertEqual(mindseam.confidence_presence(hist), 0)

    def test_confidence_presence_still_sees_real(self):
        hist = [_row(i, confidence="strong") for i in range(1, 5)]
        self.assertEqual(mindseam.confidence_presence(hist), 100)

    def test_verification_freshness_whitespace_verifier_is_stale(self):
        # No real verifier and no verified → stale, low score.
        hist = [_row(i, verifier="   ") for i in range(1, 5)]
        self.assertLess(mindseam.verification_freshness(hist), 100)

    def test_verification_freshness_real_verifier_is_fresh(self):
        hist = [_row(i, verifier="pytest") for i in range(1, 5)]
        self.assertEqual(mindseam.verification_freshness(hist), 100)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("detector-whitespace-verifier-evidence", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "detector-whitespace-verifier-evidence")
        self.assertEqual(entry["since"], "r231")
        self.assertIn("_row_verifier", entry["summary"])
        self.assertIn("verification_depth", entry["summary"])


if __name__ == "__main__":
    unittest.main()
