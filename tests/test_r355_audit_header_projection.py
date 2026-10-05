# -*- coding: utf-8 -*-
"""r355 — the audit text header did not name its projections.

r161 gave ``--at`` a header clause ("(at seam N of M)") and r162 gave
``--baseline`` its "Baselined: N" line, but ``--tag`` and the
``--since``/``--until`` window printed under a bare header — while the
JSON face disclosed both all along (the ``tags`` key and
``history_window``). Live before-fix, on a ledger whose full audit
answered "Grade: D (5 fresh items)":

    audit --tag next-stall   ->  "── mindseam ─ audit"
                                 "Grade: B (1 fresh item)"
    audit --since 1          ->  "── mindseam ─ audit"
                                 "Grade: C (2 fresh items)"

The projection was invisible and the grade read as the whole story: a
host skimming the text face saw a B where the whole-audit answer was
D, with nothing on the page saying the findings (and the grade over
them) had been narrowed first. r161 fixed the one locator it added and
missed the projector and the window it did not — the same face, the
same doctrine r324 stated for history ("a host must be able to tell
WHAT narrowed the rows it is about to act on").

The fix joins every locator/projection into one parenthesised clause
list: r161's exact "(at seam N of M)" is preserved, a "tags: X" clause
(comma-joined, the way ``--tag a,b`` is parsed) follows it, and the
window reuses the history face's r324 wording ("last N s" / "older
than N s"). --at and the window are mutually exclusive (r188), so at
most one locator appears; --tag composes with both. A no-flag call
renders byte-identically, and the clean branch's r156 literals
("Lean already. Ship." / "Lean on X. Ship.") are untouched — that
branch is the next carrier, not this round.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import mindseam
from _controller_helper import invoke_cli

FIVE_FINDINGS = ("# Mindseam Workspace Ledger\n\n## Goal\ng\n\n## Core\n"
                 "- c1 — work\n- c2 — review\n- c3 — three\n\n"
                 "## Verified\n\n## Open\n\n## Next\nbuild: the parser\n")
LEAN = ("# Mindseam Workspace Ledger\n\n## Goal\ng\n\n## Core\n\n"
        "## Verified\n\n## Open\n\n## Next\n\n")


class AuditHeaderBase(unittest.TestCase):
    def _workspace(self, rows_n, ledger=FIVE_FINDINGS):
        ws = tempfile.mkdtemp()
        d = os.path.join(ws, ".mindseam")
        os.makedirs(d)
        with open(os.path.join(d, "WORKSPACE.md"), "w",
                  encoding="utf-8") as f:
            f.write(ledger)
        rows = [{"t": 1700000000 + i, "next": "build: the parser",
                 "msg": "m", "verified": 1, "open": 0}
                for i in range(rows_n)]
        with open(os.path.join(d, "history.json"), "w",
                  encoding="utf-8") as f:
            json.dump(rows, f)
        return ws

    def _header(self, ws, *flags):
        r = invoke_cli(ws, ["audit", *flags])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.splitlines()[0]


class HeaderProjectionTests(AuditHeaderBase):
    def setUp(self):
        self.ws = self._workspace(12)

    def test_no_flags_header_is_byte_identical(self):
        self.assertEqual(self._header(self.ws), "── mindseam ─ audit")

    def test_tag_clause_single(self):
        self.assertEqual(self._header(self.ws, "--tag", "next-stall"),
                         "── mindseam ─ audit (tags: next-stall)")

    def test_tag_clause_multi(self):
        self.assertEqual(
            self._header(self.ws, "--tag", "next-stall,shrink"),
            "── mindseam ─ audit (tags: next-stall, shrink)")

    def test_window_clauses_reuse_the_history_wording(self):
        self.assertEqual(self._header(self.ws, "--since", "1"),
                         "── mindseam ─ audit (last 1 s)")
        self.assertEqual(self._header(self.ws, "--until", "3600"),
                         "── mindseam ─ audit (older than 3600 s)")

    def test_r161_at_clause_is_preserved(self):
        self.assertEqual(self._header(self.ws, "--at", "10"),
                         "── mindseam ─ audit (at seam 10 of 12)")

    def test_at_and_tag_compose(self):
        self.assertEqual(
            self._header(self.ws, "--at", "10", "--tag", "next-stall"),
            "── mindseam ─ audit (at seam 10 of 12, tags: next-stall)")

    def test_tag_and_window_compose(self):
        # 100000000 s reaches back past the 2023-11 timestamps, so the
        # window keeps every row and next-stall still fires — the
        # findings path, not the clean branch.
        self.assertEqual(
            self._header(self.ws, "--tag", "next-stall",
                         "--since", "100000000"),
            "── mindseam ─ audit (tags: next-stall, last 100000000 s)")


class GradeProjectionTests(AuditHeaderBase):
    def test_projected_grade_reads_under_its_own_clause(self):
        # The whole point: the grade is computed over the projected
        # set (r180/r156 semantics, unchanged), so the header must say
        # what it was computed over. Header first, grade second.
        ws = self._workspace(12)
        r = invoke_cli(ws, ["audit", "--tag", "next-stall"])
        self.assertEqual(r.returncode, 0, r.stderr)
        head, grade = r.stdout.splitlines()[:2]
        self.assertEqual(head, "── mindseam ─ audit (tags: next-stall)")
        self.assertEqual(grade, "Grade: B (1 fresh item)")
        full = invoke_cli(ws, ["audit"])
        self.assertIn("Grade: D (5 fresh items)", full.stdout)

    def test_unfiltered_grade_is_untouched(self):
        ws = self._workspace(12)
        self.assertIn("Grade: D (5 fresh items)",
                      invoke_cli(ws, ["audit"]).stdout)


class JsonFaceUnchangedTests(AuditHeaderBase):
    def setUp(self):
        self.ws = self._workspace(12)

    def _json(self, *flags):
        r = invoke_cli(self.ws, ["audit", "--json", *flags])
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_tags_key_still_discloses(self):
        payload = self._json("--tag", "next-stall")
        self.assertEqual(payload["tags"], ["next-stall"])
        self.assertEqual(sorted({f["tag"] for f in payload["findings"]}),
                         ["next-stall"])

    def test_history_window_still_discloses(self):
        payload = self._json("--since", "1")
        self.assertEqual(payload["history_window"]["since_seconds"], 1)

    def test_unfiltered_tags_lists_every_tag(self):
        self.assertEqual(len(self._json()["tags"]), len(mindseam.AUDIT_TAGS))


class NeighbouringGuardsTests(AuditHeaderBase):
    def test_r156_clean_literals_untouched(self):
        ws = self._workspace(0, ledger=LEAN)
        r = invoke_cli(ws, ["audit"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "Lean already. Ship.\n")

    def test_r156_clean_on_chosen_literal_untouched(self):
        ws = self._workspace(12)
        r = invoke_cli(ws, ["audit", "--tag", "next-stall",
                            "--since", "604800"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "Lean on next-stall. Ship.\n")

    def test_r161_clean_at_literal_untouched(self):
        # The --at clean branch keeps its r161 wording. The LEAN book
        # keeps the ledger-surface tags silent (they read the book
        # directly, --at does not narrow them), and a two-row slice
        # cannot fire the 3-of-last-5 stall, so the seam is lean.
        ws = self._workspace(12, ledger=LEAN)
        r = invoke_cli(ws, ["audit", "--at", "2"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout,
                         "Lean already (at seam 2 of 12). Ship.\n")

    def test_r159_unknown_tag_still_refused(self):
        r = invoke_cli(self._workspace(12), ["audit", "--tag", "bogus"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)

    def test_r161_at_out_of_range_still_refused(self):
        r = invoke_cli(self._workspace(12), ["audit", "--at", "99"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)

    def test_r188_at_and_window_still_refused(self):
        r = invoke_cli(self._workspace(12),
                       ["audit", "--at", "3", "--since", "100"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)


class CatalogPinTests(unittest.TestCase):
    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("audit-header-names-projections", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "audit-header-names-projections")
        self.assertEqual(entry["since"], "r355")
        self.assertIn("tags", entry["summary"])
        self.assertIn("Grade", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 205 before r355; later rounds keep appending above it, so this
        # pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 206)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertTrue(callable(mindseam.audit_findings))
        self.assertTrue(callable(mindseam.scan_untrusted))


if __name__ == "__main__":
    unittest.main()
