# -*- coding: utf-8 -*-
"""Round 320 guards: --row-id refuses --empty.

r276 made --row-id refuse every narrowing flag; --empty (a content
filter since r278) was missing from the list, so --empty --row-id 1
silently indexed the empty-next subset instead of refusing.
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


class RowIdEmptyNarrowingRefusalTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])
        invoke_cli(self.workspace, ["seam", "--from-stdin"],
                   stdin="a: one\nb: two\nc: three\n")

    def test_empty_rowid_refused(self):
        r = invoke_cli(self.workspace,
                       ["history", "--empty", "--row-id", "1"])
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertIn("CANNOT", r.stderr)
        self.assertIn("--row-id", r.stderr)
        self.assertIn("--empty", r.stderr)

    def test_empty_rowid_json_refused(self):
        r = invoke_cli(self.workspace,
                       ["history", "--empty", "--row-id", "1", "--json"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--empty", r.stderr)

    def test_rowid_alone_still_works(self):
        r = invoke_cli(self.workspace, ["history", "--row-id", "1"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("row 1 of 3", r.stdout)

    def test_empty_alone_still_works(self):
        r = invoke_cli(self.workspace, ["history", "--empty"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no empty-next rows", r.stdout)

    def test_grep_rowid_still_refused(self):
        # The r276 pin is unchanged.
        r = invoke_cli(self.workspace,
                       ["history", "--grep", "a", "--row-id", "1"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--grep", r.stderr)

    def test_refusal_names_both_flags(self):
        r = invoke_cli(self.workspace,
                       ["history", "--empty", "--row-id", "2"])
        self.assertIn("--row-id 2", r.stderr)
        self.assertIn("--empty", r.stderr)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("row-id-empty-narrowing-refusal", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "row-id-empty-narrowing-refusal")
        self.assertEqual(entry["since"], "r320")
        self.assertIn("--empty", entry["summary"])


if __name__ == "__main__":
    unittest.main()
