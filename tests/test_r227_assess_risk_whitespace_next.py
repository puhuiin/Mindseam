# -*- coding: utf-8 -*-
"""Round 227 guards: assess_risk strips whitespace-only next.

Probe before the fix:

    empty next (""), 4 rows     -> high, "no next actions"
    whitespace next ("   "), 4 rows -> medium, no "no next" reason

``row.get("next")`` is truthy for ``"   "``, so assess_risk counted
blanks as next actions. history --domains / --grep / --empty already
strip, so the same history reported zero domains. r227 strips in
assess_risk too.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _row(i, nxt, **kw):
    base = {
        "t": i, "next": nxt, "verified": 0, "open": 0,
        "marker": "DONE", "confidence": "strong",
        "verifier": "pytest", "risk": "low",
        "error": "", "outcome": "ok", "extra_steps": 0,
    }
    base.update(kw)
    return base


class AssessRiskWhitespaceNextTests(unittest.TestCase):

    def test_empty_next_still_fires_no_next(self):
        hist = [_row(i, "") for i in range(1, 5)]
        level, reasons = mindseam.assess_risk(hist)
        self.assertEqual(level, "high")
        self.assertTrue(any("no next" in r for r in reasons), reasons)

    def test_whitespace_next_fires_no_next(self):
        hist = [_row(i, "   ") for i in range(1, 5)]
        level, reasons = mindseam.assess_risk(hist)
        self.assertEqual(level, "high")
        self.assertTrue(any("no next" in r for r in reasons), reasons)

    def test_tab_newline_next_fires_no_next(self):
        hist = [_row(i, "\t\n") for i in range(1, 5)]
        level, reasons = mindseam.assess_risk(hist)
        self.assertTrue(any("no next" in r for r in reasons), reasons)

    def test_real_next_still_suppresses_the_reason(self):
        hist = [_row(i, "build: step") for i in range(1, 5)]
        _, reasons = mindseam.assess_risk(hist)
        self.assertFalse(any("no next" in r for r in reasons), reasons)

    def test_mixed_real_and_whitespace_still_has_next(self):
        hist = [_row(1, "build: a"), _row(2, "   "),
                _row(3, "audit: b"), _row(4, " ")]
        _, reasons = mindseam.assess_risk(hist)
        self.assertFalse(any("no next" in r for r in reasons), reasons)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("assess-risk-whitespace-next", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "assess-risk-whitespace-next")
        self.assertEqual(entry["since"], "r227")
        self.assertIn("strip", entry["summary"])
        self.assertIn("no next", entry["summary"])


if __name__ == "__main__":
    unittest.main()
