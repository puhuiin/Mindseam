# -*- coding: utf-8 -*-
"""Round 279 guards: discover counts colonless next actions.

``discover`` and ``history --domains`` are sibling read-only reflections
that both rank the domain prefix of every recorded next action --
discover's own docstring says "count the domain prefix of every recorded
next action". ``history --domains`` groups by
``nxt.split(":", 1)[0].strip().lower()`` with an empty prefix bucketed to
``(none)`` and drops only rows whose next is entirely blank
(``if not nxt: continue``).

But ``discover`` carried a stricter guard -- ``if not nxt or ":" not in
nxt: continue`` -- which silently dropped every next that had NO colon.
So a session that recorded bare actions ("refactor the loop") had those
rows counted by ``history --domains`` yet invisible to ``discover``. Worse,
``suggested_next`` -- the single next action a host actually acts on --
could name a colon'd domain while an equally- or more-visited colonless
action never surfaced at all.

r279 removes the ``":" not in nxt`` clause and groups by
``nxt.split(":", 1)[0].strip().lower() or "(none)"``: "the prefix before
the first colon" of a colonless string is the whole string, so the two
sibling reflections now agree on which rows exist.
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


class _DiscoverFixture(unittest.TestCase):
    """Four rows: two colon'd nexts under one domain (``build``) and two
    identical colonless nexts (``refactor the loop``). The colonless action
    is exactly as visited as the colon'd domain, so a face that drops it
    silently loses a top-ranked candidate."""

    ROWS = [
        {"t": 1000, "next": "build: parser", "verified": 1, "open": 0},
        {"t": 2000, "next": "build: linker", "verified": 1, "open": 0},
        {"t": 3000, "next": "refactor the loop", "verified": 1, "open": 0},
        {"t": 4000, "next": "refactor the loop", "verified": 1, "open": 0},
    ]

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r279_")
        ledger = Path(self.workspace) / ".mindseam"
        ledger.mkdir(parents=True, exist_ok=True)
        (ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        (ledger / "history.json").write_text(
            json.dumps(self.ROWS), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _discover(self, *extra):
        r = invoke_cli(self.workspace, ["discover", "--json", *extra])
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def _domains(self, *extra):
        r = invoke_cli(self.workspace, ["history", "--domains", "--json", *extra])
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class DiscoverColonlessTests(_DiscoverFixture):

    def test_discover_counts_the_colonless_action(self):
        # The tell: the bare action must appear at all.
        names = {d["name"] for d in self._discover()["domains"]}
        self.assertIn("refactor the loop", names)
        self.assertIn("build", names)

    def test_colonless_visit_count_is_correct(self):
        by_name = {d["name"]: d["visits"] for d in self._discover()["domains"]}
        self.assertEqual(by_name["refactor the loop"], 2)
        self.assertEqual(by_name["build"], 2)

    def test_discover_domain_set_matches_history_domains(self):
        # The two sibling reflections agree on WHICH rows exist. discover
        # keys on ``name``/``visits``; history --domains on ``domain``/
        # ``count`` -- compare the (label, count) pairs.
        disc = {(d["name"], d["visits"]) for d in self._discover()["domains"]}
        doms = {(d["domain"], d["count"]) for d in self._domains()["domains"]}
        self.assertEqual(disc, doms)

    def test_suggested_next_does_not_omit_a_top_action(self):
        # ``build`` and ``refactor the loop`` are equally visited; the
        # colonless one is no longer invisible, so the suggestion is drawn
        # from the full ranked set (ties break by name, so ``build`` wins,
        # but the point is the ranked set is complete).
        payload = self._discover()
        self.assertEqual(payload["suggested_next"], "build")
        names = {d["name"] for d in payload["domains"]}
        self.assertIn("refactor the loop", names)

    def test_colonless_can_outrank_and_be_suggested(self):
        # Add a third colonless visit so the bare action is the MOST
        # visited; it must now be the suggested_next -- the old drop made
        # this literally impossible.
        rows = list(self.ROWS) + [
            {"t": 5000, "next": "refactor the loop", "verified": 1, "open": 0}]
        (Path(self.workspace) / ".mindseam" / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")
        payload = self._discover()
        self.assertEqual(payload["suggested_next"], "refactor the loop")
        top = payload["domains"][0]
        self.assertEqual(top["name"], "refactor the loop")
        self.assertEqual(top["visits"], 3)

    def test_empty_prefix_buckets_to_none(self):
        # A next like ``: ship`` has an empty prefix before the first
        # colon; history --domains buckets it to ``(none)`` and discover
        # must do the same rather than drop or mislabel it.
        rows = [
            {"t": 1000, "next": ": ship", "verified": 1, "open": 0},
            {"t": 2000, "next": "build: x", "verified": 1, "open": 0},
        ]
        (Path(self.workspace) / ".mindseam" / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")
        disc = {d["name"] for d in self._discover()["domains"]}
        doms = {d["domain"] for d in self._domains()["domains"]}
        self.assertIn("(none)", disc)
        self.assertEqual(disc, doms)

    def test_blank_next_still_dropped_by_both(self):
        # An entirely blank next is dropped by BOTH faces (the one
        # ``if not nxt`` guard both share). r279 does not resurrect blanks.
        rows = [
            {"t": 1000, "next": "", "verified": 1, "open": 0},
            {"t": 2000, "next": "build: x", "verified": 1, "open": 0},
        ]
        (Path(self.workspace) / ".mindseam" / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")
        disc = {d["name"] for d in self._discover()["domains"]}
        self.assertNotIn("", disc)
        self.assertNotIn("(none)", disc)
        self.assertEqual(disc, {"build"})

    def test_text_face_lists_the_colonless_action(self):
        r = invoke_cli(self.workspace, ["discover"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("refactor the loop", r.stdout)
        self.assertIn("build", r.stdout)

    def test_only_colonless_actions_all_rank(self):
        # A session that never used the ``domain:`` convention once still
        # gets a ranking -- the old guard would have emitted an empty
        # discover with no suggested_next.
        rows = [
            {"t": 1000, "next": "write the docs", "verified": 1, "open": 0},
            {"t": 2000, "next": "write the docs", "verified": 1, "open": 0},
            {"t": 3000, "next": "fix the bug", "verified": 1, "open": 0},
        ]
        (Path(self.workspace) / ".mindseam" / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")
        payload = self._discover()
        by_name = {d["name"]: d["visits"] for d in payload["domains"]}
        self.assertEqual(by_name, {"write the docs": 2, "fix the bug": 1})
        self.assertEqual(payload["suggested_next"], "write the docs")


class CatalogTests(unittest.TestCase):

    def _since_ints(self):
        return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]

    def test_entry_present(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "discover-counts-colonless-domains"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r279")
        self.assertTrue(entry["default"])

    def test_r279_is_the_highest_round(self):
        # The newest round owns the exact ``max == NNN`` head; it retires
        # to a ``>=`` floor once its successor lands.
        self.assertEqual(max(self._since_ints()), 279)

    def test_catalog_grew_to_130(self):
        self.assertEqual(len(mindseam._FEATURE_CATALOG), 130)

    def test_recent_window_is_100(self):
        recent = [i for i in self._since_ints() if i >= 170]
        self.assertEqual(len(recent), 100)


if __name__ == "__main__":
    unittest.main()
