# -*- coding: utf-8 -*-
"""Round 237 guards: next-field helpers unified across every free-text read.

r234/r235/r236 unified error/outcome and marker/confidence/verifier.
This round routes the 25 remaining inline ``(get("next") or "").strip()``
call sites through ``_row_next`` so every free-text history field goes
through one helper. A source-scan guard pins the absence of hand-rolled
next strips.
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


class DetectorFieldHelpersNextTests(unittest.TestCase):

    def test_no_inline_next_strip_remains(self):
        inline = [
            line for line in SOURCE.splitlines()
            if 'get("next")' in line and ".strip()" in line
            and "_row_next" not in line
            and "def _row_next" not in line
            and not line.strip().startswith("#")
            and 'return (row.get("next")' not in line
        ]
        self.assertEqual(inline, [], inline)

    def test_row_next_strips(self):
        self.assertEqual(mindseam._row_next({"next": "  a  "}), "a")
        self.assertEqual(mindseam._row_next({"next": "   "}), "")
        self.assertEqual(mindseam._row_next({}), "")

    def test_detect_stall_still_works_after_unify(self):
        hist = [_row(i, next="build: x") for i in range(1, 5)]
        facts = mindseam.detect_stall(hist)
        self.assertTrue(any("not changed" in f for f in facts), facts)

    def test_loop_detection_still_works_after_unify(self):
        hist = [_row(1, next="a: 1"), _row(2, next="b: 2"),
                _row(3, next="a: 1"), _row(4, next="b: 2")]
        facts = mindseam.loop_detection(hist)
        self.assertTrue(facts, facts)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("detector-field-helpers-next", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "detector-field-helpers-next")
        self.assertEqual(entry["since"], "r237")
        self.assertIn("_row_next", entry["summary"])
        self.assertIn("25", entry["summary"])


if __name__ == "__main__":
    unittest.main()
