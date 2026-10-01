# -*- coding: utf-8 -*-
"""Round 307 guards: COVERAGE Chinese set and "up to" are precise.

r306 tightened the English half. The Chinese set still carried
ordinary nouns (文件/记录/命令/分支/范围/全部/所有/...) and bare
"up to" matched "up to the mark" / "up to you".
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


class CoverageChineseUptoPrecisionTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])

    def _ship(self, body):
        import os
        out = os.path.join(self.workspace, "out.txt")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(body)
        return invoke_cli(self.workspace, ["ship", out])

    def test_chinese_ordinary_nouns_no_longer_cover(self):
        for phrase in ("已经验证了这个文件",
                       "已经验证，见文件",
                       "已经确认记录无误",
                       "已验证命令可用",
                       "已验证分支合并",
                       "已验证范围正确",
                       "已验证全部完成"):
            self.assertTrue(mindseam.CLAIM.search(phrase), phrase)
            self.assertIsNone(mindseam.COVERAGE.search(phrase), phrase)

    def test_chinese_real_coverage_still_covers(self):
        for phrase in ("已验证所有输入",
                       "已验证，包括边界和空输入",
                       "已经验证，n<=6，覆盖空值",
                       "已验证用例与样本"):
            self.assertTrue(mindseam.COVERAGE.search(phrase), phrase)

    def test_upto_requires_digits(self):
        for phrase in ("tested up to the mark",
                       "verified up to you",
                       "已经验证，up to the mark"):
            self.assertTrue(mindseam.CLAIM.search(phrase), phrase)
            self.assertIsNone(mindseam.COVERAGE.search(phrase), phrase)

    def test_upto_with_digits_still_covers(self):
        for phrase in ("verified up to 10 cases",
                       "brute force, up to 10, including empty"):
            self.assertTrue(mindseam.COVERAGE.search(phrase), phrase)

    def test_r306_pins_unchanged(self):
        self.assertIsNone(mindseam.COVERAGE.search("the line was verified"))
        self.assertTrue(mindseam.COVERAGE.search("brute force, n <= 6"))
        self.assertTrue(mindseam.COVERAGE.search("proven for all cases"))

    def test_ship_fires_on_chinese_uncov_claim(self):
        r = self._ship("已经验证了这个文件\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("verification covered", r.stdout)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("coverage-chinese-and-upto-precision", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "coverage-chinese-and-upto-precision")
        self.assertEqual(entry["since"], "r307")
        self.assertIn("Chinese", entry["summary"])


if __name__ == "__main__":
    unittest.main()
