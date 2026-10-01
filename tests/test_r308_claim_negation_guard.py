# -*- coding: utf-8 -*-
"""Round 308 guards: CLAIM carries the negation guard.

"not verified", "has not been tested", "cannot be verified" and the
Chinese "未经验证" / "未经确认" state the ABSENCE of verification, yet
the old CLAIM regex matched the bare verb inside the negation.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam
from _controller_helper import invoke_cli


class ClaimNegationGuardTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])

    def _ship(self, body):
        import os
        out = os.path.join(self.workspace, "out.txt")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(body)
        return invoke_cli(self.workspace, ["ship", out])

    def test_english_negation_is_not_a_claim(self):
        for phrase in ("not verified", "never verified", "not confirmed",
                       "not tested", "not proven", "not validated",
                       "is not tested", "was not confirmed",
                       "cannot be verified", "has not been tested"):
            self.assertIsNone(mindseam.CLAIM.search(phrase), phrase)

    def test_chinese_negation_is_not_a_claim(self):
        for phrase in ("未经验证", "未经确认", "未经测试", "未经证明",
                       "未经验证的代码", "这个方法未经验证"):
            self.assertIsNone(mindseam.CLAIM.search(phrase), phrase)

    def test_positives_still_claims(self):
        for phrase in ("verified", "tested", "confirmed", "proven",
                       "validated", "已经验证", "已验证", "经验证",
                       "验证通过", "确认无误", "测试通过", "已证明"):
            self.assertTrue(mindseam.CLAIM.search(phrase), phrase)

    def test_unverified_still_not_a_claim(self):
        # The \\b guard, not the negation chain.
        self.assertIsNone(mindseam.CLAIM.search("unverified"))
        self.assertIsNone(mindseam.CLAIM.search("verification pending"))

    def test_ship_clean_on_negated_claim(self):
        r = self._ship("this path is not verified\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("verification covered", r.stdout)

    def test_ship_fires_on_positive_claim(self):
        r = self._ship("verified working\n")
        self.assertIn("verification covered", r.stdout)

    def test_ship_clean_on_negated_chinese(self):
        r = self._ship("这个方法未经验证\n")
        self.assertNotIn("verification covered", r.stdout)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("claim-negation-guard", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "claim-negation-guard")
        self.assertEqual(entry["since"], "r308")
        self.assertIn("CLAIM", entry["summary"])


if __name__ == "__main__":
    unittest.main()
