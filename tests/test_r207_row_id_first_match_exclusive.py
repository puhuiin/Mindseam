# -*- coding: utf-8 -*-
"""Round 207 guards: history --row-id and --first-match are exclusive.

Two locators answer "show me one row" and they disagree about
which row. The row-id branch runs first and indexes the FULL
history, so ``history --row-id 2 --first-match`` printed row 2 of
5 (of the full ledger) and the first-match slice never applied —
exit 0, the r188/r200 branch-exclusive family on history's
locators. r207 refuses the pair with exit 2 naming both, before
the destructive --keep rotation, like the renderer pair refusal
it sits next to.

What is NOT refused is pinned in the same file, because the
boundary matters: --first-match with the renderers is REAL
composition — the slice runs first and the renderer renders the
sliced rows (span reports "across 1 rows", csv emits one row,
quiet prints one fact) — and --row-id with a renderer keeps its
documented before-every-render-flag precedence (r197's pin).
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from _controller_helper import invoke_cli

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _invoke(args, cwd):
    return invoke_cli(cwd, args)


class RowIdFirstMatchExclusiveTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        now = int(time.time())
        rows = [{"t": now - i * 60, "next": "dom: s%d" % i,
                 "verified": i + 1, "open": 0} for i in range(5)]
        (self.ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_pair_refused_naming_both(self):
        r = _invoke(["history", "--row-id", "2", "--first-match"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--row-id 2 and --first-match", r.stderr)
        self.assertIn("mutually exclusive row locators", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_refusal_keeps_the_json_face_empty(self):
        r = _invoke(["history", "--row-id", "2", "--first-match",
                     "--json"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_refusal_happens_before_keep_rotation(self):
        # The renderer refusal refuses before the destructive
        # rotation; the locator refusal sits in the same block.
        r = _invoke(["history", "--row-id", "2", "--first-match",
                     "--keep", "1"], self.workspace)
        self.assertEqual(r.returncode, 2)
        rows = json.loads(
            (self.ledger / "history.json").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 5)

    def test_out_of_range_row_id_still_loses_to_the_pair(self):
        # The combination is invalid as a combination before any
        # single flag's own validation matters (r201 precedent).
        r = _invoke(["history", "--row-id", "99", "--first-match"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("mutually exclusive row locators", r.stderr)

    def test_row_id_alone_unchanged(self):
        r = _invoke(["history", "--row-id", "2", "--json"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["row_id"], 2)

    def test_first_match_alone_slices_to_one(self):
        r = _invoke(["history", "--first-match", "--json"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["history_count"], 1)

    def test_first_match_composes_with_renderers(self):
        # Real composition: slice first, then render the slice.
        r = _invoke(["history", "--first-match", "--span"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("across 1 rows", r.stdout)
        r = _invoke(["history", "--first-match", "--quiet"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 1)
        r = _invoke(["history", "--first-match", "--csv"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # header + exactly one data row
        self.assertEqual(len(r.stdout.strip().splitlines()), 2)

    def test_row_id_precedence_pin_untouched(self):
        # r197's composition pin: --row-id with a renderer keeps
        # its documented precedence and does not refuse.
        r = _invoke(["history", "--row-id", "1", "--quiet"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-row-id-first-match-exclusive", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-row-id-first-match-exclusive")
        self.assertEqual(entry["since"], "r207")
        self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
