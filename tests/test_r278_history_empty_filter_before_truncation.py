# -*- coding: utf-8 -*-
"""Round 278 guards: history --empty filters BEFORE head/tail truncation.

r275 moved head/tail truncation to run AFTER every content filter
(--since/--until/--grep/--exclude/--filter), so a positional selector
picks from the rows that SURVIVED the filters -- the ``git log --grep X
-n 2`` / ``journalctl --since -n 2`` order.

``--empty`` is itself a content filter (keep rows whose next action is
blank, the sibling of --grep/--exclude, as its own docstring says: "a
post-filter on the existing filter chain, so --grep, --since and the
rest all narrow the candidate set before the empty check runs, the way
--exclude does"). But its filter step lived in the renderer block BELOW
the relocated truncation, so the empty predicate ran truncate-then-filter
-- the exact order r275 had just moved the other filters off of.

The tell: ``history --empty --tail 2`` on a window whose empty rows sit
at the OLD end sliced the two NEWEST rows (both non-empty) and then kept
the empties among them -> "no empty-next rows" at exit 0, the r275 lie
(an empty result for a query that plainly had matches). r278 lifts the
empty predicate into the filter chain right after --grep/--exclude, so
head/tail slices the rows that survived the empty check, order-invariant
to where the empty rows sit.
"""

import json
import os
import shutil
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


class _EmptyFixture(unittest.TestCase):
    """Five rows in append order (oldest first): three empty-next rows at
    the OLD end (t 1000/2000/3000), two with a next action at the NEW end
    (t 4000/5000). The empties sit at the old end so head/tail truncation
    on the RAW window would slice past them."""

    ROWS = [
        {"t": 1000, "next": "", "verified": 1, "open": 0},
        {"t": 2000, "next": "", "verified": 1, "open": 0},
        {"t": 3000, "next": "", "verified": 1, "open": 0},
        {"t": 4000, "next": "dom: ship", "verified": 1, "open": 0},
        {"t": 5000, "next": "dom: test", "verified": 1, "open": 0},
    ]

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r278_")
        ledger = Path(self.workspace) / ".mindseam"
        ledger.mkdir(parents=True, exist_ok=True)
        (ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        (ledger / "history.json").write_text(
            json.dumps(self.ROWS), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _empty_json(self, *extra):
        r = invoke_cli(self.workspace, ["history", "--empty", "--json", *extra])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        return payload, [row.get("t") for row in payload["rows"]]


class EmptyFilterBeforeTruncationTests(_EmptyFixture):

    def test_empty_alone_returns_all_three(self):
        payload, ts = self._empty_json()
        self.assertEqual(payload["history_count"], 3)
        self.assertEqual(ts, [1000, 2000, 3000])

    def test_empty_with_tail_keeps_last_of_the_empties(self):
        # Pre-fix: --tail 2 sliced the two NEWEST rows (t 4000/5000, both
        # non-empty), then the empty check dropped them -> 0 rows. Now the
        # empty filter runs first (3 rows), then --tail 2 keeps the last
        # two empties (t 2000/3000).
        payload, ts = self._empty_json("--tail", "2")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(ts, [2000, 3000])

    def test_empty_with_head_keeps_first_of_the_empties(self):
        payload, ts = self._empty_json("--head", "2")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(ts, [1000, 2000])

    def test_empty_with_limit_alias_tails(self):
        # -n / --limit alias --tail; the empty filter runs first.
        payload, ts = self._empty_json("--limit", "2")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(ts, [2000, 3000])

    def test_empty_tail_larger_than_matches_never_leaks(self):
        # A --tail larger than the empty set yields exactly the empties,
        # never a raw-slice leak of the non-empty rows.
        payload, ts = self._empty_json("--tail", "9")
        self.assertEqual(payload["history_count"], 3)
        self.assertEqual(ts, [1000, 2000, 3000])

    def test_empty_head_zero_empties_the_window(self):
        # r272 zero-window pin composes: 0 rows after the empty filter.
        payload, ts = self._empty_json("--head", "0")
        self.assertEqual(payload["history_count"], 0)
        self.assertEqual(ts, [])

    def test_empty_tail_zero_empties_the_window(self):
        payload, ts = self._empty_json("--tail", "0")
        self.assertEqual(payload["history_count"], 0)
        self.assertEqual(ts, [])

    def test_empty_text_face_tail_reports_two(self):
        # The text renderer reads the same pre-filtered, truncated hist.
        r = invoke_cli(self.workspace, ["history", "--empty", "--tail", "2"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("2 empty-next rows", r.stdout)


class EmptyOrderInvariantTests(unittest.TestCase):
    """The non-empty rows now at the HEAD: --empty --head 2 must still find
    the empties, proving the fix is invariant to where the empties sit (the
    pre-fix --head path looked correct only because the empties happened to
    be at the head)."""

    ROWS = [
        {"t": 1000, "next": "dom: ship", "verified": 1, "open": 0},
        {"t": 2000, "next": "dom: test", "verified": 1, "open": 0},
        {"t": 3000, "next": "", "verified": 1, "open": 0},
        {"t": 4000, "next": "", "verified": 1, "open": 0},
        {"t": 5000, "next": "", "verified": 1, "open": 0},
    ]

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r278b_")
        ledger = Path(self.workspace) / ".mindseam"
        ledger.mkdir(parents=True, exist_ok=True)
        (ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        (ledger / "history.json").write_text(
            json.dumps(self.ROWS), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_head_finds_empties_past_the_nonempty_head(self):
        r = invoke_cli(self.workspace,
                       ["history", "--empty", "--head", "2", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual([row.get("t") for row in payload["rows"]],
                         [3000, 4000])

    def test_tail_finds_last_empties(self):
        r = invoke_cli(self.workspace,
                       ["history", "--empty", "--tail", "2", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual([row.get("t") for row in payload["rows"]],
                         [4000, 5000])


class EmptyComposesWithFiltersTests(_EmptyFixture):

    def test_empty_after_grep(self):
        # --grep runs before --empty (both filters), then no truncation:
        # only the empty rows whose next/msg matched. None of the empties
        # carry 'ship', so the empty set survives grep untouched only when
        # grep also matches; here grep 'dom' matches the non-empty rows,
        # which the empty filter then drops -> 0.
        r = invoke_cli(self.workspace,
                       ["history", "--empty", "--grep", "dom", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["history_count"], 0)

    def test_empty_reverse_after_truncation(self):
        # --reverse is presentation, applied AFTER truncation: --tail 2
        # keeps [t2000, t3000], --reverse flips to [t3000, t2000].
        r = invoke_cli(self.workspace, ["history", "--empty", "--tail", "2",
                                        "--reverse", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual([row.get("t") for row in payload["rows"]],
                         [3000, 2000])

    def test_empty_json_untrusted_map_still_present(self):
        # r277 pin survives the relocation: the machine face still carries
        # the untrusted map over the surviving rows; a clean window -> {}.
        payload, _ = self._empty_json("--tail", "2")
        self.assertEqual(payload["untrusted"], {})


class CatalogTests(unittest.TestCase):

    def _since_ints(self):
        return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]

    def test_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-empty-filter-before-truncation", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-empty-filter-before-truncation")
        self.assertEqual(entry["since"], "r278")
        self.assertTrue(entry["default"])

    def test_r278_is_the_highest_round(self):
        # The newest round owns the exact ``max == NNN`` head; it retires
        # to a ``>=`` floor once its successor lands (r279 landed).
        self.assertGreaterEqual(max(self._since_ints()), 278)

    def test_catalog_grew_to_129(self):
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 129)

    def test_recent_window_is_99(self):
        recent = [i for i in self._since_ints() if i >= 170]
        self.assertGreaterEqual(len(recent), 99)


if __name__ == "__main__":
    unittest.main()
