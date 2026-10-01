# -*- coding: utf-8 -*-
"""Round 314 guards: --format %x renders extra_steps.

r253 gave %v/%o the count guard, r313 put extra_steps in
HISTORY_COUNT_FIELDS for --fields/--csv, but the format template
never grew a token for the third count. %x rendered the literal 'x'.
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


class FormatExtraStepsTokenTests(unittest.TestCase):

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

    def test_x_renders_extra_steps(self):
        r = invoke_cli(self.workspace, ["history", "--format", "%x %n"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "0 a: one\n3 b: two\n")

    def test_x_zero_renders_zero(self):
        r = invoke_cli(self.workspace, ["history", "--format", "%x"])
        self.assertEqual(r.stdout.splitlines()[0], "0")

    def test_x_missing_renders_placeholder(self):
        p = os.path.join(self.workspace, ".mindseam", "history.json")
        with open(p, encoding="utf-8") as fh:
            hist = json.load(fh)
        hist.append({"t": 3, "next": "c: three"})
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(hist, fh, ensure_ascii=False)
        r = invoke_cli(self.workspace, ["history", "--format", "%x %n"])
        self.assertEqual(r.stdout.splitlines()[-1], "- c: three")

    def test_x_agrees_with_fields_and_json(self):
        r_fmt = invoke_cli(self.workspace, ["history", "--format", "%x"])
        r_fld = invoke_cli(self.workspace, ["history", "--fields", "extra_steps"])
        r_json = invoke_cli(self.workspace, ["history", "--json"])
        fmt_vals = r_fmt.stdout.splitlines()
        fld_vals = r_fld.stdout.splitlines()[1:]
        json_vals = [str(row.get("extra_steps"))
                     for row in json.loads(r_json.stdout)["rows"]]
        self.assertEqual(fmt_vals, fld_vals)
        self.assertEqual(fmt_vals, json_vals)

    def test_count_trio_agrees(self):
        r = invoke_cli(self.workspace, ["history", "--format", "%v %o %x"])
        self.assertEqual(r.stdout, "0 0 0\n1 2 3\n")

    def test_json_lines_carry_x(self):
        r = invoke_cli(self.workspace,
                       ["history", "--format", "%x", "--json"])
        lines = json.loads(r.stdout)["lines"]
        self.assertEqual(lines, ["0", "3"])

    def test_existing_tokens_unchanged(self):
        r = invoke_cli(self.workspace,
                       ["history", "--format", "%t %n %m %v %o %h"])
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("a: one", lines[0])

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("format-extra-steps-token", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "format-extra-steps-token")
        self.assertEqual(entry["since"], "r314")
        self.assertIn("%x", entry["summary"])


if __name__ == "__main__":
    unittest.main()
