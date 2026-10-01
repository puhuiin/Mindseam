# -*- coding: utf-8 -*-
"""r331 — pin the contracts the coverage-shaped sweep verified live.

r329 and r330 found defects by sweeping the module for functions no test
names. This round swept the same list against the survivors and probed
each through its caller: ``info --changed`` across seven state-file
shapes, ``info --workspace-id`` / ``--content-hash``, ``ship``'s file
reader across five BOM/encoding shapes plus a directory, cross-face
numeric agreement over five ledger configurations, the open-number
retirement sequence, ``--grep`` / ``--exclude`` case symmetry,
``--filter``'s unknown-key refusal, and the ``--core`` / ``--core-slot``
parking rules.

None of those had a defect. What the sweep did find is that several
contracts the probes confirmed are pinned only on their *message* or not
at all, so a later round could change the behaviour and the suite would
stay green. This file pins the structure behind the messages, which is
the durable half.

- ``--core-slot``'s parking: ``Core[:2]`` is the live pair and a
  displaced or overflow entry lands in ``Core[2:]``. The existing pin
  (``test_core_slot_swap_shows_parking_notice``) asserts only that the
  seam report says "two live at a time", which a display-only change
  would satisfy.
- ``--exclude``'s case-insensitivity and its field scope. ``--grep``'s
  case-insensitivity is noted in a comment in the baseline file;
  ``--exclude`` — the other half of the r310 pair — has no pin, so the
  two could drift apart.
- The open-number retirement end to end. ``next_open_number`` is
  unit-tested against a hand-built book (r128/r147) and the refusal is
  tested (r206), but the CLI sequence open -> close -> open, which is
  what actually guarantees a closed number is never reused, is not.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _controller_helper import invoke_cli, run_controller  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "mindseam", "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import mindseam  # noqa: E402


class _Base(unittest.TestCase):
    def setUp(self):
        self._workspaces = []
        self.ws = self._fresh()
        invoke_cli(self.ws, ["note", "--goal", "ship it",
                             "--next", "verify it"])

    def tearDown(self):
        for ws in self._workspaces:
            shutil.rmtree(ws, ignore_errors=True)

    def _fresh(self):
        ws = tempfile.mkdtemp(prefix="r331_")
        self._workspaces.append(ws)
        return ws

    def _book(self):
        """Read the ledger with the CWD inside this workspace."""
        prev = os.getcwd()
        try:
            os.chdir(self.ws)
            return mindseam.read_ledger()
        finally:
            os.chdir(prev)

    def _core(self):
        return list(self._book().get("Core", []))

    def _open_numbers(self):
        out = []
        for row in self._book().get("Open", []):
            m = re.match(r"\?(\d+)", row)
            if m:
                out.append(int(m.group(1)))
        return out

    def _write_rows(self, rows):
        path = os.path.join(self.ws, ".mindseam", "history.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)


CHECK = "what now holds"
BY = "brute force, n <= 6, including empty"


class CoreParkingStructureTests(_Base):
    """Core[:2] is live; displaced and overflow entries are parked."""

    def test_first_two_entries_are_live(self):
        run_controller(self.ws, "note", "--next", "nx", "--core", "A - one")
        run_controller(self.ws, "note", "--next", "nx", "--core", "B - two")
        self.assertEqual(self._core(), ["A - one", "B - two"])

    def test_third_entry_is_parked_not_live(self):
        for name in ("A - one", "B - two", "C - three"):
            run_controller(self.ws, "note", "--next", "nx", "--core", name)
        core = self._core()
        self.assertEqual(len(core), 3)
        # the first two are unchanged and the new entry is parked
        self.assertEqual(core[:2], ["A - one", "B - two"])
        self.assertEqual(core[2:], ["C - three"])

    def test_slot_swap_parks_the_displaced_entry(self):
        run_controller(self.ws, "note", "--next", "nx", "--core", "A - one")
        run_controller(self.ws, "note", "--next", "nx", "--core", "B - two")
        r = run_controller(self.ws, "note", "--next", "nx",
                           "--core", "C - three", "--core-slot", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        core = self._core()
        # the new entry takes slot 1, the displaced one is parked behind
        self.assertEqual(core[:2], ["C - three", "B - two"])
        self.assertEqual(core[2:], ["A - one"])

    def test_slot_swap_keeps_the_other_live_entry(self):
        run_controller(self.ws, "note", "--next", "nx", "--core", "A - one")
        run_controller(self.ws, "note", "--next", "nx", "--core", "B - two")
        run_controller(self.ws, "note", "--next", "nx", "--core",
                       "C - three", "--core-slot", "2")
        self.assertEqual(self._core()[:2], ["A - one", "C - three"])

    def test_slot_two_before_slot_one_is_refused(self):
        r = run_controller(self.ws, "note", "--next", "nx",
                           "--core", "A - one", "--core-slot", "2")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("live core slot 2 does not exist", r.stderr)
        self.assertEqual(self._core(), [])

    def test_slot_out_of_range_is_refused(self):
        run_controller(self.ws, "note", "--next", "nx", "--core", "A - one")
        r = run_controller(self.ws, "note", "--next", "nx", "--core",
                           "B - two", "--core-slot", "5")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(self._core(), ["A - one"])

    def test_already_live_entry_cannot_be_re_slotted(self):
        run_controller(self.ws, "note", "--next", "nx", "--core", "A - one")
        run_controller(self.ws, "note", "--next", "nx", "--core", "B - two")
        r = run_controller(self.ws, "note", "--next", "nx", "--core",
                           "A - one", "--core-slot", "2")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("already live", r.stderr)
        self.assertEqual(self._core(), ["A - one", "B - two"])

    def test_core_without_a_separator_is_refused(self):
        r = run_controller(self.ws, "note", "--next", "nx",
                           "--core", "no separator here")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Mentioning is not loading", r.stderr)
        self.assertEqual(self._core(), [])

    def test_duplicate_core_is_not_added_twice(self):
        for _ in range(3):
            run_controller(self.ws, "note", "--next", "nx",
                           "--core", "A - one")
        self.assertEqual(self._core(), ["A - one"])


class GrepExcludeSymmetryTests(_Base):
    """--grep and --exclude are the r310 pair: same case, same fields."""

    def _json_rows(self, *extra):
        r = run_controller(self.ws, "history", "--json", *extra)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)["rows"]

    def _nexts(self, *extra):
        return [r["next"] for r in self._json_rows(*extra)]

    def setUp(self):
        super().setUp()
        self._write_rows([
            {"t": 1000, "next": "build: alpha", "msg": "one",
             "verified": 0, "open": 0, "risk": "", "marker": "",
             "confidence": "", "outcome": "", "error": "", "verifier": ""},
            {"t": 2000, "next": "BUILD: BETA", "msg": "two",
             "verified": 0, "open": 0, "risk": "", "marker": "",
             "confidence": "", "outcome": "", "error": "", "verifier": ""},
            {"t": 3000, "next": "deploy: gamma", "msg": "three",
             "verified": 0, "open": 0, "risk": "", "marker": "",
             "confidence": "", "outcome": "", "error": "", "verifier": ""},
        ])

    def test_grep_is_case_insensitive(self):
        self.assertEqual(self._nexts("--grep", "build"),
                         ["build: alpha", "BUILD: BETA"])
        self.assertEqual(self._nexts("--grep", "BUILD"),
                         ["build: alpha", "BUILD: BETA"])
        self.assertEqual(self._nexts("--grep", "bUiLd"),
                         ["build: alpha", "BUILD: BETA"])

    def test_exclude_is_case_insensitive_too(self):
        # The other half of the r310 pair must agree with --grep.
        self.assertEqual(self._nexts("--exclude", "build"),
                         ["deploy: gamma"])
        self.assertEqual(self._nexts("--exclude", "BUILD"),
                         ["deploy: gamma"])
        self.assertEqual(self._nexts("--exclude", "bUiLd"),
                         ["deploy: gamma"])

    def test_both_flags_read_the_same_fields(self):
        # --grep matches on msg as well as next, and --exclude drops the
        # same row, so the pair cannot disagree about what a needle hits.
        self.assertEqual(self._nexts("--grep", "one"), ["build: alpha"])
        self.assertEqual(self._nexts("--exclude", "one"),
                         ["BUILD: BETA", "deploy: gamma"])

    def test_the_pair_partitions_the_same_rows(self):
        kept = self._nexts("--grep", "build")
        dropped = self._nexts("--exclude", "build")
        self.assertEqual(sorted(kept + dropped),
                         sorted(["build: alpha", "BUILD: BETA",
                                 "deploy: gamma"]))

    def test_filter_key_is_case_sensitive(self):
        # --filter speaks exact key=value, so the KEY is exact too.
        r = run_controller(self.ws, "history", "--json",
                           "--filter", "Risk=high")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("is not a history field", r.stderr)


class OpenNumberRetirementTests(_Base):
    """A closed question's number is never reused, end to end."""

    def _open(self, question):
        return run_controller(self.ws, "note", "--next", "nx",
                              "--open", question, "--settled-by", "b",
                              "--confidence", "strong")

    def _close(self, number):
        return run_controller(self.ws, "note", "--close", number,
                              "--check", CHECK, "--by", BY)

    def test_close_then_open_never_reuses_the_number(self):
        for i in (1, 2, 3):
            self._open("Q%d?" % i)
        self.assertEqual(self._open_numbers(), [1, 2, 3])

        r = self._close("2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self._open_numbers(), [1, 3])

        self._open("Qnew?")
        # the closed 2 is retired, so the new question is 4
        self.assertEqual(self._open_numbers(), [1, 3, 4])

    def test_closed_number_is_recorded_on_the_checkpoint(self):
        self._open("Q1?")
        r = self._close("1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        verified = self._book().get("Verified", [])
        self.assertTrue(any("closes: ?01" in row for row in verified),
                        verified)

    def test_closing_the_same_number_twice_refuses(self):
        self._open("Q1?")
        self._close("1")
        r = self._close("1")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("no open question numbered 1", r.stderr)

    def test_close_requires_a_checkpoint_in_the_same_call(self):
        self._open("Q1?")
        r = run_controller(self.ws, "note", "--close", "1")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("closes only against a recorded checkpoint", r.stderr)
        self.assertEqual(self._open_numbers(), [1])

    def test_close_of_an_absent_number_refuses(self):
        r = self._close("9")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("no open question numbered 9", r.stderr)

    def test_stray_un_numbered_row_does_not_block_a_close(self):
        self._open("Q1?")
        path = os.path.join(self.ws, ".mindseam", "WORKSPACE.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace("## Open", "## Open\n  a stray row", 1))
        r = self._close("1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self._open_numbers(), [])


class CatalogPinTests(unittest.TestCase):

    def _since_ints(self):
        out = []
        for e in mindseam._FEATURE_CATALOG:
            since = e.get("since")
            if isinstance(since, str) and since.startswith("r"):
                try:
                    out.append(int(since.lstrip("r")))
                except ValueError:
                    pass
        return out

    def test_entry_present_since_r331_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "sweep-verified-contracts-pinned"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r331")
        self.assertTrue(entry["default"])

    def test_r331_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 331)


if __name__ == "__main__":
    unittest.main()
