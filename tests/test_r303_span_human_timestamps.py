# -*- coding: utf-8 -*-
"""Round 303 guards: history --span honours --human on its endpoint
timestamps.

r197 promised "--human renders timestamps under any renderer", and
the table / --row-id detail face honour it through _history_when.
--span hardcoded strftime, so --span --human printed absolute dates
and silently dropped the flag. Duration stays raw seconds (r283 pin).
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


class SpanHumanTimestampsTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])
        invoke_cli(self.workspace, ["seam", "--from-stdin"],
                   stdin="a: one\nb: two\n")

    def test_span_human_renders_relative(self):
        r = invoke_cli(self.workspace, ["history", "--span", "--human"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ago", r.stdout)
        # No absolute date stamp in the human face.
        self.assertNotIn("First seam: 20", r.stdout)

    def test_span_without_human_keeps_absolute(self):
        r = invoke_cli(self.workspace, ["history", "--span"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("First seam: 20", r.stdout)

    def test_span_human_agrees_with_table(self):
        # Both faces read the same _history_when helper.
        table = invoke_cli(self.workspace, ["history", "--human"])
        span = invoke_cli(self.workspace, ["history", "--span", "--human"])
        self.assertIn("ago", table.stdout)
        self.assertIn("ago", span.stdout)

    def test_duration_stays_raw_seconds(self):
        # The r283 pin: duration is an integer, not a humanized ladder.
        r = invoke_cli(self.workspace, ["history", "--span", "--human"])
        self.assertIn("second", r.stdout)
        r = invoke_cli(self.workspace, ["history", "--span"])
        self.assertIn("second", r.stdout)

    def test_span_json_unchanged(self):
        r = invoke_cli(self.workspace, ["history", "--span", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        span = json.loads(r.stdout)["span"]
        self.assertIn("first", span)
        self.assertIn("last", span)
        self.assertIn("duration_seconds", span)
        self.assertIsInstance(span["first"], int)

    def test_rowid_human_unchanged(self):
        r = invoke_cli(self.workspace, ["history", "--row-id", "1", "--human"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ago", r.stdout)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("span-human-timestamps", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "span-human-timestamps")
        self.assertEqual(entry["since"], "r303")
        self.assertIn("human", entry["summary"])


if __name__ == "__main__":
    unittest.main()
