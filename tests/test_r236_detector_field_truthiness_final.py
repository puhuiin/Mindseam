# -*- coding: utf-8 -*-
"""Round 236 guards: the last confidence/marker/verifier truthiness sites.

r235 unified the inline strips. This round fixes the remaining
truthiness reads that skipped the strip entirely: convergence
c_first, confidence_volatility, confidence_decay_rate, and the
fusion c / win6-verifier / vt6-marker sites. Whitespace-only tags
no longer count as tagged steps anywhere in the detector layer.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam

SOURCE = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(encoding="utf-8")


def _row(i, **kw):
    base = {
        "t": i, "next": "build: x", "verified": 0, "open": 0,
        "marker": "", "confidence": "", "verifier": "",
        "risk": "low", "error": "", "outcome": "", "extra_steps": 0,
    }
    base.update(kw)
    return base


class DetectorFieldTruthinessFinalTests(unittest.TestCase):

    def test_confidence_volatility_ignores_whitespace(self):
        hist = [_row(i, confidence="  ") for i in range(1, 5)]
        self.assertEqual(mindseam.confidence_volatility(hist), 0)

    def test_confidence_volatility_still_sees_changes(self):
        hist = [_row(1, confidence="strong"),
                _row(2, confidence="thin"),
                _row(3, confidence="shaky")]
        self.assertGreater(mindseam.confidence_volatility(hist), 0)

    def test_confidence_decay_rate_ignores_whitespace(self):
        hist = [_row(i, confidence="   ") for i in range(1, 5)]
        self.assertEqual(mindseam.confidence_decay_rate(hist), 0.0)

    def test_no_truthiness_confidence_without_helper_in_detectors(self):
        # Flag lines that do `c = h.get("confidence")` then `if c:`
        # without going through _row_confidence. Exact-equality
        # uses after a stripped assignment are fine.
        offenders = []
        lines = SOURCE.splitlines()
        for i, line in enumerate(lines):
            if ('= h.get("confidence")' in line
                    and "_row_confidence" not in line
                    and not line.strip().startswith("#")):
                # Look ahead for a bare truthiness check
                window = "\n".join(lines[i:i + 3])
                if "if c:" in window or "if c " in window:
                    offenders.append(line.strip())
        self.assertEqual(offenders, [], offenders)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("detector-field-truthiness-final", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "detector-field-truthiness-final")
        self.assertEqual(entry["since"], "r236")
        self.assertIn("confidence_volatility", entry["summary"])
        self.assertIn("detector layer", entry["summary"])


if __name__ == "__main__":
    unittest.main()
