# -*- coding: utf-8 -*-
"""Round 298 guards: display row numbers agree with --row-id.

history --row-id N is a 1-based index into the FULL log (r207, r276).
But the default table, the --empty face, and --format %h all numbered
their output with enumerate(hist, 1) AFTER the filter chain, so
``history --tail 2`` printed "1, 2" while ``--row-id 1`` returned the
oldest row of the full log — the same visual "row 1" named two
different rows in one command.
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


class DisplayRowIdAgreementTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])
        for nxt in ("a: one", "b: two", "c: three", "d: four", "e: five"):
            invoke_cli(self.workspace, ["seam", "--from-stdin"],
                       stdin=nxt + "\n")

    def test_tail_shows_full_log_numbers(self):
        r = invoke_cli(self.workspace, ["history", "--tail", "2"])
        self.assertEqual(r.returncode, 0, r.stderr)
        body = [l for l in r.stdout.splitlines() if l.strip()
                and not l.startswith("─")]
        # Rows 4 and 5 of the five-row log, not 1 and 2.
        self.assertIn("    4", body[0])
        self.assertIn("d: four", body[0])
        self.assertIn("    5", body[1])
        self.assertIn("e: five", body[1])

    def test_grep_keeps_full_log_numbers(self):
        r = invoke_cli(self.workspace,
                       ["history", "--grep", "three", "--format", "%h %next"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "3 c: three")

    def test_format_h_is_row_id(self):
        # The number %h prints is the number --row-id accepts.
        r = invoke_cli(self.workspace,
                       ["history", "--tail", "2", "--format", "%h %next"])
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "4 d: four")
        self.assertEqual(lines[1], "5 e: five")
        r4 = invoke_cli(self.workspace, ["history", "--row-id", "4"])
        self.assertIn("d: four", r4.stdout)
        r5 = invoke_cli(self.workspace, ["history", "--row-id", "5"])
        self.assertIn("e: five", r5.stdout)

    def test_empty_face_shows_full_log_numbers(self):
        # Plant a blank-next row at the end of the log.
        import json
        import os
        hist_path = os.path.join(self.workspace, ".mindseam", "history.json")
        with open(hist_path, encoding="utf-8") as fh:
            hist = json.load(fh)
        hist.append({"t": 1790000000, "next": "", "verified": 0, "open": 0})
        with open(hist_path, "w", encoding="utf-8") as fh:
            json.dump(hist, fh, ensure_ascii=False)
        r = invoke_cli(self.workspace, ["history", "--empty"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("    6", r.stdout)

    def test_unfiltered_numbers_unchanged(self):
        r = invoke_cli(self.workspace, ["history", "--format", "%h %next"])
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "1 a: one")
        self.assertEqual(lines[-1], "5 e: five")

    def test_reverse_keeps_full_log_numbers(self):
        r = invoke_cli(self.workspace,
                       ["history", "--tail", "2", "--reverse",
                        "--format", "%h %next"])
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        # Newest first, but the numbers stay the log positions.
        self.assertEqual(lines[0], "5 e: five")
        self.assertEqual(lines[1], "4 d: four")

    def test_row_id_contract_unchanged(self):
        r = invoke_cli(self.workspace, ["history", "--row-id", "3"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("row 3 of 5", r.stdout)
        self.assertIn("c: three", r.stdout)

    def test_dedup_index_still_lists_uniques(self):
        # --dedup numbers unique entries, not log rows — unchanged.
        r = invoke_cli(self.workspace, ["history", "--dedup"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("    1", r.stdout)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("display-row-id-agreement", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "display-row-id-agreement")
        self.assertEqual(entry["since"], "r298")
        self.assertIn("full-log", entry["summary"])


if __name__ == "__main__":
    unittest.main()
