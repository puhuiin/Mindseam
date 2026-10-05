# -*- coding: utf-8 -*-
"""r356 — the clean line could not name the window that cleaned it.

r355 named the projections on the audit findings header, but the CLEAN
branch has no header — it answers in a single line — and the window
was unnamed there. Live before-fix, on a ledger whose full audit
answered "Grade: B (1 fresh item)" (goal-stale: 12 seams, none of
them re-anchoring the goal):

    audit                  ->  Grade: B, [G1] goal-stale, Net: 1
    audit --since 3600     ->  "Lean already. Ship."

That clean line is byte-identical to the clean answer an EMPTY history
gives with no flags at all — so the window that just made a finding
disappear was indistinguishable from a ledger that never had one. The
JSON face's history_window was always there; the clean line was the
lying half, and it is the only face a clean call answers with. The
same blindness applied to the tagged clean line: `audit --tag
next-stall --since 3600` answered "Lean on next-stall. Ship." with
the window unnamed.

The fix appends the window to the clean line's own parenthesis: the
tagged branch reads "Lean on X (last N s). Ship.", the bare branch
"Lean already (last N s). Ship." / "(older than N s)" — the r324
history wording again, on r355's principle that the same narrowing
says the same thing everywhere. --at names its slice already (r161)
and cannot compose with the window (r188), so its r161 literal stays
byte-identical; the r156 bare clean literal is unchanged when no
window was asked for.
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

LEAN = ("# Mindseam Workspace Ledger\n\n## Goal\ng\n\n## Core\n\n"
        "## Verified\n\n## Open\n\n## Next\n\n")
# A book with ledger-surface findings, all of which the --tag filter
# drops — the shape that reaches the clean-on-chosen branch.
FIVE_FINDINGS_TAGGED = (
    "# Mindseam Workspace Ledger\n\n## Goal\ng\n\n## Core\n"
    "- c1 — work\n- c2 — review\n- c3 — three\n\n"
    "## Verified\n\n## Open\n\n## Next\nbuild: the parser\n")


class CleanBranchBase(unittest.TestCase):
    def _workspace(self, rows_n, distinct=True, ledger=LEAN):
        ws = tempfile.mkdtemp()
        d = os.path.join(ws, ".mindseam")
        os.makedirs(d)
        with open(os.path.join(d, "WORKSPACE.md"), "w",
                  encoding="utf-8") as f:
            f.write(ledger)
        rows = [{"t": 1700000000 + i,
                 "next": ("dom%d: action %d" % (i % 4, i))
                 if distinct else "build: x",
                 "msg": "m%d" % i, "verified": 1, "open": 0}
                for i in range(rows_n)]
        with open(os.path.join(d, "history.json"), "w",
                  encoding="utf-8") as f:
            json.dump(rows, f)
        return ws

    def _clean(self, ws, *flags):
        r = invoke_cli(ws, ["audit", *flags])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout


class CleanWindowTests(CleanBranchBase):
    def test_no_flags_clean_literal_is_byte_identical(self):
        # r156, re-pinned: without a window the clean line is exactly
        # what it always was.
        self.assertEqual(self._clean(self._workspace(0)),
                         "Lean already. Ship.\n")

    def test_since_clean_names_the_window(self):
        # 12 seams with distinct nexts; the 3600 s window reaches back
        # to none of them, so goal-stale loses its evidence and the
        # audit goes lean — with the window named.
        self.assertEqual(self._clean(self._workspace(12), "--since", "3600"),
                         "Lean already (last 3600 s). Ship.\n")

    def test_until_clean_names_the_window(self):
        self.assertEqual(
            self._clean(self._workspace(0), "--until", "7200"),
            "Lean already (older than 7200 s). Ship.\n")

    def test_tagged_clean_names_the_window(self):
        self.assertEqual(
            self._clean(self._workspace(12), "--tag", "next-stall",
                        "--since", "3600"),
            "Lean on next-stall (last 3600 s). Ship.\n")

    def test_tagged_clean_without_window_is_unchanged(self):
        # r156's chosen-branch literal holds whenever NO window narrows:
        # a bare --tag on a book whose only findings belong to other
        # tags (the tag filter drops them) goes lean with no window to
        # name. A --since flag WOULD be named now — r356's point.
        ws = self._workspace(0, ledger=FIVE_FINDINGS_TAGGED)
        r = invoke_cli(ws, ["audit", "--tag", "next-stall"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "Lean on next-stall. Ship.\n")

    def test_the_before_fix_repro_now_distinguishes(self):
        # The heart of the round: a full audit that found goal-stale
        # and the windowed audit that found nothing must NOT answer
        # with the same bytes anymore.
        ws = self._workspace(12)
        full = invoke_cli(ws, ["audit"])
        self.assertIn("[G1] goal-stale", full.stdout)
        windowed = invoke_cli(ws, ["audit", "--since", "3600"])
        self.assertEqual(windowed.stdout,
                         "Lean already (last 3600 s). Ship.\n")
        self.assertNotEqual(full.stdout, windowed.stdout)

    def test_empty_history_with_window_still_names_it(self):
        # A window over an empty history is also a window, not a bare
        # clean audit.
        self.assertEqual(self._clean(self._workspace(0), "--since", "1"),
                         "Lean already (last 1 s). Ship.\n")


class NeighbouringGuardsTests(CleanBranchBase):
    def test_r161_at_clean_literal_untouched(self):
        # --at names its own slice and cannot compose with the window
        # (r188), so its r161 wording keeps standing alone.
        self.assertEqual(self._clean(self._workspace(12), "--at", "2"),
                         "Lean already (at seam 2 of 12). Ship.\n")

    def test_r188_at_and_window_still_refused(self):
        r = invoke_cli(self._workspace(12),
                       ["audit", "--at", "3", "--since", "100"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)

    def test_findings_header_still_names_the_window(self):
        # r355's clause on the findings path: --until keeps the old
        # rows in the window, goal-stale fires, and the r355 header
        # names the window above the grade.
        ws = self._workspace(12)
        r = invoke_cli(ws, ["audit", "--until", "7200"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0],
                         "── mindseam ─ audit (older than 7200 s)")
        self.assertIn("[G1] goal-stale", r.stdout)

    def test_json_history_window_still_discloses(self):
        r = invoke_cli(self._workspace(12), ["audit", "--json",
                                             "--since", "3600"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_window"]["since_seconds"], 3600)


class CatalogPinTests(unittest.TestCase):
    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("audit-clean-window-disclosed", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "audit-clean-window-disclosed")
        self.assertEqual(entry["since"], "r356")
        self.assertIn("Lean", entry["summary"])
        self.assertIn("window", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 206 before r356; later rounds keep appending above it, so this
        # pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 207)

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
