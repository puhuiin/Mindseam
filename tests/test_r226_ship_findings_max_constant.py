# -*- coding: utf-8 -*-
"""Round 226 guards: ship's findings cap is a named constant.

The text face printed ``findings[:7]`` — a magic number next to
heal's named ``HEAL_REPORT_MAX``. r226 names it ``SHIP_FINDINGS_MAX``
and adds an overflow line in the same shape heal uses, so a future
finding source that pushes past the cap cannot silently truncate.

The cap sits above the five finding sources ship can emit today
(leaked symbols, hot markers, uncovered claim, line-repeat, char-run),
so the overflow path is a safety contract, not a live path. The guard
pins the constant, the source shape, and the catalog entry.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam

SOURCE = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(encoding="utf-8")


class ShipFindingsMaxTests(unittest.TestCase):

    def test_constant_exists_and_is_seven(self):
        self.assertEqual(mindseam.SHIP_FINDINGS_MAX, 7)
        self.assertGreater(mindseam.SHIP_FINDINGS_MAX,
                           mindseam.HEAL_REPORT_MAX)

    def test_source_uses_the_constant_not_a_magic_slice(self):
        self.assertIn("findings[:SHIP_FINDINGS_MAX]", SOURCE)
        self.assertNotIn("findings[:7]", SOURCE)

    def test_overflow_notice_matches_heal_shape(self):
        self.assertIn("JSON face carries the full list", SOURCE)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("ship-findings-max-constant", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "ship-findings-max-constant")
        self.assertEqual(entry["since"], "r226")
        self.assertIn("SHIP_FINDINGS_MAX", entry["summary"])


if __name__ == "__main__":
    unittest.main()
