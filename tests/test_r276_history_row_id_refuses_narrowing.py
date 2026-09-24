# -*- coding: utf-8 -*-
"""Round 276 guards: history --row-id refuses the narrowing/reorder flags.

--row-id N returns the single row at the 1-based index N, and its
r207 documentation promises it indexes the FULL history (1..N). But
the row-id detail branch runs AFTER every narrowing and reordering
step in mode_history — --filter, the --since/--until window,
--grep/--exclude, the r275-relocated head/tail truncation, and
--reverse — so it silently indexed the narrowed, possibly reordered
slice instead of the full log. ``history --row-id 2 --grep new``
returned row 2 of the grep survivors while the JSON still reported
``row_id: 2``; a host reading the docs expected row 2 of the whole
log. ``--row-id 5 --grep new`` reported "out of range (1..3)" against
the filtered count, not the real N. Every one exited 0.

This is the sibling of ``audit --at``, which refuses to compose with
the window (r188) and --baseline-write (r201) for exactly this reason
— the silent-wrong-at-exit-0 family (r188/r200/r201/r207) on
history's row-id locator. r276 refuses the combination with exit 2
naming the clash, before the destructive --keep rotation. The
renderers (--json / --human / --quiet / --count) still compose: they
present the located row without moving it (r197's precedence pin).
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


def _row(t, nxt, marker):
    return {"t": t, "next": nxt, "verified": 1, "open": 0,
            "marker": marker, "confidence": "strong", "verifier": "pytest",
            "risk": "low", "error": "", "outcome": "ok", "extra_steps": 0}


class RowIdRefusesNarrowingTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r276_")
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        now = int(time.time())
        # three OLD rows outside a recent window, three NEW rows inside.
        rows = [_row(now - 10000, "a: old zero", "DONE"),
                _row(now - 9000, "a: old one", "DONE"),
                _row(now - 8000, "a: old two", "DONE"),
                _row(now - 300, "a: new zero", "OPEN"),
                _row(now - 200, "a: new one", "OPEN"),
                _row(now - 100, "a: new two", "OPEN")]
        (self.ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _refused(self, *extra):
        r = invoke_cli(self.workspace, ["history", "--row-id", "2"] + list(extra))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertIn("--row-id 2 composes with none of", r.stderr)
        return r

    def test_grep_refused(self):
        self.assertIn("--grep", self._refused("--grep", "new").stderr)

    def test_exclude_refused(self):
        self.assertIn("--exclude", self._refused("--exclude", "old").stderr)

    def test_filter_refused(self):
        self.assertIn("--filter", self._refused("--filter", "marker=DONE").stderr)

    def test_since_refused(self):
        self.assertIn("--since", self._refused("--since", "3600").stderr)

    def test_until_refused(self):
        self.assertIn("--until", self._refused("--until", "3600").stderr)

    def test_head_refused(self):
        self.assertIn("--head", self._refused("--head", "3").stderr)

    def test_tail_refused(self):
        self.assertIn("--tail", self._refused("--tail", "3").stderr)

    def test_limit_refused(self):
        self.assertIn("--limit", self._refused("--limit", "3").stderr)

    def test_reverse_refused(self):
        self.assertIn("--reverse", self._refused("--reverse").stderr)

    def test_keep_refused(self):
        self.assertIn("--keep", self._refused("--keep", "1").stderr)

    def test_all_clashes_named_together(self):
        # Every narrowing flag present is named in one message, the way
        # the r201 --baseline-write refusal lists all its clashes.
        r = invoke_cli(self.workspace, ["history", "--row-id", "2",
                                        "--grep", "new", "--since", "3600",
                                        "--reverse"])
        self.assertEqual(r.returncode, 2, r.stderr)
        for flag in ("--grep", "--since", "--reverse"):
            self.assertIn(flag, r.stderr)

    def test_keep_refusal_leaves_file_unrotated(self):
        # The refusal happens before the destructive --keep rotation, the
        # way the r207 locator refusal does. The on-disk log is intact.
        invoke_cli(self.workspace, ["history", "--row-id", "2", "--keep", "1"])
        rows = json.loads(
            (self.ledger / "history.json").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 6)

    def test_out_of_range_row_id_still_loses_to_the_clash(self):
        # The combination is invalid as a combination before the row-id's
        # own range check matters (r201/r207 precedent): a filtered count
        # never gets to answer "out of range".
        r = invoke_cli(self.workspace, ["history", "--row-id", "99",
                                        "--grep", "new"])
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("composes with none of", r.stderr)
        self.assertNotIn("out of range", r.stderr)

    def test_refusal_is_on_stderr_only(self):
        r = self._refused("--grep", "new")
        self.assertEqual(r.stdout, "")
        self.assertTrue(r.stderr)


class RowIdAloneAndRenderersStillComposeTests(unittest.TestCase):
    """The fix narrows nothing that already worked."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r276b_")
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        now = int(time.time())
        rows = [_row(now - 10000, "a: old zero", "DONE"),
                _row(now - 9000, "a: old one", "DONE"),
                _row(now - 8000, "a: old two", "DONE"),
                _row(now - 300, "a: new zero", "OPEN"),
                _row(now - 200, "a: new one", "OPEN"),
                _row(now - 100, "a: new two", "OPEN")]
        (self.ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_row_id_alone_indexes_the_full_log(self):
        # Row 2 of the full six-row log is "a: old one" — NOT row 2 of
        # any filtered subset. This is the contract the guard defends.
        r = invoke_cli(self.workspace, ["history", "--row-id", "2", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["row_id"], 2)
        self.assertEqual(payload["row"]["next"], "a: old one")

    def test_row_id_with_json_composes(self):
        r = invoke_cli(self.workspace, ["history", "--row-id", "2", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_row_id_with_human_composes(self):
        r = invoke_cli(self.workspace, ["history", "--row-id", "2", "--human"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_row_id_with_quiet_composes(self):
        # r197's before-every-render precedence pin, untouched.
        r = invoke_cli(self.workspace, ["history", "--row-id", "2", "--quiet"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_row_id_with_count_composes(self):
        r = invoke_cli(self.workspace, ["history", "--row-id", "2", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_narrowing_flags_alone_still_work(self):
        # The guard only fires when --row-id is present. Each narrowing
        # flag on its own is unaffected.
        for extra in (["--grep", "new"], ["--since", "3600"], ["--head", "2"],
                      ["--tail", "2"], ["--reverse"], ["--filter", "marker=OPEN"]):
            r = invoke_cli(self.workspace, ["history"] + extra)
            self.assertEqual(r.returncode, 0, (extra, r.stderr))


class CatalogTests(unittest.TestCase):

    def _since_ints(self):
        return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]

    def test_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-row-id-refuses-narrowing", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-row-id-refuses-narrowing")
        self.assertEqual(entry["since"], "r276")
        self.assertTrue(entry["default"])

    def test_r276_is_the_highest_round(self):
        # The newest round owns the exact ``max == NNN`` head; it retires
        # to a ``>=`` floor once its successor lands (r277 did).
        self.assertGreaterEqual(max(self._since_ints()), 276)

    def test_catalog_grew_to_127(self):
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 127)

    def test_recent_window_is_97(self):
        recent = [i for i in self._since_ints() if i >= 170]
        self.assertGreaterEqual(len(recent), 97)


if __name__ == "__main__":
    unittest.main()
