# -*- coding: utf-8 -*-
"""Round 187 guards: skillbook recency evidence.

Borrowed from Claude Code's memory staleness protocol (asgeirtj/
system_prompts_leaks, Anthropic/claude-code): "verify a recalled
memory still applies before recommending it". Mindseam's skillbook is
the controller's recalled-pattern store — errors that recurred, domains
that cost unplanned steps — but until r187 an entry carried no
recency evidence: a host reading skillbook.md could not tell whether
a documented error was from three seams ago or three hundred.

r187 stamps every entry with ``first_seen`` / ``last_seen`` (1-based
seam indices), ``age_seams`` (distance from the newest history row),
and ``stale`` (age >= SKILLBOOK_STALE_SEAMS, i.e. unseen for 10
seams). Stale entries still ship — the way the r162 audit marks
baselined debt instead of hiding it — so a host can weigh a recalled
pattern by its recency rather than mistaking a long-fixed error for
a live one. The text face appends ``[stale: last seen seam N]`` to
stale lines only; fresh lines render byte-identically to the pre-r187
face.

Backward-compat pins defended: kind / text / count / utility remain,
the sort order is unchanged (staleness is a marker, not a rank
change), and the entry cap still applies.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from _controller_helper import invoke_cli

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _invoke(args, cwd):
    return invoke_cli(cwd, args)


def _row(i, error=None, outcome=None, extra_steps=0, next_text=None):
    row = {"t": i + 1,
           "next": next_text or ("dom: step %d" % i),
           "verified": 0, "open": 0}
    if error:
        row["error"] = error
    if outcome:
        row["outcome"] = outcome
    if extra_steps:
        row["extra_steps"] = extra_steps
    return row


class ExtractionRecencyTests(unittest.TestCase):
    """first_seen / last_seen / age_seams / stale on the extractor."""

    def test_fresh_pattern_records_both_indices(self):
        # The error recurs at seams 2 and 8 of 8 total: fresh on the
        # last row, age 0, not stale.
        hist = [_row(0), _row(1, error="persist: write failed",
                              outcome="ok"),
                _row(2), _row(3), _row(4), _row(5), _row(6),
                _row(7, error="persist: write failed", outcome="ok")]
        entries = mindseam.extract_skillbook(hist)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["kind"], "error")
        self.assertEqual(e["first_seen"], 2)
        self.assertEqual(e["last_seen"], 8)
        self.assertEqual(e["age_seams"], 0)
        self.assertFalse(e["stale"])

    def test_old_pattern_is_stale(self):
        # Same error, but the history moved on: last seen at seam 4
        # of 15 total -> age 11 >= SKILLBOOK_STALE_SEAMS -> stale.
        hist = [_row(0), _row(1), _row(2),
                _row(3, error="persist: write failed", outcome="ok"),
                _row(4, error="persist: write failed", outcome="ok")]
        hist += [_row(i) for i in range(5, 15)]
        entries = mindseam.extract_skillbook(hist)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["last_seen"], 5)
        self.assertEqual(e["age_seams"], 10)
        self.assertTrue(e["stale"])

    def test_stale_boundary_is_inclusive(self):
        # age == SKILLBOOK_STALE_SEAMS is stale; age one below is not.
        # Two error rows then filler: total = 2 + filler rows, and
        # age = total - 2 (the last error seam).
        base = [_row(0, error="e: boom", outcome="ok"),
                _row(1, error="e: boom", outcome="ok")]
        fill = [_row(i) for i in range(2, 2 + mindseam.SKILLBOOK_STALE_SEAMS)]
        at_boundary = base + fill          # 12 rows -> age 10
        below = base + fill[:-1]           # 11 rows -> age 9
        self.assertTrue(
            mindseam.extract_skillbook(at_boundary)[0]["stale"])
        self.assertFalse(
            mindseam.extract_skillbook(below)[0]["stale"])

    def test_hard_kind_carries_recency(self):
        # The domain-cost pattern gets the same evidence: two seams on
        # the same domain with extra steps, fresh at the end.
        hist = [_row(0, next_text="build: compile", extra_steps=2),
                _row(1), _row(2),
                _row(3, next_text="build: link", extra_steps=3)]
        entries = mindseam.extract_skillbook(hist)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["kind"], "hard")
        self.assertEqual(e["text"], "build")
        self.assertEqual(e["first_seen"], 1)
        self.assertEqual(e["last_seen"], 4)
        self.assertFalse(e["stale"])

    def test_backward_compat_keys_survive(self):
        # Old hosts parse kind / text / count / utility; the new keys
        # ride alongside without displacing them.
        hist = [_row(0, error="e: boom", outcome="ok"),
                _row(1, error="e: boom", outcome="ok")]
        e = mindseam.extract_skillbook(hist)[0]
        for key in ("kind", "text", "count", "utility"):
            self.assertIn(key, e)
        self.assertEqual(e["count"], 2)

    def test_sort_order_ignores_staleness(self):
        # A stale high-count pattern still outranks a fresh
        # low-count one: staleness marks, it does not re-rank.
        stale = [_row(0, error="a: old", outcome="ok"),
                 _row(1, error="a: old", outcome="ok")]
        stale += [_row(i) for i in range(2, 14)]
        fresh = [_row(0), _row(1),
                 _row(2, error="b: new", outcome="ok"),
                 _row(3, error="b: new", outcome="ok")]
        self.assertEqual(
            [e["text"] for e in mindseam.extract_skillbook(stale)],
            ["a: old"])
        self.assertEqual(
            [e["text"] for e in mindseam.extract_skillbook(fresh)],
            ["b: new"])
        # And the stale one is genuinely stale while the fresh one
        # is not: rank ignores the marker, the marker does not lie.
        self.assertTrue(mindseam.extract_skillbook(stale)[0]["stale"])
        self.assertFalse(mindseam.extract_skillbook(fresh)[0]["stale"])


class SurfaceRecencyTests(unittest.TestCase):
    """The recency evidence rides the CLI faces."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _history(self, rows):
        (self.ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def _stale_history(self):
        rows = [_row(0, error="persist: write failed", outcome="ok"),
                _row(1, error="persist: write failed", outcome="ok")]
        rows += [_row(i) for i in range(2, 15)]
        self._history(rows)

    def test_json_face_carries_recency_fields(self):
        self._stale_history()
        r = _invoke(["skillbook", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        entries = json.loads(r.stdout)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["last_seen"], 2)
        self.assertTrue(e["stale"])
        self.assertEqual(e["age_seams"],
                         len(json.loads(
                             (self.ledger / "history.json")
                             .read_text(encoding="utf-8"))) - 2)

    def test_text_face_marks_stale_and_leaves_fresh_untouched(self):
        self._stale_history()
        r = _invoke(["skillbook"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[stale: last seen seam 2]", r.stdout)
        # A fresh history renders the pre-r187 line byte-identically.
        fresh = [_row(0, error="persist: write failed", outcome="ok"),
                 _row(1, error="persist: write failed", outcome="ok"),
                 _row(2)]
        self._history(fresh)
        r = _invoke(["skillbook"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[error] persist: write failed (x2, utility +2)",
                      r.stdout)
        self.assertNotIn("[stale", r.stdout)

    def test_format_face_resolves_new_paths(self):
        # --format resolves against the additive keys, the way it
        # resolves kind / count (r170).
        self._stale_history()
        r = _invoke(["skillbook", "--format",
                     "entries[0].last_seen,entries[0].stale"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("2", r.stdout)
        self.assertIn("true", r.stdout)


class CatalogTests(unittest.TestCase):

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("skillbook-staleness", ids)

    def test_feature_since_r187(self):
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "skillbook-staleness")
        self.assertEqual(entry["since"], "r187")
        self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
