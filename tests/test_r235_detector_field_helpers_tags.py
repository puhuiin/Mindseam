# -*- coding: utf-8 -*-
"""Round 235 guards: tag-field helpers unified across every free-text read.

r234 unified error/outcome. This round routes the remaining inline
marker/confidence/verifier strips through ``_row_marker`` /
``_row_confidence`` / ``_row_verifier`` so every free-text history
field goes through one normalisation. A source-scan guard pins the
absence of hand-rolled ``.strip()`` on those three fields — exact-
equality uses (``== "PHEW"``, ``in ("thin", "shaky")``) are fine
and are not flagged.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam

SOURCE = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(encoding="utf-8")


def _inline_strips(field):
    return [
        line for line in SOURCE.splitlines()
        if 'get("%s")' % field in line and ".strip()" in line
        and ("_row_%s" % field) not in line
        and not line.strip().startswith("#")
        and 'return (row.get("%s")' % field not in line
    ]


class DetectorFieldHelpersTagsTests(unittest.TestCase):

    def test_no_inline_marker_strip_remains(self):
        self.assertEqual(_inline_strips("marker"), [],
                         _inline_strips("marker"))

    def test_no_inline_confidence_strip_remains(self):
        self.assertEqual(_inline_strips("confidence"), [],
                         _inline_strips("confidence"))

    def test_no_inline_verifier_strip_remains(self):
        self.assertEqual(_inline_strips("verifier"), [],
                         _inline_strips("verifier"))

    def test_verify_then_act_strips_whitespace_marker(self):
        # Whitespace marker reads as unrecorded (OPEN/empty).
        self.assertEqual(mindseam._row_marker({"marker": "   "}), "")
        self.assertIn(mindseam._row_marker({"marker": "   "}),
                      ("OPEN", ""))

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("detector-field-helpers-tags", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "detector-field-helpers-tags")
        self.assertEqual(entry["since"], "r235")
        self.assertIn("_row_marker", entry["summary"])
        self.assertIn("one helper", entry["summary"])


if __name__ == "__main__":
    unittest.main()
