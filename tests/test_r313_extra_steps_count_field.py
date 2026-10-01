# -*- coding: utf-8 -*-
"""Round 313 guards: extra_steps is a count field.

r254's taxonomy listed only verified/open in HISTORY_COUNT_FIELDS,
so --fields extra_steps rendered '-' and --csv rendered a blank cell
for 0 while --json reported 0.
"""

import json
import os
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


class ExtraStepsCountFieldTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])
        invoke_cli(self.workspace, ["seam", "--from-stdin"], stdin="a: one\n")
        p = os.path.join(self.workspace, ".mindseam", "history.json")
        with open(p, encoding="utf-8") as fh:
            hist = json.load(fh)
        hist.append({"t": 2, "next": "b: two", "verified": 1, "open": 2,
                     "extra_steps": 3})
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(hist, fh, ensure_ascii=False)

    def test_fields_extra_steps_zero_renders_zero(self):
        r = invoke_cli(self.workspace,
                       ["history", "--fields", "next,extra_steps"])
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "next\textra_steps")
        self.assertEqual(lines[1], "a: one\t0")
        self.assertEqual(lines[2], "b: two\t3")

    def test_csv_extra_steps_zero_renders_zero(self):
        r = invoke_cli(self.workspace,
                       ["history", "--csv", "--fields", "next,extra_steps"])
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[1], "a: one,0")
        self.assertEqual(lines[2], "b: two,3")

    def test_json_extra_steps_unchanged(self):
        r = invoke_cli(self.workspace, ["history", "--json"])
        rows = json.loads(r.stdout)["rows"]
        self.assertEqual(rows[0]["extra_steps"], 0)
        self.assertEqual(rows[1]["extra_steps"], 3)

    def test_all_three_counts_agree(self):
        r = invoke_cli(self.workspace,
                       ["history", "--fields", "verified,open,extra_steps"])
        lines = r.stdout.splitlines()
        self.assertEqual(lines[1], "0\t0\t0")
        self.assertEqual(lines[2], "1\t2\t3")

    def test_missing_extra_steps_still_placeholder(self):
        p = os.path.join(self.workspace, ".mindseam", "history.json")
        with open(p, encoding="utf-8") as fh:
            hist = json.load(fh)
        hist.append({"t": 3, "next": "c: three"})  # no extra_steps key
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(hist, fh, ensure_ascii=False)
        r = invoke_cli(self.workspace, ["history", "--fields", "extra_steps"])
        # A MISSING key is not a genuine zero — r254's taxonomy keeps
        # the placeholder for absent values, only is-not-None 0 shows '0'.
        lines = r.stdout.splitlines()
        self.assertEqual(lines[-1], "-")

    def test_text_field_empty_still_placeholder(self):
        r = invoke_cli(self.workspace, ["history", "--fields", "next,msg"])
        lines = r.stdout.splitlines()
        self.assertEqual(lines[1], "a: one\t-")

    def test_count_fields_include_extra_steps(self):
        self.assertIn("extra_steps", mindseam.HISTORY_COUNT_FIELDS)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("extra-steps-count-field", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "extra-steps-count-field")
        self.assertEqual(entry["since"], "r313")
        self.assertIn("extra_steps", entry["summary"])


if __name__ == "__main__":
    unittest.main()
