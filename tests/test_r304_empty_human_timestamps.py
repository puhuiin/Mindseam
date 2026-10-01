# -*- coding: utf-8 -*-
"""Round 304 guards: history --empty honours --human on its
timestamps.

r303 fixed --span ignoring --human. The same hardcoded strftime sat
on the --empty text face, so ``history --empty --human`` printed
absolute dates and silently dropped the flag.
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


class EmptyHumanTimestampsTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])
        invoke_cli(self.workspace, ["seam", "--from-stdin"], stdin="a: one\n")
        hist_path = os.path.join(self.workspace, ".mindseam", "history.json")
        with open(hist_path, encoding="utf-8") as fh:
            hist = json.load(fh)
        hist.append({"t": 1790000000, "next": "", "verified": 0, "open": 0})
        with open(hist_path, "w", encoding="utf-8") as fh:
            json.dump(hist, fh, ensure_ascii=False)

    def test_empty_human_renders_relative(self):
        r = invoke_cli(self.workspace, ["history", "--empty", "--human"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ago", r.stdout)
        self.assertNotIn("1790", r.stdout)

    def test_empty_without_human_keeps_absolute(self):
        r = invoke_cli(self.workspace, ["history", "--empty"])
        self.assertEqual(r.returncode, 0, r.stderr)
        # Absolute date stamp, not "ago".
        self.assertRegex(r.stdout, r"20\d\d-\d\d-\d\d")

    def test_empty_human_agrees_with_table(self):
        table = invoke_cli(self.workspace, ["history", "--human"])
        empty = invoke_cli(self.workspace, ["history", "--empty", "--human"])
        self.assertIn("ago", table.stdout)
        self.assertIn("ago", empty.stdout)

    def test_empty_json_unchanged(self):
        r = invoke_cli(self.workspace, ["history", "--empty", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(len(payload["rows"]), 1)
        self.assertIsInstance(payload["rows"][0].get("t"), int)

    def test_empty_row_number_still_full_log(self):
        # The r298 pin: the number is the full-log index.
        r = invoke_cli(self.workspace, ["history", "--empty"])
        self.assertIn("    2", r.stdout)

    def test_span_human_still_works(self):
        # The r303 pin.
        r = invoke_cli(self.workspace, ["history", "--span", "--human"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ago", r.stdout)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("empty-human-timestamps", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "empty-human-timestamps")
        self.assertEqual(entry["since"], "r304")
        self.assertIn("--empty", entry["summary"])


if __name__ == "__main__":
    unittest.main()
