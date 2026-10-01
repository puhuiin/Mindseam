# -*- coding: utf-8 -*-
"""Round 297 guards: history --fields refuses unknown columns.

A column name is a closed vocabulary the way --filter keys and
--tag names are. --filter already refuses an unknown key with exit 2
and a CANNOT naming the field list; --fields rendered an unknown name
as a silent '-' column at exit 0. A host typo (``--fields next,ms``)
got a two-column TSV whose second column was every row's '-'.
"""

import json
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


class FieldsColumnRefusalTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "build: one"])
        invoke_cli(self.workspace, ["seam", "--from-stdin"], stdin="build: a\n")

    def test_unknown_column_refused(self):
        r = invoke_cli(self.workspace, ["history", "--fields", "bogus"])
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertIn("CANNOT", r.stderr)
        self.assertIn("bogus", r.stderr)
        self.assertIn("history field", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_typo_column_refused(self):
        # The live-before-fix lie: next,ms rendered a silent '-' column.
        r = invoke_cli(self.workspace, ["history", "--fields", "next,ms"])
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertIn("ms", r.stderr)

    def test_wrong_case_refused(self):
        r = invoke_cli(self.workspace, ["history", "--fields", "next,NEXT"])
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertIn("NEXT", r.stderr)

    def test_error_names_field_list(self):
        r = invoke_cli(self.workspace, ["history", "--fields", "zzz"])
        self.assertIn("fields:", r.stderr)
        for name in mindseam.HISTORY_ROW_FIELDS:
            self.assertIn(name, r.stderr)

    def test_agrees_with_filter_shape(self):
        # The same unknown name refuses the same way --filter does.
        filt = invoke_cli(self.workspace,
                          ["history", "--filter", "zzz=1"])
        cols = invoke_cli(self.workspace,
                          ["history", "--fields", "zzz"])
        self.assertEqual(filt.returncode, cols.returncode)
        self.assertIn("is not a history field", filt.stderr)
        self.assertIn("is not a history field", cols.stderr)

    def test_valid_columns_still_work(self):
        r = invoke_cli(self.workspace,
                       ["history", "--fields", "next,msg,error"])
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = [l for l in r.stdout.splitlines() if l]
        self.assertEqual(lines[0], "next\tmsg\terror")
        self.assertEqual(len(lines), 2)  # header + one row

    def test_trailing_comma_still_dropped(self):
        r = invoke_cli(self.workspace, ["history", "--fields", "next,"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], "next")

    def test_empty_still_defaults_to_next(self):
        r = invoke_cli(self.workspace, ["history", "--fields", ","])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], "next")

    def test_filter_unknown_still_refused(self):
        # The sibling contract is unchanged.
        r = invoke_cli(self.workspace,
                       ["history", "--filter", "bogus=1"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("is not a history field", r.stderr)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("fields-column-refusal", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "fields-column-refusal")
        self.assertEqual(entry["since"], "r297")
        self.assertIn("HISTORY_ROW_FIELDS", entry["summary"])


if __name__ == "__main__":
    unittest.main()
