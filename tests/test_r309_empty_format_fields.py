# -*- coding: utf-8 -*-
"""Round 309 guards: empty --format / --fields strings are values.

history tested truthiness, so "" was read as "no flag" and fell
through to the default table — while info --format '' (is not None)
and --fields ',' (default next) both honoured the empty value.
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


class EmptyFormatFieldsAreValuesTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])
        invoke_cli(self.workspace, ["seam", "--from-stdin"], stdin="a: one\n")

    def test_format_empty_renders_empty_line(self):
        r = invoke_cli(self.workspace, ["history", "--format", ""])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "\n")

    def test_format_empty_agrees_with_format_space(self):
        r_space = invoke_cli(self.workspace, ["history", "--format", " "])
        r_empty = invoke_cli(self.workspace, ["history", "--format", ""])
        self.assertEqual(r_space.stdout, " \n")
        self.assertEqual(r_empty.stdout, "\n")

    def test_format_empty_not_the_table(self):
        r = invoke_cli(self.workspace, ["history", "--format", ""])
        self.assertNotIn("mindseam", r.stdout)
        self.assertNotIn("entry", r.stdout)

    def test_fields_empty_defaults_to_next(self):
        r = invoke_cli(self.workspace, ["history", "--fields", ""])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], "next")
        self.assertIn("a: one", r.stdout)

    def test_fields_empty_agrees_with_comma(self):
        r_comma = invoke_cli(self.workspace, ["history", "--fields", ","])
        r_empty = invoke_cli(self.workspace, ["history", "--fields", ""])
        self.assertEqual(r_comma.stdout.splitlines()[0], "next")
        self.assertEqual(r_empty.stdout.splitlines()[0], "next")

    def test_format_empty_json_carries_lines(self):
        r = invoke_cli(self.workspace, ["history", "--format", "", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("lines", payload)
        self.assertEqual(payload["lines"], [""])

    def test_absent_flag_unchanged(self):
        r = invoke_cli(self.workspace, ["history"])
        self.assertIn("mindseam", r.stdout)
        self.assertIn("entry", r.stdout)

    def test_nonempty_values_unchanged(self):
        r = invoke_cli(self.workspace, ["history", "--format", "%n"])
        self.assertEqual(r.stdout, "a: one\n")
        r = invoke_cli(self.workspace, ["history", "--fields", "next"])
        self.assertEqual(r.stdout.splitlines()[0], "next")

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("empty-format-fields-are-values", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "empty-format-fields-are-values")
        self.assertEqual(entry["since"], "r309")
        self.assertIn("is-not-None", entry["summary"])


if __name__ == "__main__":
    unittest.main()
