"""r287 — the history-row count pluralizes "entry" irregularly.

The history-row count is projected as a bare "N entries" on two human
faces that read the SAME quantity ``len(hist)``: the ``history`` header
("── mindseam ─ history (N entries...)") and the ``info`` report
("History: N entries"). "entry" pluralizes irregularly (entry -> entries,
not a bare ``+s``), so the r285 ``_bytes_noun`` "append s" spelling cannot
render it, and both sites hardcoded the plural stem "entries".

Live before-fix (fresh workspace, one seam): ``info`` printed
"History: 1 entries" and ``history`` printed
"── mindseam ─ history (1 entries)"; ``history --limit 1`` over a longer
log printed the same wrong singular header.

The fix routes both faces through one chokepoint ``_entries_noun(count)``
returning ``"%d entr" + ("y" if count == 1 else "ies")``. "0 entries" and
every count >= 2 stay byte-identical; only exactly 1 becomes "1 entry".
Because the two faces render one value they must agree by construction
(the r254/r259 enumerate-every-projector discipline). The ``--json`` faces
expose the raw integer ``history_count`` with no noun and are untouched.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam  # noqa: E402

from _controller_helper import invoke_cli  # noqa: E402


def _since_ints():
    return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]


class EntriesNounHelperTests(unittest.TestCase):
    def test_zero_is_plural(self):
        # An empty history is documented as "0 entries" — the plural stem
        # stays exactly as before the fix.
        self.assertEqual(mindseam._entries_noun(0), "0 entries")

    def test_one_is_the_irregular_singular(self):
        self.assertEqual(mindseam._entries_noun(1), "1 entry")

    def test_two_is_plural(self):
        self.assertEqual(mindseam._entries_noun(2), "2 entries")

    def test_many_stay_plural(self):
        for n in (3, 10, 42, 500, 1000):
            self.assertEqual(mindseam._entries_noun(n), "%d entries" % n)

    def test_only_one_ever_reads_singular(self):
        # The singular stem "entry" is reached by exactly the count 1 and
        # nothing else — the guard is ``count == 1``, not ``count <= 1``.
        for n in range(0, 200):
            word = mindseam._entries_noun(n)
            if n == 1:
                self.assertEqual(word, "1 entry")
            else:
                self.assertTrue(
                    word.endswith("entries"),
                    "count %d should read entries, got %r" % (n, word),
                )


class _WorkspaceBase(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r287_")
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)

    def _seam(self, n=1):
        for _ in range(n):
            res = invoke_cli(self.workspace, ["seam"])
            self.assertEqual(res.returncode, 0, res.stderr)


class HistoryHeaderPluralTests(_WorkspaceBase):
    def test_one_entry_header_is_singular(self):
        self._seam(1)
        res = invoke_cli(self.workspace, ["history"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("(1 entry)", res.stdout)
        self.assertNotIn("(1 entries)", res.stdout)

    def test_two_entries_header_is_plural(self):
        self._seam(2)
        res = invoke_cli(self.workspace, ["history"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("(2 entries)", res.stdout)

    def test_limit_one_over_longer_log_is_singular(self):
        # --limit narrows hist to a single row BEFORE the header is built,
        # so a three-row log printed through --limit 1 still reads "1 entry".
        self._seam(3)
        res = invoke_cli(self.workspace, ["history", "--limit", "1"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("(1 entry)", res.stdout)
        self.assertNotIn("(1 entries)", res.stdout)


class InfoHistoryLinePluralTests(_WorkspaceBase):
    def test_zero_entries_is_plural(self):
        res = invoke_cli(self.workspace, ["info"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("History: 0 entries", res.stdout)

    def test_one_entry_is_singular(self):
        self._seam(1)
        res = invoke_cli(self.workspace, ["info"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("History: 1 entry", res.stdout)
        self.assertNotIn("History: 1 entries", res.stdout)

    def test_two_entries_is_plural(self):
        self._seam(2)
        res = invoke_cli(self.workspace, ["info"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("History: 2 entries", res.stdout)


class FacesAgreeTests(_WorkspaceBase):
    def test_history_header_and_info_line_agree_on_the_noun(self):
        # The two faces render one value (len(hist)); the r254/r259
        # enumerate-every-projector discipline requires they never disagree
        # about the noun for the same workspace.
        self._seam(1)
        info = invoke_cli(self.workspace, ["info"]).stdout
        hist = invoke_cli(self.workspace, ["history"]).stdout
        self.assertIn("History: 1 entry", info)
        self.assertIn("(1 entry)", hist)
        # And neither leaks the wrong plural.
        self.assertNotIn("1 entries", info)
        self.assertNotIn("1 entries", hist)


class JsonFaceUntouchedTests(_WorkspaceBase):
    def test_history_json_carries_raw_integer_not_noun(self):
        self._seam(1)
        res = invoke_cli(self.workspace, ["history", "--json"])
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["history_count"], 1)
        # The JSON face is a data face: no pluralized English noun in it.
        self.assertNotIn("entry", res.stdout)
        self.assertNotIn("entries", res.stdout)

    def test_info_json_history_count_is_integer(self):
        self._seam(1)
        res = invoke_cli(self.workspace, ["info", "--json"])
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["history_count"], 1)


class CatalogTests(unittest.TestCase):
    def test_entry_present_since_r287_default_true(self):
        entry = next(
            (e for e in mindseam._FEATURE_CATALOG
             if e["id"] == "entries-noun-irregular-plural"),
            None,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r287")
        self.assertTrue(entry["default"])

    def test_r287_is_the_highest_round(self):
        # r288 retired this exact head pin to a floor; r287 remains a
        # registered round, so the max never drops below it.
        self.assertGreaterEqual(max(_since_ints()), 287)

    def test_catalog_grew_to_138(self):
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 138)

    def test_recent_window_is_108(self):
        recent = [n for n in _since_ints() if n >= 170]
        self.assertGreaterEqual(len(recent), 108)


if __name__ == "__main__":
    unittest.main()
