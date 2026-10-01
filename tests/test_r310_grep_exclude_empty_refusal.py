# -*- coding: utf-8 -*-
"""Round 310 guards: --grep '' / --exclude '' refuse.

An empty needle is not "no filter". --grep '' would match every row
and --exclude '' would drop every row — and the old truthiness skip
made the two disagree. The honest answer is refuse, matching
--since '' / --filter ''.
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


class GrepExcludeEmptyRefusalTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])
        invoke_cli(self.workspace, ["seam", "--from-stdin"],
                   stdin="a: one\nb: two\nc: three\n")

    def test_grep_empty_refused(self):
        r = invoke_cli(self.workspace, ["history", "--grep", ""])
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertIn("CANNOT", r.stderr)
        self.assertIn("--grep", r.stderr)

    def test_exclude_empty_refused(self):
        r = invoke_cli(self.workspace, ["history", "--exclude", ""])
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertIn("CANNOT", r.stderr)
        self.assertIn("--exclude", r.stderr)

    def test_whitespace_only_refused(self):
        for flag in ("--grep", "--exclude"):
            r = invoke_cli(self.workspace, ["history", flag, "   "])
            self.assertEqual(r.returncode, 2, (flag, r.stdout, r.stderr))
            self.assertIn("empty value", r.stderr)

    def test_nonempty_needles_still_work(self):
        r = invoke_cli(self.workspace, ["history", "--grep", "one"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 entry", r.stdout)
        r = invoke_cli(self.workspace, ["history", "--exclude", "one"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("2 entries", r.stdout)

    def test_absent_flag_unchanged(self):
        r = invoke_cli(self.workspace, ["history"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("3 entries", r.stdout)

    def test_refusal_names_the_flag(self):
        r = invoke_cli(self.workspace, ["history", "--grep", "", "--json"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--grep", r.stderr)
        r = invoke_cli(self.workspace, ["history", "--exclude", "", "--json"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--exclude", r.stderr)

    def test_since_empty_still_refused(self):
        # The sibling CANNOT family is unchanged.
        r = invoke_cli(self.workspace, ["history", "--since", ""])
        self.assertEqual(r.returncode, 2)
        self.assertIn("empty", r.stderr)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("grep-exclude-empty-refusal", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "grep-exclude-empty-refusal")
        self.assertEqual(entry["since"], "r310")
        self.assertIn("empty needle", entry["summary"])


if __name__ == "__main__":
    unittest.main()
