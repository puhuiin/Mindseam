# -*- coding: utf-8 -*-
"""Round 283: ``history --span`` pluralizes both nouns of its Duration
line, so a one-second window reads "1 second" and a one-row window reads
"across 1 row" instead of "1 seconds" / "1 rows".

r281 pluralized ``history --domains`` and r282 pluralized ``history
--dedup``; r283 closes the last member of that family on a different
operator. ``history --span`` (borrowed from ``git log --stat`` /
``journalctl --list-boots``) prints a one-line window summary — first
seam, last seam, and the duration between them. r273 already fixed the
duration to be order-invariant (``min``/``max`` endpoints, raw
``duration_seconds`` in JSON). But the text line was::

    print("  Duration:   %d seconds across %d rows" % (duration, len(hist)))

Both nouns are hardcoded plural, so a one-second window prints "1
seconds" and a one-row window prints "across 1 rows". It is additionally
the only human-facing duration in the tool that does not route through
``_humanize_seconds`` (which pluralizes and scales), so it alone kept the
raw-plural form every sibling had already dropped.

LIVE DEFECT: a two-row ``history.json`` one second apart printed
``Duration:   1 seconds across 2 rows``; a one-row ``history.json``
printed ``Duration:   0 seconds across 1 rows``.

The fix pluralizes both nouns with the same ``"" if n == 1 else "s"``
idiom the siblings use — "1 second across 2 rows", "0 seconds across 1
row". ``duration`` stays raw seconds, so r273's text pin ("9000 seconds")
and the JSON ``duration_seconds`` are byte-identical; only the missing
singular is added, and the ``--json`` face never carried this line.
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


class _SpanBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r283_")
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

    def _write(self, rows):
        # The on-disk root is a bare LIST of row dicts (read_history
        # requires it), not a {"rows": [...]} wrapper.
        self.history.write_text(json.dumps(rows), encoding="utf-8")

    def _span_text(self, *flags):
        r = invoke_cli(self.workspace, ["history", "--span", *flags])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def _duration_line(self, *flags):
        for line in self._span_text(*flags).splitlines():
            if "Duration:" in line:
                return line
        self.fail("no Duration line in --span output")


class SpanDurationPluralizationTests(_SpanBase):

    def test_one_second_window_is_singular_second(self):
        # Two rows one second apart: duration 1, so "1 second".
        self._write([{"t": 100, "next": "a: x"},
                     {"t": 101, "next": "a: y"}])
        line = self._duration_line()
        self.assertIn("1 second across", line)
        self.assertNotIn("1 seconds", line)

    def test_one_row_window_is_singular_row(self):
        # A single row: duration 0 (first == last), one row: "1 row".
        self._write([{"t": 500, "next": "a: solo"}])
        line = self._duration_line()
        self.assertIn("across 1 row", line)
        self.assertNotIn("1 rows", line)

    def test_zero_seconds_stays_plural(self):
        # English says "0 seconds"; n == 0 keeps the plural "s".
        self._write([{"t": 500, "next": "a: solo"}])
        line = self._duration_line()
        self.assertIn("0 seconds across", line)

    def test_many_seconds_are_plural(self):
        self._write([{"t": 1000000, "next": "a: first"},
                     {"t": 1009000, "next": "a: last"}])
        line = self._duration_line()
        self.assertIn("9000 seconds across", line)

    def test_many_rows_are_plural(self):
        self._write([{"t": 1000000, "next": "a: first"},
                     {"t": 1000500, "next": "a: mid"},
                     {"t": 1009000, "next": "a: last"}])
        line = self._duration_line()
        self.assertIn("across 3 rows", line)

    def test_both_singular_are_never_both_present_at_once(self):
        # A one-second window has two rows; a one-row window has zero
        # duration. The singular pair "1 second across 1 row" is
        # unreachable by construction, but each singular fires on its own
        # window, which is exactly what the two tests above pin.
        self._write([{"t": 100, "next": "a: x"},
                     {"t": 101, "next": "a: y"}])
        one_sec = self._duration_line()
        self._write([{"t": 500, "next": "a: solo"}])
        one_row = self._duration_line()
        self.assertIn("1 second across", one_sec)
        self.assertIn("across 1 row", one_row)


class SpanRawSecondsPreservedTests(_SpanBase):
    """r273 pins the extent as raw seconds; r283 must not humanize it."""

    def test_r273_text_pin_still_literal_9000_seconds(self):
        self._write([{"t": 1000000, "next": "a: first"},
                     {"t": 1000500, "next": "a: mid"},
                     {"t": 1009000, "next": "a: last"}])
        # Same substring r273 asserts — raw seconds, not "2 hours".
        self.assertIn("Duration:   9000 seconds", self._span_text())

    def test_json_duration_seconds_unchanged(self):
        self._write([{"t": 1000000, "next": "a: first"},
                     {"t": 1009000, "next": "a: last"}])
        r = invoke_cli(self.workspace, ["history", "--span", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        span = json.loads(r.stdout)["span"]
        self.assertEqual(span["duration_seconds"], 9000)
        self.assertEqual(span["rows"], 2)


class HeaderAgreesWithSiblingsTests(_SpanBase):
    """The --span Duration line now pluralizes the way --domains (r281),
    --dedup (r282) and discover ('%d visit%s') already do."""

    def test_span_singular_matches_sibling_idiom(self):
        # One row: --span says "1 row"; the discover/domains family would
        # likewise say the singular noun for a count of one.
        self._write([{"t": 500, "next": "a: solo"}])
        self.assertIn("across 1 row", self._duration_line())

    def test_no_stray_double_plural_on_singular(self):
        self._write([{"t": 500, "next": "a: solo"}])
        line = self._duration_line()
        # Neither "1 rows" nor a "1 seconds" — the two hardcoded plurals
        # this round removed.
        self.assertNotIn("1 rows", line)
        self.assertNotIn("1 seconds", line)


class CatalogTests(unittest.TestCase):

    def _since_ints(self):
        return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]

    def test_entry_present(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "span-duration-pluralizes"),
                     None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r283")
        self.assertTrue(entry["default"])

    def test_r283_is_the_highest_round(self):
        # The newest round owns the exact ``max == NNN`` head; it retires
        # to a ``>=`` floor once its successor lands (r284).
        self.assertEqual(max(self._since_ints()), 283)

    def test_catalog_grew_to_134(self):
        self.assertEqual(len(mindseam._FEATURE_CATALOG), 134)

    def test_recent_window_is_104(self):
        recent = [i for i in self._since_ints() if i >= 170]
        self.assertEqual(len(recent), 104)


if __name__ == "__main__":
    unittest.main()
