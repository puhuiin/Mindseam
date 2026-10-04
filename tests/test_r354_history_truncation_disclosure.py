# -*- coding: utf-8 -*-
"""r354 — the truncation selectors had no disclosure on either face.

r324's doctrine: a host must be able to tell WHAT narrowed the rows it
is about to act on. r324 applied it to the four text/time filters
(--since/--until/--grep/--exclude) and left the truncation selectors
out — the ones r272 had added and the --row-id refusal list (r320)
already counts as members that "change which rows exist":

    history --head 2 --json   -> 2 rows, limit null, no head key
    history --tail 2 --json   -> 2 rows, limit null (the alias never
                                 filled the key its own aliasee owns)
    history --keep 2 --json   -> 2 rows, no keep key — AND the file on
                                 disk silently rotated

Live before-fix, on a five-row history: all three answered exit 0 with
rows=[2] and a payload whose every narrowing key was null — a host
could not distinguish a head-truncated window from a history that
simply holds two rows, and --keep was worse: the destructive rotation
left no stdout trace at all. The text face was equally blind: the
header clause set was {last N s, older than N s, grep, exclude,
newest first} with no clause for first-N / last-N / keep.

The fix extends the r324 shape to the selectors: a head key, a keep
key, and the limit key that now reports the EFFECTIVE newest-N bound
(--tail is r272's alias of --limit, one dest at runtime — the merge
expression the slicing branch already uses — so the alias fills the
same key instead of answering null). Null when unset, so the key set
is stable; a no-flag call renders byte-identically on both faces.
The text header gains ", first N rows" / ", last N rows" (the
`head -n N` / `tail -n N` shapes r272 borrowed) and ", keep N" after
"newest first", because the rotation is the last thing that happened.
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

ROWS = [{"t": 1700000000 + i, "next": "dom%d: action %d" % (i % 3, i),
         "msg": "m%d" % i, "verified": 1, "open": 0} for i in range(5)]

KEYS = ["exclude", "grep", "head", "history_count", "keep", "limit",
        "reverse", "rows", "since", "until", "untrusted"]


class DisclosureBase(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        d = os.path.join(self.ws, ".mindseam")
        os.makedirs(d)
        with open(os.path.join(d, "history.json"), "w",
                  encoding="utf-8") as f:
            json.dump(ROWS, f)

    def _json(self, *flags):
        r = invoke_cli(self.ws, ["history", "--json", *flags])
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def _text(self, *flags):
        r = invoke_cli(self.ws, ["history", *flags])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.splitlines()[0]


class JsonDisclosureTests(DisclosureBase):
    def test_head_is_disclosed(self):
        payload = self._json("--head", "2")
        self.assertEqual(len(payload["rows"]), 2)
        self.assertEqual(payload["head"], 2)
        self.assertIsNone(payload["limit"])
        self.assertIsNone(payload["keep"])

    def test_tail_fills_the_limit_key(self):
        # --tail is r272's alias of --limit: one dest at runtime. The
        # alias answers the same key its aliasee owns — before r354 it
        # answered null while truncating the rows just the same.
        payload = self._json("--tail", "2")
        self.assertEqual(len(payload["rows"]), 2)
        self.assertEqual(payload["limit"], 2)
        self.assertIsNone(payload["head"])

    def test_limit_key_semantics_unchanged(self):
        self.assertEqual(self._json("--limit", "2")["limit"], 2)
        self.assertEqual(self._json("-n", "3")["limit"], 3)

    def test_keep_is_disclosed(self):
        payload = self._json("--keep", "3")
        self.assertEqual(payload["keep"], 3)
        self.assertIsNone(payload["head"])
        self.assertIsNone(payload["limit"])

    def test_key_set_stable_and_null_when_unset(self):
        payload = self._json()
        self.assertEqual(sorted(payload.keys()), KEYS)
        for key in ("head", "limit", "keep"):
            self.assertIsNone(payload[key])
        self.assertEqual(len(payload["rows"]), 5)

    def test_history_count_answers_the_surviving_window(self):
        # r324's existing semantics, unchanged: history_count is
        # len(hist) AFTER the selectors ran, so it always equals
        # len(rows) — the NEW keys are what name the narrowing that
        # produced that count (before r354 a host saw count 2 with
        # every narrowing key null and had to guess).
        payload = self._json("--head", "2")
        self.assertEqual(payload["history_count"], 2)
        self.assertEqual(payload["head"], 2)
        self.assertEqual(len(payload["rows"]), 2)

    def test_untrusted_map_still_rides(self):
        payload = self._json("--head", "2")
        self.assertIn("untrusted", payload)


class TextHeaderTests(DisclosureBase):
    def test_head_clause(self):
        self.assertIn("first 2 rows", self._text("--head", "2"))

    def test_tail_and_limit_share_the_last_n_clause(self):
        self.assertIn("last 2 rows", self._text("--tail", "2"))
        self.assertIn("last 2 rows", self._text("--limit", "2"))

    def test_keep_clause(self):
        self.assertIn("keep 3", self._text("--keep", "3"))

    def test_no_flags_header_is_byte_identical(self):
        self.assertEqual(self._text(), "── mindseam ─ history (5 entries)")

    def test_clauses_compose_with_the_filter_clauses(self):
        header = self._text("--head", "1", "--grep", "dom1")
        self.assertIn("grep 'dom1'", header)
        self.assertIn("first 1 rows", header)

    def test_keep_clause_follows_reverse(self):
        header = self._text("--keep", "3", "--reverse")
        self.assertLess(header.index("newest first"),
                        header.index("keep 3"))


class KeepRotationTests(DisclosureBase):
    def test_keep_rotates_the_file_and_discloses(self):
        payload = self._json("--keep", "2")
        self.assertEqual(payload["keep"], 2)
        self.assertEqual(len(payload["rows"]), 2)
        led = os.path.join(self.ws, ".mindseam", "history.json")
        with open(led, encoding="utf-8") as f:
            rotated = json.load(f)
        self.assertEqual(len(rotated), 2, "the file did not rotate")
        self.assertEqual(payload["rows"], rotated)

    def test_keep_zero_empties_and_discloses(self):
        payload = self._json("--keep", "0")
        self.assertEqual(payload["keep"], 0)
        self.assertEqual(payload["rows"], [])
        led = os.path.join(self.ws, ".mindseam", "history.json")
        with open(led, encoding="utf-8") as f:
            self.assertEqual(json.load(f), [])


class NeighbouringGuardsTests(DisclosureBase):
    def test_r217_negative_refusal_precedes_the_face(self):
        for flag in ("--head", "--keep"):
            r = invoke_cli(self.ws, ["history", "--json", flag, "-1"])
            self.assertEqual(r.returncode, 2)
            self.assertIn("CANNOT", r.stderr)

    def test_r272_zero_windows_unchanged(self):
        self.assertEqual(self._json("--head", "0")["rows"], [])
        self.assertEqual(self._json("--limit", "0")["rows"], [])
        self.assertEqual(self._json("--head", "0")["head"], 0)
        self.assertEqual(self._json("--limit", "0")["limit"], 0)

    def test_r320_row_id_still_refuses_every_selector(self):
        for flag in (["--head", "2"], ["--tail", "2"], ["--limit", "2"],
                     ["--keep", "2"]):
            r = invoke_cli(self.ws, ["history", "--row-id", "1", *flag])
            self.assertEqual(r.returncode, 2, flag)
            self.assertIn("CANNOT", r.stderr)

    def test_r275_filter_then_truncate_order_unchanged(self):
        # Filter dom0 rows (i=0 and i=3) first, THEN keep the last one:
        # the truncation-then-filter order would answer empty instead.
        payload = self._json("--grep", "dom0", "--tail", "1")
        self.assertEqual([r["next"] for r in payload["rows"]],
                         ["dom0: action 3"])

    def test_r324_time_and_text_keys_unchanged(self):
        payload = self._json("--until", "7200", "--exclude", "dom0")
        self.assertEqual(payload["until"], 7200)
        self.assertEqual(payload["exclude"], "dom0")
        self.assertIsNone(payload["head"])
        self.assertIsNone(payload["keep"])


class CatalogPinTests(unittest.TestCase):
    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("truncation-selectors-disclosed", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "truncation-selectors-disclosed")
        self.assertEqual(entry["since"], "r354")
        self.assertIn("head", entry["summary"])
        self.assertIn("keep", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 204 before r354; later rounds keep appending above it, so this
        # pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 205)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertTrue(callable(mindseam.scan_untrusted))
        self.assertTrue(callable(mindseam.text_contains_any))


if __name__ == "__main__":
    unittest.main()
