"""r288 — the seam ledger-stagnation fact agrees noun AND verb.

``detect_ledger_stagnation`` (surfaced by ``observations()`` on every
seam) rendered the stale-core-item count as
"%d core item(s) have gone unverified across %d seams". This was the ONLY
count-render left in the tool using the "(s)" lazy plural, and the only
one whose VERB also disagreed at exactly one item: "1 core item(s) have
gone" reads a plural verb ("have") for a single subject and shows the
parenthetical "(s)" that every sibling health fact avoids.

Live before-fix (a workspace with one stale Core item and a flat 8-seam
verified window): the seam fact read
"· 1 core item(s) have gone unverified across 8 seams."

This is the singular/plural family of r281 (history --domains), r282
(history --dedup), r283 (history --span), r285 (bytes) and r287 (entries),
but the FIRST to fix subject-verb agreement — the verb, not just the noun.
The noun routes through the same "item" vs "items" split every sibling
health fact uses and the verb agrees: "has" for one, "have" for two or
more. A lone stale item now reads "1 core item has gone unverified across
8 seams." while two or more read "2 core items have gone ...". The
"across N seams" clause is unchanged (LEDGER_STALE_SEAMS is the constant
8, never singular) and the "gone unverified" remediation key
(mindseam.py:6143) survives verbatim, so the advice mapping still fires.
The --json seam payload carries the same fact list, so a host reads the
corrected sentence there too.
"""

import json
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam  # noqa: E402

from _controller_helper import invoke_cli  # noqa: E402


def _since_ints():
    return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]


def _flat_window(n=mindseam.LEDGER_STALE_SEAMS):
    # n seams whose verified count never moves — hist[-LEDGER_STALE_SEAMS]
    # and hist[-1] read the same value, so the stagnation guard fires.
    return [{"verified": 0} for _ in range(n)]


class StagnationHelperTests(unittest.TestCase):
    """detect_ledger_stagnation agrees noun and verb on the count."""

    def test_one_stale_item_is_singular_noun_and_verb(self):
        book = {"Core": ["auth layer — token refresh"], "Verified": []}
        facts = mindseam.detect_ledger_stagnation(_flat_window(), book)
        self.assertEqual(
            facts,
            ["1 core item has gone unverified across 8 seams."],
        )

    def test_two_stale_items_are_plural_noun_and_verb(self):
        book = {
            "Core": ["auth layer — token refresh", "cache — eviction"],
            "Verified": [],
        }
        facts = mindseam.detect_ledger_stagnation(_flat_window(), book)
        self.assertEqual(
            facts,
            ["2 core items have gone unverified across 8 seams."],
        )

    def test_never_emits_the_lazy_parenthetical_plural(self):
        # Across every stale count the fact reaches, "item(s)" must never
        # appear — that was the exact spelling this round retired.
        for k in range(1, 6):
            book = {
                "Core": ["c%d — anchor%d" % (i, i) for i in range(k)],
                "Verified": [],
            }
            facts = mindseam.detect_ledger_stagnation(_flat_window(), book)
            self.assertEqual(len(facts), 1)
            self.assertNotIn("item(s)", facts[0])

    def test_verb_tracks_the_noun_across_counts(self):
        # Singular subject -> "has"; every plural subject -> "have".
        for k in range(1, 6):
            book = {
                "Core": ["c%d — anchor%d" % (i, i) for i in range(k)],
                "Verified": [],
            }
            fact = mindseam.detect_ledger_stagnation(_flat_window(), book)[0]
            if k == 1:
                self.assertIn("1 core item has gone", fact)
                self.assertNotIn("have gone", fact)
            else:
                self.assertIn("%d core items have gone" % k, fact)
                self.assertNotIn("item has gone", fact)

    def test_across_clause_is_the_constant_never_singular(self):
        # LEDGER_STALE_SEAMS is 8, so the trailing count is always plural
        # regardless of how many core items are stale.
        book = {"Core": ["only — one"], "Verified": []}
        fact = mindseam.detect_ledger_stagnation(_flat_window(), book)[0]
        self.assertIn("across 8 seams.", fact)


class SeamSurfaceTests(unittest.TestCase):
    """The live seam text and JSON faces carry the corrected sentence."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r288_")
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)
        res = invoke_cli(
            self.workspace,
            ["note", "--goal", "ship the thing",
             "--next", "write the parser"],
        )
        self.assertEqual(res.returncode, 0, res.stderr)

    def _add_core(self, text):
        res = invoke_cli(self.workspace, ["note", "--core", text])
        self.assertEqual(res.returncode, 0, res.stderr)

    def _run_flat_seams(self, n=mindseam.LEDGER_STALE_SEAMS + 1):
        # A core item goes stale only after LEDGER_STALE_SEAMS seams with a
        # flat verified count; no Verified item is ever added, so the
        # window stays flat by construction.
        for _ in range(n):
            res = invoke_cli(self.workspace, ["seam"])
            self.assertEqual(res.returncode, 0, res.stderr)

    def test_one_stale_item_text_face_is_singular(self):
        self._add_core("auth layer — token refresh path")
        self._run_flat_seams()
        res = invoke_cli(self.workspace, ["seam", "--dry-run"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("1 core item has gone unverified across 8 seams.",
                      res.stdout)
        self.assertNotIn("item(s)", res.stdout)
        self.assertNotIn("1 core item have gone", res.stdout)

    def test_two_stale_items_text_face_is_plural(self):
        self._add_core("auth layer — token refresh path")
        self._add_core("cache layer — eviction policy")
        self._run_flat_seams()
        res = invoke_cli(self.workspace, ["seam", "--dry-run"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("2 core items have gone unverified across 8 seams.",
                      res.stdout)
        self.assertNotIn("item(s)", res.stdout)

    def test_json_face_carries_the_corrected_singular_fact(self):
        self._add_core("auth layer — token refresh path")
        self._run_flat_seams()
        res = invoke_cli(self.workspace, ["seam", "--dry-run", "--json"])
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        stale = [f for f in payload["facts"] if "unverified" in f]
        self.assertEqual(
            stale, ["1 core item has gone unverified across 8 seams."])
        self.assertNotIn("item(s)", res.stdout)

    def test_remediation_still_fires_on_gone_unverified(self):
        # The fix preserves the "gone unverified" substring, so the advice
        # mapping (mindseam.py:6143) still surfaces its remediation line.
        self._add_core("auth layer — token refresh path")
        self._run_flat_seams()
        res = invoke_cli(self.workspace, ["seam", "--dry-run"])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn(
            "Core items have gone unverified — run one check against the "
            "oldest core item.",
            res.stdout,
        )


class FacesAgreeTests(unittest.TestCase):
    """Text and JSON render one fact list; they must agree word for word."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r288f_")
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)
        invoke_cli(
            self.workspace,
            ["note", "--goal", "ship", "--next", "write parser"],
        )
        invoke_cli(self.workspace, ["note", "--core", "auth — refresh"])
        for _ in range(mindseam.LEDGER_STALE_SEAMS + 1):
            invoke_cli(self.workspace, ["seam"])

    def test_text_and_json_carry_the_same_sentence(self):
        text = invoke_cli(self.workspace, ["seam", "--dry-run"]).stdout
        payload = json.loads(
            invoke_cli(self.workspace, ["seam", "--dry-run", "--json"]).stdout)
        sentence = "1 core item has gone unverified across 8 seams."
        self.assertIn(sentence, text)
        self.assertIn(sentence, payload["facts"])
        # Neither face leaks the retired spelling nor a disagreeing verb.
        self.assertNotIn("item(s)", text)
        self.assertNotIn("1 core item have gone", text)
        for fact in payload["facts"]:
            self.assertNotIn("item(s)", fact)


class CatalogTests(unittest.TestCase):
    def test_entry_present_since_r288_default_true(self):
        entry = next(
            (e for e in mindseam._FEATURE_CATALOG
             if e["id"] == "ledger-stagnation-agrees-noun-and-verb"),
            None,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r288")
        self.assertTrue(entry["default"])

    def test_r288_is_the_highest_round(self):
        # r289 retired this exact head pin to a floor: r288's entry
        # is permanent, but later rounds append past it.
        self.assertGreaterEqual(max(_since_ints()), 288)

    def test_catalog_grew_to_139(self):
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 139)

    def test_recent_window_is_109(self):
        recent = [n for n in _since_ints() if n >= 170]
        self.assertGreaterEqual(len(recent), 109)


if __name__ == "__main__":
    unittest.main()
