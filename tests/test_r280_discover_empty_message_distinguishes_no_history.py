# -*- coding: utf-8 -*-
"""Round 280 guards: discover's empty message distinguishes no-history
from history-with-no-next.

``discover`` ranks the domain prefix of every recorded next action. Its
ranking is empty in TWO different states:

  1. A truly empty ``history.json`` (nothing has happened yet).
  2. A history that HAS recorded seams, but no row carries a next action
     to rank.

The old text face printed a single message for both --
"No history yet -- run a seam and the domain map appears." -- which is a
FALSE statement in state 2: the session has history, so a host reading
"No history yet" concludes nothing has happened and may re-run work that
already ran.

The sibling ``history --domains`` never made this claim. Its empty face
says "no rows with a next action", which is accurate whether or not
history exists, because it distinguishes the empty COUNT from the CAUSE.

r280 branches on whether ``hist`` is non-empty inside the not-ranked
block: history-with-no-next now prints "No next actions recorded yet --
note a next and the domain map appears." and only a truly empty history
keeps "No history yet". The ``--json`` face is untouched (``{"domains":
[]}`` is accurate for both, matching ``history --domains --json``), so
this is a text-face correctness fix bringing discover to parity with its
sibling.
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


class _DiscoverEmptyFixture(unittest.TestCase):
    """A workspace whose history is set per-test. Two rows that both have
    an EMPTY next action stand in for "history exists but nothing to
    rank"; ``[]`` stands in for "truly empty"."""

    ROWS_NO_NEXT = [
        {"t": 1000, "next": "", "verified": 1, "open": 0, "msg": "did a thing"},
        {"t": 2000, "next": "", "verified": 1, "open": 0, "msg": "did another"},
    ]

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r280_")
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

    def _discover_text(self, *extra):
        r = invoke_cli(self.workspace, ["discover", *extra])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def _discover_json(self, *extra):
        r = invoke_cli(self.workspace, ["discover", "--json", *extra])
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def _domains_text(self):
        r = invoke_cli(self.workspace, ["history", "--domains"])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout


class DiscoverEmptyMessageTests(_DiscoverEmptyFixture):

    def test_history_with_no_next_does_not_claim_no_history(self):
        # The r280 defect: recorded seams exist, but discover said
        # "No history yet". That claim must be gone.
        self._write_history(self.ROWS_NO_NEXT)
        out = self._discover_text()
        self.assertNotIn("No history yet", out)

    def test_history_with_no_next_reports_the_true_cause(self):
        # It names the real reason the map is empty: no next actions.
        self._write_history(self.ROWS_NO_NEXT)
        out = self._discover_text()
        self.assertIn("No next actions recorded yet", out)

    def test_truly_empty_history_still_says_no_history(self):
        # The truly-empty state keeps its original, accurate message.
        self._write_history([])
        out = self._discover_text()
        self.assertIn("No history yet", out)

    def test_truly_empty_history_does_not_say_no_next_actions(self):
        # The two states must not collapse in the other direction either.
        self._write_history([])
        out = self._discover_text()
        self.assertNotIn("No next actions recorded yet", out)

    def test_missing_history_file_says_no_history(self):
        # No history.json at all is the truly-empty state.
        out = self._discover_text()
        self.assertIn("No history yet", out)

    def test_both_empty_states_agree_with_domains_on_no_domains(self):
        # The parity claim: whenever discover's ranking is empty, so is
        # history --domains'. Both empty states rank nothing.
        for rows in ([], self.ROWS_NO_NEXT):
            self._write_history(rows)
            disc = self._discover_json()
            self.assertEqual(disc["domains"], [])
            # history --domains text names the no-next cause, never
            # "No history yet" -- the accurate framing discover now mirrors.
            dom_text = self._domains_text()
            self.assertIn("no rows with a next action", dom_text)

    def test_json_face_identical_for_both_empty_states(self):
        # The fix is text-only: JSON stays {"domains": []} for both, the
        # way history --domains --json does not distinguish them.
        self._write_history([])
        empty_json = self._discover_json()
        self._write_history(self.ROWS_NO_NEXT)
        no_next_json = self._discover_json()
        self.assertEqual(empty_json, {"domains": []})
        self.assertEqual(no_next_json, {"domains": []})

    def test_recorded_domain_is_unaffected(self):
        # A history that DOES have a next action still ranks and suggests,
        # untouched by the empty-branch change.
        self._write_history(
            [{"t": 1000, "next": "build: ship", "verified": 1, "open": 0}])
        out = self._discover_text()
        self.assertIn("discover", out)
        self.assertIn("build", out)
        self.assertNotIn("No history yet", out)
        self.assertNotIn("No next actions recorded yet", out)

    def test_no_next_message_is_one_line_at_exit_zero(self):
        # The new branch is a single print at exit 0, like its sibling.
        self._write_history(self.ROWS_NO_NEXT)
        r = invoke_cli(self.workspace, ["discover"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 1)


class CatalogTests(_DiscoverEmptyFixture):

    def _since_ints(self):
        return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]

    def test_entry_present(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "discover-empty-message-distinguishes-no-history"),
                     None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r280")
        self.assertTrue(entry["default"])

    def test_r280_is_the_highest_round(self):
        # The newest round owns the exact ``max == NNN`` head; it retires
        # to a ``>=`` floor once its successor lands (r281).
        self.assertGreaterEqual(max(self._since_ints()), 280)

    def test_catalog_grew_to_131(self):
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 131)

    def test_recent_window_is_101(self):
        recent = [i for i in self._since_ints() if i >= 170]
        self.assertGreaterEqual(len(recent), 101)


if __name__ == "__main__":
    unittest.main()
