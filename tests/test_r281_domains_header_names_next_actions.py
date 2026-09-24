# -*- coding: utf-8 -*-
"""Round 281 guards: history --domains header names next actions, not
seams, and pluralizes both nouns.

``history --domains`` ranks the domain prefix of every recorded next
action. Its NON-EMPTY text header used to read

    "-- mindseam - history (%d domains across %d seams)" % (len(counts), total)

but ``total`` is the count of rows WITH a next action -- the loop above
skips a blank-next row with ``if not nxt: continue`` -- NOT the number of
seams. So on a window that holds a blank-next seam, the header claimed
"across 2 seams" while ``history --count`` reported 3, and the word it
used ("seams") disagreed with this command's OWN empty face, which names
the unit accurately: "no rows with a next action".

The header also never pluralized: a single row read "1 domains across 1
seams", while the sibling ``discover`` already pluralizes ("%d visit%s").

r281 renames the ranked unit to "next action" so both faces of
``--domains`` agree with each other and with the ``if not nxt`` guard,
and pluralizes both "domain" and "next action". The ``--json`` face is
untouched (it never carried this header), so this is a text-face
correctness + grammar fix.
"""

import json
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


class _DomainsHeaderFixture(unittest.TestCase):
    """A workspace whose history is set per-test."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r281_")
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _write_history(self, rows):
        (self.ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def _domains_header(self, *extra):
        r = invoke_cli(self.workspace, ["history", "--domains", *extra])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.splitlines()[0]

    def _count(self, *extra):
        r = invoke_cli(self.workspace, ["history", "--count", *extra])
        self.assertEqual(r.returncode, 0, r.stderr)
        return int(r.stdout.strip())


# Two build: nexts + one blank-next row. Three seams; two next actions.
ROWS_BLANK_NEXT = [
    {"t": 1000, "next": "build: a", "verified": 0, "open": 1, "msg": "m1"},
    {"t": 2000, "next": "", "verified": 1, "open": 0, "msg": "m2"},
    {"t": 3000, "next": "build: c", "verified": 0, "open": 2, "msg": "m3"},
]
ROW_SINGLE = [
    {"t": 1000, "next": "build: a", "verified": 0, "open": 1, "msg": "m1"},
]
ROWS_TWO_DOMAINS = [
    {"t": 1000, "next": "build: a", "verified": 0, "open": 1, "msg": "m1"},
    {"t": 2000, "next": "refactor: b", "verified": 1, "open": 0, "msg": "m2"},
    {"t": 3000, "next": "build: c", "verified": 0, "open": 2, "msg": "m3"},
]


class DomainsHeaderUnitTests(_DomainsHeaderFixture):

    def test_header_says_next_actions_not_seams(self):
        # The r281 defect: the header called the ranked unit "seams".
        self._write_history(ROWS_TWO_DOMAINS)
        header = self._domains_header()
        self.assertNotIn("seams", header)
        self.assertIn("next action", header)

    def test_header_next_action_count_is_rows_with_a_next(self):
        # total (rows WITH a next), not the seam count. The blank-next
        # row is excluded from the domain ranking, so it is excluded here.
        self._write_history(ROWS_BLANK_NEXT)
        header = self._domains_header()
        self.assertIn("2 next actions", header)

    def test_header_does_not_claim_a_wrong_seam_count(self):
        # Before r281 the header said "across 2 seams" while there were 3
        # seams; the word "seams" with a wrong number is what's gone.
        self._write_history(ROWS_BLANK_NEXT)
        header = self._domains_header()
        self.assertNotIn("2 seams", header)
        self.assertNotIn("3 seams", header)


class HeaderAgreesWithSiblingsTests(_DomainsHeaderFixture):

    def test_seam_count_disagreement_is_gone(self):
        # The parity claim: history --count reports the true seam count.
        # The old header borrowed the word "seams" for a smaller number.
        # Now the header names a DIFFERENT unit (next actions), so there
        # is no longer a "seams" number to disagree with --count.
        self._write_history(ROWS_BLANK_NEXT)
        self.assertEqual(self._count(), 3)
        header = self._domains_header()
        # It reports 2 next actions (accurate) and no seam count at all.
        self.assertIn("2 next actions", header)
        self.assertNotIn("seams", header)

    def test_header_unit_matches_empty_face(self):
        # The command's empty face already says "no rows with a next
        # action"; the non-empty header now uses the same noun.
        self._write_history([])
        empty = self._domains_header()
        self.assertIn("next action", empty)
        self._write_history(ROWS_TWO_DOMAINS)
        nonempty = self._domains_header()
        self.assertIn("next action", nonempty)

    def test_empty_face_unchanged(self):
        # The empty branch is untouched by r281.
        self._write_history([{"t": 1000, "next": "", "verified": 0, "open": 1}])
        self.assertIn("no rows with a next action", self._domains_header())


class PluralizationTests(_DomainsHeaderFixture):

    def test_single_domain_single_next_is_singular(self):
        # The grammar defect: "1 domains across 1 seams".
        self._write_history(ROW_SINGLE)
        header = self._domains_header()
        self.assertIn("1 domain across 1 next action", header)
        self.assertNotIn("1 domains", header)
        self.assertNotIn("1 next actions", header)

    def test_plural_domains_and_next_actions(self):
        self._write_history(ROWS_TWO_DOMAINS)
        header = self._domains_header()
        self.assertIn("2 domains across 3 next actions", header)

    def test_one_domain_many_next_actions(self):
        # A single domain reached by two next actions: domain singular,
        # next action plural.
        self._write_history(ROWS_BLANK_NEXT)
        header = self._domains_header()
        self.assertIn("1 domain across 2 next actions", header)
        self.assertNotIn("1 domains", header)

    def test_pluralization_matches_discover_visit_style(self):
        # discover already pluralizes its per-line count ("%d visit%s");
        # a single-visit domain there reads "1 visit", not "1 visits".
        self._write_history(ROW_SINGLE)
        r = invoke_cli(self.workspace, ["discover"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 visit", r.stdout)
        self.assertNotIn("1 visits", r.stdout)


class JsonFaceUntouchedTests(_DomainsHeaderFixture):

    def test_domains_json_carries_no_header(self):
        # The JSON face never had this header; it stays a domains list.
        self._write_history(ROWS_TWO_DOMAINS)
        r = invoke_cli(self.workspace, ["history", "--domains", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("domains", payload)
        self.assertNotIn("seams", r.stdout)
        # The counts JSON still reflects the two next-action rows.
        counts = {d["domain"]: d["count"] for d in payload["domains"]}
        self.assertEqual(counts.get("build"), 2)

    def test_grep_still_narrows_before_grouping(self):
        # The header change did not disturb --grep narrowing (r-earlier).
        self._write_history([
            {"t": 1000, "next": "build: a", "verified": 0, "open": 1, "msg": "TODO"},
            {"t": 2000, "next": "refactor: b", "verified": 1, "open": 0, "msg": "done"},
            {"t": 3000, "next": "build: c", "verified": 0, "open": 2, "msg": "TODO"},
        ])
        header = self._domains_header("--grep", "TODO")
        self.assertIn("1 domain across 2 next actions", header)


class CatalogTests(_DomainsHeaderFixture):

    def _since_ints(self):
        return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]

    def test_entry_present(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "domains-header-names-next-actions"),
                     None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r281")
        self.assertTrue(entry["default"])

    def test_r281_is_the_highest_round(self):
        # The newest round owns the exact ``max == NNN`` head; it retires
        # to a ``>=`` floor once its successor lands.
        self.assertEqual(max(self._since_ints()), 281)

    def test_catalog_grew_to_132(self):
        self.assertEqual(len(mindseam._FEATURE_CATALOG), 132)

    def test_recent_window_is_102(self):
        recent = [i for i in self._since_ints() if i >= 170]
        self.assertEqual(len(recent), 102)


if __name__ == "__main__":
    unittest.main()
