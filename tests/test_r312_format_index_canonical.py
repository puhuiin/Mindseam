# -*- coding: utf-8 -*-
"""Round 312 guards: --format bracket indices are canonical ASCII.

_resolve_path used (\\d+|\\*|-?\\d+), so features[０] folded to index 0
and features[01] folded to 1 — the r294/r296 looseness on a third
surface. Keys stay \\w+ (Unicode JSON keys are real).
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


class FormatIndexCanonicalTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])

    def test_canonical_indices_work(self):
        for path, expect in (("features[0].id", "info-warnings-only"),
                             ("features[-1].id", None),  # last feature
                             ("ledger.Goal[0]", "g")):
            r = invoke_cli(self.workspace, ["info", "--format", path])
            self.assertEqual(r.returncode, 0, r.stderr)
            if expect is not None:
                self.assertEqual(r.stdout.strip(), expect)
            else:
                self.assertTrue(r.stdout.strip())  # non-empty id

    def test_fullwidth_index_refused(self):
        for path in ("features[０].id", "features[１].id", "ledger.Goal[０]"):
            r = invoke_cli(self.workspace, ["info", "--format", path])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "\n", path)

    def test_leading_zeros_refused(self):
        for path in ("features[00].id", "features[01].id", "ledger.Goal[00]"):
            r = invoke_cli(self.workspace, ["info", "--format", path])
            self.assertEqual(r.stdout, "\n", path)

    def test_minus_zero_refused(self):
        r = invoke_cli(self.workspace, ["info", "--format", "features[-0].id"])
        self.assertEqual(r.stdout, "\n")

    def test_star_still_works(self):
        r = invoke_cli(self.workspace, ["info", "--format", "features[*].id"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("info-warnings-only", r.stdout)

    def test_unicode_key_still_works(self):
        # JSON keys may be Unicode; only the index is tightened.
        import os
        import json
        p = os.path.join(self.workspace, ".mindseam", "aliases.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"日本語": {"command": "x", "args": [], "summary": "s"}},
                      fh, ensure_ascii=False)
        r = invoke_cli(self.workspace, ["info", "--aliases", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("format-index-canonical", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "format-index-canonical")
        self.assertEqual(entry["since"], "r312")
        self.assertIn("canonical", entry["summary"])


if __name__ == "__main__":
    unittest.main()
