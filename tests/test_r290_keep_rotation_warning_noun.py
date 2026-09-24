# -*- coding: utf-8 -*-
"""r290 — the history --keep failed-rotation warning agrees noun with count.

r214 gave the destructive ``history --keep`` rotation an honesty
branch: when ``atomic_write_text`` cannot persist the truncated
history, the run must NOT present the truncated view. It keeps the
full in-memory list and says so on stderr:

    WARNING: could not rotate history.json — disk full
      the on-disk history is unchanged; this run reports the full N rows.

That warning hardcoded the plural stem ``"reports the full %d rows."
% len(hist)``, so a single-row history whose rotation write fails read
"reports the full 1 rows." — a singular/plural agreement hole on the
same family as r281-r289, this time on a stderr WARNING attached to an
I/O-failure branch (not a happy-path human or machine face).

Reachability (deterministic, no timing): a one-row ledger and
``history --keep 0`` satisfy the ``len(hist) > keep_n`` guard
(``1 > 0``), so the rotation write is attempted; with
``atomic_write_text`` monkeypatched to fail on history.json the run
falls into the honesty branch with ``len(hist) == 1``.

Probe (before the fix): with a 1-row history and a failing
``atomic_write_text``, ``history --keep 0 --count`` printed ``1`` on
stdout and its last stderr line read
"  the on-disk history is unchanged; this run reports the full
1 rows." — the buggy singular. After the fix the same run reads
"...the full 1 row." while a 5-row/``--keep 2`` failure still reads
"...the full 5 rows."
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


def _since_ints():
    return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]


def _rows(n):
    return [{
        "t": i, "next": "a: x%d" % i, "verified": i, "open": 0,
        "marker": "DONE", "confidence": "strong",
        "verifier": "pytest", "risk": "low",
        "error": "", "outcome": "ok", "extra_steps": 0,
    } for i in range(1, n + 1)]


class _Base(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r290_")
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        self.history = self.ledger / "history.json"
        self._orig = mindseam.atomic_write_text

    def tearDown(self):
        mindseam.atomic_write_text = self._orig
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _write_rows(self, n):
        self.history.write_text(json.dumps(_rows(n)), encoding="utf-8")

    def _fail_history_writes(self):
        orig = self._orig

        def failing(path, text):
            if str(path).endswith("history.json"):
                return "disk full"
            return orig(path, text)
        mindseam.atomic_write_text = failing

    def _rotate_warning_line(self, keep, n):
        self._write_rows(n)
        self._fail_history_writes()
        r = invoke_cli(self.workspace,
                       ["history", "--keep", str(keep), "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stderr.strip().splitlines()[-1]


class KeepRotationWarningNounTests(_Base):
    """The failed-rotation warning pluralizes the row count."""

    def test_single_row_failure_is_singular(self):
        line = self._rotate_warning_line(keep=0, n=1)
        self.assertTrue(line.endswith("reports the full 1 row."), line)

    def test_single_row_has_no_lazy_plural(self):
        line = self._rotate_warning_line(keep=0, n=1)
        self.assertNotIn("1 rows", line)

    def test_two_rows_stay_plural(self):
        line = self._rotate_warning_line(keep=1, n=2)
        self.assertTrue(line.endswith("reports the full 2 rows."), line)

    def test_ten_rows_stay_plural(self):
        line = self._rotate_warning_line(keep=3, n=10)
        self.assertTrue(line.endswith("reports the full 10 rows."), line)

    def test_warning_header_still_present(self):
        # The r214 two-line contract: the WARNING header is unchanged;
        # only the second line's noun agreement moved.
        self._write_rows(1)
        self._fail_history_writes()
        r = invoke_cli(self.workspace, ["history", "--keep", "0", "--count"])
        self.assertIn("WARNING: could not rotate history.json — disk full",
                      r.stderr)


class KeepRotationHonestyPreservedTests(_Base):
    """r214's honesty contract is untouched by the noun fix."""

    def test_failed_write_reports_full_count_not_truncated(self):
        # r214: a failed rotation keeps the full list; --count prints
        # the full len, not the (would-be) truncated 1.
        self._write_rows(10)
        self._fail_history_writes()
        r = invoke_cli(self.workspace, ["history", "--keep", "3", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "10")

    def test_negative_keep_still_refused(self):
        # r214: negative --keep refuses with exit 2, not a silent no-op.
        self._write_rows(3)
        r = invoke_cli(self.workspace, ["history", "--keep", "-1", "--count"])
        self.assertEqual(r.returncode, 2, r.stderr)

    def test_single_row_disk_untouched_after_failed_rotation(self):
        # The on-disk file is genuinely unchanged when the write fails.
        self._write_rows(1)
        self._fail_history_writes()
        invoke_cli(self.workspace, ["history", "--keep", "0", "--count"])
        on_disk = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertEqual(len(on_disk), 1)


class CatalogPinTests(_Base):
    def test_entry_present_since_r290_default_true(self):
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "keep-rotation-warning-agrees-noun")
        self.assertEqual(entry["since"], "r290")
        self.assertTrue(entry["default"])

    def test_r290_is_the_highest_round(self):
        self.assertEqual(max(_since_ints()), 290)

    def test_catalog_grew_to_141(self):
        self.assertEqual(len(mindseam._FEATURE_CATALOG), 141)

    def test_recent_window_is_111(self):
        recent = [n for n in _since_ints() if n >= 170]
        self.assertEqual(len(recent), 111)


if __name__ == "__main__":
    unittest.main()
