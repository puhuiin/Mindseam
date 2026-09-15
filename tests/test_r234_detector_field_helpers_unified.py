# -*- coding: utf-8 -*-
"""Round 234 guards: field helpers unified across every free-text read.

r233 closed the truthiness family. This round (1) fixes the last
``if h.get("outcome")`` in cognitive_efficiency, and (2) routes the
remaining inline ``(get("error") or "").strip()`` call sites through
the shared ``_row_*`` helpers so every free-text field read goes
through one normalisation.
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
        "marker": "DONE", "confidence": "strong",
        "verifier": "pytest", "risk": "low",
        "error": "", "outcome": "", "extra_steps": 0,
    }
    base.update(kw)
    return base


class DetectorFieldHelpersUnifiedTests(unittest.TestCase):

    def test_cognitive_efficiency_ignores_whitespace_outcome(self):
        hist = [_row(i, outcome="  ") for i in range(1, 5)]
        # No verified and no real outcome → 0 deliverables.
        self.assertEqual(mindseam.cognitive_efficiency(hist), 0)

    def test_cognitive_efficiency_still_sees_real_outcome(self):
        hist = [_row(i, outcome="ok") for i in range(1, 5)]
        self.assertEqual(mindseam.cognitive_efficiency(hist), 100)

    def test_no_inline_error_strip_remains(self):
        # The family of hand-rolled strips is gone; only the
        # helpers themselves may contain get("error").
        inline = [
            line for line in SOURCE.splitlines()
            if 'get("error")' in line and "_row_error" not in line
            and "def _row_error" not in line
            and not line.strip().startswith("#")
            and 'return (row.get("error")' not in line
        ]
        self.assertEqual(inline, [], inline)

    def test_no_inline_outcome_strip_remains(self):
        inline = [
            line for line in SOURCE.splitlines()
            if 'get("outcome")' in line and "_row_outcome" not in line
            and "def _row_outcome" not in line
            and not line.strip().startswith("#")
            and 'return (row.get("outcome")' not in line
        ]
        self.assertEqual(inline, [], inline)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("detector-field-helpers-unified", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "detector-field-helpers-unified")
        self.assertEqual(entry["since"], "r234")
        self.assertIn("cognitive_efficiency", entry["summary"])
        self.assertIn("_row_", entry["summary"])


if __name__ == "__main__":
    unittest.main()
