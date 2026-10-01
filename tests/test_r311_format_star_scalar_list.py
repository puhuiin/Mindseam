# -*- coding: utf-8 -*-
"""Round 311 guards: --format a[*] on a scalar list renders values.

_format_path's list branch stripped the indexer and then checked for
a dot in what was left, so ledger.Goal[*] (list of scalars, indexer
at the end) took the nested-key branch and rendered empty.
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


class FormatStarScalarListTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])

    def test_star_on_scalar_list_renders_values(self):
        r = invoke_cli(self.workspace, ["info", "--format", "ledger.Goal[*]"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "g\n")

    def test_star_agrees_with_bare_key(self):
        r_star = invoke_cli(self.workspace, ["info", "--format", "ledger.Goal[*]"])
        r_bare = invoke_cli(self.workspace, ["info", "--format", "ledger.Goal"])
        self.assertEqual(r_star.stdout, r_bare.stdout)

    def test_star_on_dict_list_still_nests(self):
        r = invoke_cli(self.workspace, ["info", "--format", "features[*].id"])
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertTrue(len(lines) > 5)
        self.assertIn("info-warnings-only", lines[0])

    def test_bracket_zero_still_scalar(self):
        r = invoke_cli(self.workspace, ["info", "--format", "ledger.Goal[0]"])
        self.assertEqual(r.stdout, "g\n")

    def test_warnings_star(self):
        r = invoke_cli(self.workspace, ["info", "--format", "warnings[*]"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no seams recorded", r.stdout)

    def test_missing_path_still_empty(self):
        r = invoke_cli(self.workspace, ["info", "--format", "ledger.Goal[99]"])
        self.assertEqual(r.stdout, "\n")

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("format-star-scalar-list", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "format-star-scalar-list")
        self.assertEqual(entry["since"], "r311")
        self.assertIn("scalar", entry["summary"])


if __name__ == "__main__":
    unittest.main()
