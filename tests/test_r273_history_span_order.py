# -*- coding: utf-8 -*-
"""Round 273: ``history --span`` reports the window's true time extent
regardless of row order, instead of a 0-second lie under ``--reverse``.

r272 pivoted from the exhausted untrusted-framing family to a
slicing-correctness bug on history's window selectors; r273 stays on
correctness but on a different operator — a ``max(0, ...)`` clamp that
lied when the rows were reordered.

``history --span`` borrows ``git log --stat`` / ``journalctl
--list-boots``: a one-line summary of the surviving window's first seam,
last seam and the duration between them. The endpoints were read
positionally::

    first_t = int(hist[0].get("t") or 0)
    last_t = int(hist[-1].get("t") or 0)
    duration = max(0, last_t - first_t)

The default walk is append order (oldest first), so ``hist[0]`` is the
earliest and ``hist[-1]`` the latest and the subtraction is positive. But
``--span`` composes with ``--reverse`` (``git log --reverse``, applied a
few lines up as ``hist[::-1]``), which walks the same rows newest-first;
that swapped ``hist[0]`` / ``hist[-1]``, made ``last_t - first_t``
negative, and the ``max(0, ...)`` floor reported ``Duration: 0 seconds``
for a window that plainly spanned time.

LIVE DEFECT (``history`` with a three-row ``history.json`` spanning 9000
seconds): ``--span`` printed ``Duration: 9000 seconds`` but ``--span
--reverse`` printed ``Duration: 0 seconds`` over the identical rows, and
``--span --json --reverse`` reported ``first`` 1009000 / ``last`` 1000000
/ ``duration_seconds`` 0. A hand-written ``history.json`` whose rows are
not in ascending ``t`` hit the same lie without ``--reverse`` at all.

The span is the time EXTENT of the window — an interval that reordering
the rows must not change. The fix reads the endpoints from the window's
timestamps with ``min()`` / ``max()`` and drops the sign-swallowing floor
(``min``/``max`` make the difference provably non-negative), so ``--span``
is order-invariant, the earliest / latest labels are correct under any
row order, and every non-reversed pin is byte-identical because append
order already had ``hist[0] == min`` and ``hist[-1] == max``.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from _controller_helper import invoke_cli

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam

class HistorySpanOrderTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r273_")
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        self.history = self.ledger / "history.json"
        # Three rows in append order (ascending ``t``) spanning 9000s.
        # The on-disk root is a bare LIST of row dicts (read_history
        # requires it), not a {"rows": [...]} wrapper.
        self._write([
            {"t": 1000000, "next": "a: first", "verified": 1, "open": 0},
            {"t": 1000500, "next": "a: middle", "verified": 2, "open": 0},
            {"t": 1009000, "next": "a: last", "verified": 3, "open": 0},
        ])

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _write(self, rows):
        self.history.write_text(json.dumps(rows), encoding="utf-8")

    def _span(self, *flags):
        r = invoke_cli(self.workspace, ["history", "--span", "--json", *flags])
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["span"]

    def test_span_default_reports_full_duration(self):
        self.assertEqual(self._span()["duration_seconds"], 9000)

    def test_span_json_first_is_min_last_is_max(self):
        span = self._span()
        self.assertEqual(span["first"], 1000000)
        self.assertEqual(span["last"], 1009000)
        self.assertEqual(span["rows"], 3)

    def test_span_reverse_matches_default_duration(self):
        # The regression: --reverse flips hist[0]/hist[-1]; the old
        # positional endpoints plus max(0, ...) reported 0 seconds.
        self.assertEqual(self._span("--reverse")["duration_seconds"], 9000)

    def test_span_reverse_json_is_identical_to_default(self):
        # --reverse only changes row WALK order; the span is an interval,
        # so reordering must not change any of its fields.
        self.assertEqual(self._span("--reverse"), self._span())

    def test_span_reverse_first_le_last(self):
        span = self._span("--reverse")
        self.assertLessEqual(span["first"], span["last"])
        self.assertEqual(span["first"], 1000000)
        self.assertEqual(span["last"], 1009000)

    def test_span_reverse_text_duration_matches(self):
        default = invoke_cli(self.workspace, ["history", "--span"])
        reverse = invoke_cli(self.workspace, ["history", "--span", "--reverse"])
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertEqual(reverse.returncode, 0, reverse.stderr)
        self.assertIn("Duration:   9000 seconds", default.stdout)
        self.assertIn("Duration:   9000 seconds", reverse.stdout)

    def test_out_of_order_history_uses_extremes(self):
        # A hand-written history.json whose rows are not ascending hit the
        # same lie without --reverse; min/max fix it there too.
        self._write([
            {"t": 1009000, "next": "a: c", "verified": 3, "open": 0},
            {"t": 1000000, "next": "a: a", "verified": 1, "open": 0},
            {"t": 1000500, "next": "a: b", "verified": 2, "open": 0},
        ])
        span = self._span()
        self.assertEqual(span["first"], 1000000)
        self.assertEqual(span["last"], 1009000)
        self.assertEqual(span["duration_seconds"], 9000)

    def test_span_duration_never_negative(self):
        # Whatever the order, min <= max, so the duration is >= 0.
        self._write([
            {"t": 500, "next": "a: y", "verified": 1, "open": 0},
            {"t": 100, "next": "a: x", "verified": 2, "open": 0},
        ])
        self.assertGreaterEqual(self._span()["duration_seconds"], 0)
        self.assertEqual(self._span("--reverse")["duration_seconds"], 400)

    def test_single_row_window_zero_duration(self):
        span = self._span("--head", "1")
        self.assertEqual(span["rows"], 1)
        self.assertEqual(span["duration_seconds"], 0)

    def test_empty_history_says_no_rows(self):
        # Contract preserved: a window that matches nothing is span None,
        # not a zero-second span as if time had elapsed.
        r = invoke_cli(self.workspace, ["history", "--span", "--json",
                                        "--head", "0"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIsNone(json.loads(r.stdout)["span"])
        r = invoke_cli(self.workspace, ["history", "--span", "--head", "0"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no rows", r.stdout)

    def test_grep_span_narrows_first(self):
        # "How long did the TODO burst last": --grep narrows the window,
        # --span measures only the surviving rows.
        self._write([
            {"t": 2000000000, "next": "a: TODO cache", "verified": 1, "open": 0},
            {"t": 2000000050, "next": "a: fix typo", "verified": 2, "open": 0},
            {"t": 2000000100, "next": "a: TODO dead", "verified": 3, "open": 0},
        ])
        span = self._span("--grep", "TODO")
        self.assertEqual(span["rows"], 2)
        self.assertEqual(span["duration_seconds"], 100)

    def test_grep_span_reverse_matches_grep_span(self):
        self._write([
            {"t": 2000000000, "next": "a: TODO cache", "verified": 1, "open": 0},
            {"t": 2000000050, "next": "a: fix typo", "verified": 2, "open": 0},
            {"t": 2000000100, "next": "a: TODO dead", "verified": 3, "open": 0},
        ])
        self.assertEqual(self._span("--grep", "TODO", "--reverse"),
                         self._span("--grep", "TODO"))

    def test_head_span_is_order_invariant(self):
        # --head keeps the first two rows (t 1000000, 1000500 -> 500s);
        # --reverse keeps the last two (t 1000500, 1009000 -> 8500s) but
        # the span of each surviving set is order-invariant within itself.
        self.assertEqual(self._span("--head", "2")["duration_seconds"], 500)


class HistorySpanOrderSourceTests(unittest.TestCase):
    """The fix reads the endpoints from min/max, not positional rows."""

    def _src(self):
        import inspect
        return inspect.getsource(mindseam.mode_history)

    def test_endpoints_use_min_max(self):
        src = self._src()
        self.assertIn("span_times", src)
        self.assertIn("min(span_times)", src)
        self.assertIn("max(span_times)", src)

    def test_sign_swallowing_clamp_removed(self):
        # The old floor hid the negative difference; it must be gone so a
        # regression to positional endpoints cannot be masked again.
        self.assertNotIn("max(0, last_t - first_t)", self._src())


class HistorySpanOrderCatalogTests(unittest.TestCase):

    def _since_ints(self):
        return [int(e["since"].lstrip("r"))
                for e in mindseam._FEATURE_CATALOG]

    def test_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-span-order", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-span-order")
        self.assertEqual(entry["since"], "r273")
        self.assertIn("--reverse", entry["summary"])
        self.assertIn("min", entry["summary"])

    def test_r273_is_present_and_not_the_last_word(self):
        # The newest round owns the exact ``max == NNN`` head; once its
        # successor (r274) landed, r273 retires to a ``>=`` floor.
        self.assertGreaterEqual(max(self._since_ints()), 273)

    def test_catalog_grew_to_at_least_124(self):
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 124)

    def test_recent_window_is_at_least_94(self):
        recent = [i for i in self._since_ints() if i >= 170]
        self.assertGreaterEqual(len(recent), 94)


if __name__ == "__main__":
    unittest.main()

