# -*- coding: utf-8 -*-
"""Round 284: ``_humanize_seconds`` closes the [360, 365)-day dead zone,
so a span of 360-to-364 days reads "12 months" instead of "0 years".

r281-r283 pluralized the ``history --domains`` / ``--dedup`` / ``--span``
headers; r284 pivots off that family to a different class of bug — an
off-by-unit dead zone in the shared age humanizer. ``_humanize_seconds``
scales a raw second count through a units ladder (second, minute, hour,
day, month, year) and is the humanizer behind ``history --human`` (the
per-row "N ago" age), ``info --human`` (the "Last seam: N ago (long
gap)" line) and ``info --human --json`` (``human.gap_human``).

A "month" on this ladder is 30 days and a "year" is 365, so 12 months
(360 days) is five days short of a full year. The old code was::

    months = days // 30
    if months < 12:
        return "%d month%s" % (months, ...)
    years = days // 365
    return "%d year%s" % (years, ...)

At day 360 ``months`` is 12, so the ``months < 12`` guard falls through
to the year branch — but ``years = 360 // 365`` is still 0, so the span
rendered "0 years". The whole window [360, 365) days was a dead zone:
past the last month but before the first year, printing a literal zero.

LIVE DEFECT: a one-row ``history.json`` timed 361 days before now made
``history --human`` print "1  0 years ago" and ``info --human`` print
"Last seam: 0 years ago (long gap)".

The fix gates the month/year handoff on the year COUNT rather than the
month count: compute ``years = days // 365`` up front and hold the month
branch while ``years < 1``. Days >= 365 are byte-identical (years >= 1),
days < 360 never reached the year branch anyway, and only the [360, 365)
dead zone changes — now "12 months" rather than "0 years".
"""

import json
import os
import shutil
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

DAY = 86400


class HumanizeYearBoundaryTests(unittest.TestCase):
    """Direct-function pins on the units ladder around the year edge."""

    def _h(self, days):
        return mindseam._humanize_seconds(days * DAY)

    def test_dead_zone_start_is_twelve_months(self):
        # Day 360 was the first day of the old "0 years" dead zone.
        self.assertEqual(self._h(360), "12 months")

    def test_dead_zone_interior_is_twelve_months(self):
        self.assertEqual(self._h(361), "12 months")
        self.assertEqual(self._h(364), "12 months")

    def test_no_zero_years_anywhere_in_the_dead_zone(self):
        for d in range(360, 365):
            self.assertNotIn("0 year", self._h(d),
                             "day %d still prints a zero year" % d)

    def test_day_before_dead_zone_is_eleven_months(self):
        # 359 // 30 == 11: unchanged by the fix.
        self.assertEqual(self._h(359), "11 months")

    def test_first_full_year_is_one_year(self):
        # 365 // 365 == 1: the year branch now fires exactly here.
        self.assertEqual(self._h(365), "1 year")

    def test_year_is_singular_at_exactly_one(self):
        self.assertEqual(self._h(366), "1 year")
        self.assertNotIn("1 years", self._h(366))

    def test_two_years_are_plural(self):
        self.assertEqual(self._h(730), "2 years")

    def test_month_branch_below_dead_zone_unchanged(self):
        # Every value the old code already got right stays byte-identical.
        self.assertEqual(self._h(30), "1 month")
        self.assertEqual(self._h(60), "2 months")
        self.assertEqual(self._h(90), "3 months")
        self.assertEqual(self._h(300), "10 months")

    def test_sub_month_ladder_unchanged(self):
        self.assertEqual(self._h(1), "1 day")
        self.assertEqual(self._h(29), "29 days")
        self.assertEqual(mindseam._humanize_seconds(0), "0 seconds")
        self.assertEqual(mindseam._humanize_seconds(3600), "1 hour")

    def test_none_and_future_preserved(self):
        self.assertIsNone(mindseam._humanize_seconds(None))
        self.assertEqual(mindseam._humanize_seconds(-1), "in the future")

    def test_monotonic_no_backward_step_across_the_edge(self):
        # A larger span must never humanize to a SMALLER-sounding label;
        # the dead zone broke this by dropping "11 months" -> "0 years".
        seq = [self._h(d) for d in (359, 360, 364, 365, 366)]
        self.assertEqual(
            seq, ["11 months", "12 months", "12 months", "1 year", "1 year"])


class _LedgerBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r284_")
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        self.history = self.ledger / "history.json"

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _write_age_days(self, days):
        # The on-disk root is a bare LIST of row dicts; age is measured
        # against real wall-clock now, so anchor the row that many days
        # back from time.time().
        now = int(time.time())
        self.history.write_text(json.dumps(
            [{"t": now - days * DAY, "next": "a: x",
              "verified": 1, "open": 0, "msg": "release"}]),
            encoding="utf-8")


class HistoryHumanSurfaceTests(_LedgerBase):

    def test_history_human_shows_twelve_months_not_zero_years(self):
        self._write_age_days(361)
        r = invoke_cli(self.workspace, ["history", "--human"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("12 months ago", r.stdout)
        self.assertNotIn("0 years ago", r.stdout)

    def test_history_human_eleven_months_still_fine(self):
        self._write_age_days(359)
        r = invoke_cli(self.workspace, ["history", "--human"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("11 months ago", r.stdout)


class InfoHumanSurfaceTests(_LedgerBase):

    def test_info_human_last_seam_line_reads_twelve_months(self):
        self._write_age_days(361)
        r = invoke_cli(self.workspace, ["info", "--human"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Last seam: 12 months ago", r.stdout)
        self.assertNotIn("0 years ago", r.stdout)

    def test_info_human_json_gap_human_reads_twelve_months(self):
        self._write_age_days(361)
        r = invoke_cli(self.workspace, ["info", "--human", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        gap_human = payload["human"]["gap_human"]
        self.assertIn("12 months", gap_human)
        self.assertNotIn("0 years", gap_human)

    def test_info_human_first_full_year_reads_one_year(self):
        self._write_age_days(366)
        r = invoke_cli(self.workspace, ["info", "--human"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Last seam: 1 year ago", r.stdout)


class CatalogTests(unittest.TestCase):

    def _since_ints(self):
        return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]

    def test_entry_present(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "humanize-year-boundary"),
                     None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r284")
        self.assertTrue(entry["default"])

    def test_r284_is_the_highest_round(self):
        # The newest round owns the exact ``max == NNN`` head; it retired
        # to a ``>=`` floor once its successor (r285) landed.
        self.assertGreaterEqual(max(self._since_ints()), 284)

    def test_catalog_grew_to_135(self):
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 135)

    def test_recent_window_is_105(self):
        recent = [i for i in self._since_ints() if i >= 170]
        self.assertGreaterEqual(len(recent), 105)


if __name__ == "__main__":
    unittest.main()
