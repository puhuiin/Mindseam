# -*- coding: utf-8 -*-
"""Round 275 guards: history head/tail truncation runs AFTER the filters.

mode_history composes filters and selectors in a fixed sequence: --keep
rotation, --filter key=value, then head/tail truncation, then
--since/--until window, then --grep/--exclude, then --reverse. The
head/tail truncation ran ABOVE the since/until and grep/exclude filters,
so a positional selector sliced the RAW history and the filters then
dropped whatever the slice happened to grab.

``history --head 2 --since 30m`` borrows ``git log -n 2 --since`` /
``journalctl --since -n 2``, where the host means "the first two rows
WITHIN the window". Instead --head took the two OLDEST rows of the full
log (almost always outside a recent window) and --since dropped them,
returning an empty result at exit 0 for a query that had matching rows.
``--tail 2 --grep old`` did the same.

The tell it was an accidental split: ``--filter`` (also a filter) already
ran BEFORE truncation and composed correctly; only since/until and
grep/exclude were left on the wrong side. r275 moves the head/tail block
to run AFTER every filter and BEFORE --reverse, so each filter narrows
first, then the selector picks from the survivors, then --reverse flips
the presentation. --head/--tail alone are byte-identical because with no
filter the narrowed set is the full set.
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam
from _controller_helper import invoke_cli


class _HistoryFixture(unittest.TestCase):
    """Six rows: three OLD (outside a 1h window, marker DONE, 'old' in
    next) then three NEW (inside 1h, marker OPEN, 'new' in next), written
    in append order (oldest first)."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r275_")
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        self.history = self.ledger / "history.json"
        now = int(time.time())

        def row(t, nxt, marker):
            return {"t": t, "next": nxt, "verified": 1, "open": 0,
                    "marker": marker, "confidence": "strong",
                    "verifier": "pytest", "risk": "low",
                    "error": "", "outcome": "ok", "extra_steps": 0}

        self.rows = [
            row(now - 10000, "a: old zero", "DONE"),
            row(now - 9000, "a: old one", "DONE"),
            row(now - 8000, "a: old two", "DONE"),
            row(now - 300, "a: new zero", "OPEN"),
            row(now - 200, "a: new one", "OPEN"),
            row(now - 100, "a: new two", "OPEN"),
        ]
        self.history.write_text(json.dumps(self.rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _rows(self, *args):
        r = invoke_cli(self.workspace, list(args) + ["--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        return payload, [row.get("next") for row in payload["rows"]]


class TruncationAfterFiltersTests(_HistoryFixture):

    def test_head_within_since_window(self):
        # The pre-fix bug: --head 2 sliced the two OLDEST full rows and
        # --since 3600 then dropped them -> []. Now the window narrows to
        # the three NEW rows first, then --head 2 keeps the two oldest of
        # those.
        payload, nexts = self._rows("history", "--head", "2", "--since", "3600")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(nexts, ["a: new zero", "a: new one"])

    def test_tail_within_grep(self):
        # --tail 2 --grep old: grep keeps the three OLD rows, tail 2 keeps
        # the last two. Pre-fix this returned [] (tail sliced the newest
        # two rows, grep 'old' dropped them).
        payload, nexts = self._rows("history", "--tail", "2", "--grep", "old")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(nexts, ["a: old one", "a: old two"])

    def test_head_within_grep(self):
        payload, nexts = self._rows("history", "--head", "2", "--grep", "new")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(nexts, ["a: new zero", "a: new one"])

    def test_tail_within_since(self):
        payload, nexts = self._rows("history", "--tail", "2", "--since", "3600")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(nexts, ["a: new one", "a: new two"])

    def test_head_within_until(self):
        # --until 3600 keeps rows OLDER than 1h ago -> the three OLD rows;
        # --head 2 keeps the two oldest of those.
        payload, nexts = self._rows("history", "--head", "2", "--until", "3600")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(nexts, ["a: old zero", "a: old one"])

    def test_head_within_exclude(self):
        # --exclude old drops the three OLD rows, leaving the three NEW;
        # --head 2 keeps the first two.
        payload, nexts = self._rows("history", "--head", "2", "--exclude", "old")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(nexts, ["a: new zero", "a: new one"])

    def test_grep_and_head_never_exceed_matches(self):
        # A --head larger than the match set yields exactly the matches,
        # never a raw-slice leak of non-matching rows.
        payload, nexts = self._rows("history", "--head", "9", "--grep", "old")
        self.assertEqual(payload["history_count"], 3)
        self.assertEqual(nexts, ["a: old zero", "a: old one", "a: old two"])


class FilterStillBeforeTruncationTests(_HistoryFixture):

    def test_filter_narrows_before_head(self):
        # --filter ran before truncation pre-r275 (correct) and still
        # does: marker=OPEN keeps the three NEW rows, --head 2 keeps two.
        payload, nexts = self._rows(
            "history", "--filter", "marker=OPEN", "--head", "2")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(nexts, ["a: new zero", "a: new one"])

    def test_filter_then_tail(self):
        payload, nexts = self._rows(
            "history", "--filter", "marker=DONE", "--tail", "2")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(nexts, ["a: old one", "a: old two"])


class ReverseAfterTruncationTests(_HistoryFixture):

    def test_head_then_reverse(self):
        # --reverse is presentation, applied AFTER truncation: --head 2
        # keeps [old zero, old one], then --reverse flips to [old one,
        # old zero].
        payload, nexts = self._rows("history", "--head", "2", "--reverse")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(nexts, ["a: old one", "a: old zero"])

    def test_since_head_reverse_compose(self):
        payload, nexts = self._rows(
            "history", "--since", "3600", "--head", "2", "--reverse")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(nexts, ["a: new one", "a: new zero"])


class SelectorsAloneUnchangedTests(_HistoryFixture):

    def test_head_alone(self):
        payload, nexts = self._rows("history", "--head", "2")
        self.assertEqual(nexts, ["a: old zero", "a: old one"])

    def test_tail_alone(self):
        payload, nexts = self._rows("history", "--tail", "2")
        self.assertEqual(nexts, ["a: new one", "a: new two"])

    def test_tail_zero_empties(self):
        # r272 pin survives the reorder.
        payload, nexts = self._rows("history", "--tail", "0")
        self.assertEqual(payload["history_count"], 0)
        self.assertEqual(nexts, [])

    def test_head_zero_empties(self):
        payload, nexts = self._rows("history", "--head", "0")
        self.assertEqual(payload["history_count"], 0)
        self.assertEqual(nexts, [])

    def test_limit_alias_tails(self):
        # -n / --limit alias --tail; alone, unchanged.
        payload, nexts = self._rows("history", "--limit", "2")
        self.assertEqual(nexts, ["a: new one", "a: new two"])


class CatalogTests(unittest.TestCase):

    def _since_ints(self):
        return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]

    def test_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-truncation-after-filters", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-truncation-after-filters")
        self.assertEqual(entry["since"], "r275")
        self.assertIn("AFTER", entry["summary"])

    def test_r275_is_the_highest_round(self):
        # The newest round owns the exact ``max == NNN`` head; it retires
        # to a ``>=`` floor once its successor lands.
        self.assertEqual(max(self._since_ints()), 275)

    def test_catalog_grew_to_126(self):
        self.assertEqual(len(mindseam._FEATURE_CATALOG), 126)

    def test_recent_window_is_96(self):
        recent = [i for i in self._since_ints() if i >= 170]
        self.assertEqual(len(recent), 96)


if __name__ == "__main__":
    unittest.main()
