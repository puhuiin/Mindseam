# -*- coding: utf-8 -*-
"""r327 — the WRITE path stops silently dropping a repeated flag.

r326 closed history's selectors and audit's window with one shared
mechanism, and named the rest as the remaining carriers. This round
takes the ones where the harm is highest: the flags that WRITE.

``note`` records one value per ledger field and ``seam`` records one
message, and every one of them registered with argparse's default
``store`` action, which keeps only the LAST value. The consequence is
not a wrong projection but a wrong RECORD — the ledger ends up holding
something different from what was asked, with no way to tell afterwards.

Live before-fix (fresh workspace, ledger already open)::

    note --next nx --open "Q1?" --settled-by s1 --open "Q2?" --settled-by s2
      -> rc=0, "Open:     ?01 Q2? — settled by: s2"
         ledger opens: ["?01 Q2? — settled by: s2"]     # Q1 gone
    note --goal a --goal b          -> rc=0, Goal: "b"
    note --core "a — f" --core "b — f" -> rc=0, one core item
    note --check c1 --check c2      -> rc=0, one checkpoint
    seam --dry-run --message a --message b -> rc=0

The ``--open`` case is the sharpest: the tool opens ONE question, prints
a single ``?01`` line, and never hints that a second was asked for — so
a model that queues two questions in one call silently loses the first
and reads the output as success.

The fix reuses r326's mechanism unchanged: the flags register with
``action="append"`` so the repetition is visible at all, then
``refuse_repeated_single_use`` refuses with exit 2 naming every value
given and unwraps the surviving single value back to the scalar
``clean_scalar`` and the rest of ``mode_note`` expect. The refusal runs
BEFORE ``clean_scalar`` reads any dest (a list where a string was
expected is the classic silent break) and covers the r199
``--from-stdin`` path too, because ``mode_note`` receives the merged
namespace whatever produced it.

Scope: note's sixteen ledger-writing flags plus seam's ``--message``.
The remaining read-path store flags (``--format`` on seven commands,
``info --field``/``--explain``/``--index-since``/``--index-until``,
``audit --intensity``/``--tag``/``--at``/``--baseline``/``--baseline-write``)
still last-win — each chooses a different projection or a different read
parameter, so nothing is RECORDED wrongly, and they are the
pre-identified carriers for a later round.
"""

import json
import os
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
        ws = tempfile.mkdtemp(prefix="r327_")
        self._workspaces.append(ws)
        return ws

    def _open_questions(self):
        r = run_controller(self.ws, "resume", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)["ledger"]["open"]


NOTE_CASES = (
    (["--goal", "a", "--goal", "b"], "--goal"),
    (["--next", "na", "--next", "nb"], "--next"),
    (["--core", "a — f1", "--core", "b — f2"], "--core"),
    (["--core-slot", "1", "--core-slot", "2"], "--core-slot"),
    (["--check", "c1", "--check", "c2"], "--check"),
    (["--memory", "x", "--memory", "y"], "--memory"),
    (["--by", "v1", "--by", "v2"], "--by"),
    (["--open", "Q1?", "--open", "Q2?"], "--open"),
    (["--settled-by", "s1", "--settled-by", "s2"], "--settled-by"),
    (["--close", "1", "--close", "2"], "--close"),
    (["--marker", "m1", "--marker", "m2"], "--marker"),
    (["--confidence", "strong", "--confidence", "thin"], "--confidence"),
    (["--verifier", "v1", "--verifier", "v2"], "--verifier"),
    (["--error", "e1", "--error", "e2"], "--error"),
    (["--outcome", "o1", "--outcome", "o2"], "--outcome"),
    (["--extra-steps", "1", "--extra-steps", "2"], "--extra-steps"),
)


class WriteFlagRepetitionRefusedTests(_Base):
    """Every note write flag refuses a repetition."""

    def test_every_note_flag_refuses(self):
        for extra, flag in NOTE_CASES:
            with self.subTest(flag=flag):
                r = run_controller(self.ws, "note", *extra)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("CANNOT: %s was given 2 times" % flag,
                              r.stderr)

    def test_refusal_names_every_value_given(self):
        r = run_controller(self.ws, "note", "--open", "Q1?", "--open",
                           "Q2?")
        self.assertEqual(r.returncode, 2)
        first = r.stderr.splitlines()[0]
        self.assertIn("'Q1?'", first)
        self.assertIn("'Q2?'", first)

    def test_typed_flags_name_their_ints(self):
        r = run_controller(self.ws, "note", "--close", "1", "--close", "2")
        first = r.stderr.splitlines()[0]
        self.assertIn("CANNOT: --close was given 2 times", first)
        self.assertIn("1", first)
        self.assertIn("2", first)

    def test_nothing_is_written_on_a_refused_call(self):
        before = self._read_workspace()
        r = run_controller(self.ws, "note", "--goal", "a", "--goal", "b")
        self.assertEqual(r.returncode, 2)
        after = self._read_workspace()
        self.assertEqual(before, after,
                         "a refused note must not touch the ledger")

    def _read_workspace(self):
        path = os.path.join(self.ws, ".mindseam", "WORKSPACE.md")
        with open(path, encoding="utf-8") as fh:
            return fh.read()


class TheOpenQuestionCarrierTests(_Base):
    """The sharpest case: two questions asked, one recorded, no hint."""

    def test_two_open_questions_in_one_call_is_refused(self):
        r = run_controller(self.ws, "note", "--next", "nx", "--open", "Q1?",
                           "--settled-by", "s1", "--open", "Q2?",
                           "--settled-by", "s2")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --open was given 2 times", r.stderr)

    def test_no_open_question_is_recorded_by_a_refused_call(self):
        r = run_controller(self.ws, "note", "--next", "nx", "--open", "Q1?",
                           "--settled-by", "s1", "--open", "Q2?",
                           "--settled-by", "s2")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self._open_questions(), [])

    def test_one_open_question_still_records(self):
        r = run_controller(self.ws, "note", "--next", "nx", "--open", "Q?",
                           "--settled-by", "s")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self._open_questions()), 1)
        self.assertIn("Q?", self._open_questions()[0])

    def test_refusal_tells_the_host_to_split_the_call(self):
        r = run_controller(self.ws, "note", "--open", "Q1?", "--open", "Q2?")
        self.assertIn("an open question you asked to record is lost",
                      r.stderr)


class SeamMessageTests(_Base):
    """seam --message is a write flag: it lands in the history row."""

    def test_repeated_message_is_refused(self):
        r = run_controller(self.ws, "seam", "--dry-run", "--message", "a",
                           "--message", "b")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --message was given 2 times", r.stderr)

    def test_single_message_is_accepted(self):
        r = run_controller(self.ws, "seam", "--dry-run", "--message", "done")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_msg_alias_is_the_same_dest(self):
        # --msg shares dest=message, so mixing the two spellings twice is
        # a repetition, not a composition.
        r = run_controller(self.ws, "seam", "--dry-run", "--message", "a",
                           "--msg", "b")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --message was given 2 times", r.stderr)

    def test_nothing_is_written_on_a_refused_seam(self):
        before = self._history_bytes()
        r = run_controller(self.ws, "seam", "--dry-run", "--message", "a",
                           "--message", "b")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(before, self._history_bytes())

    def _history_bytes(self):
        path = os.path.join(self.ws, ".mindseam", "history.json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as fh:
            return fh.read()


class SingleUseUnchangedTests(_Base):
    """One value keeps every existing note contract byte-identical."""

    def test_single_values_are_recorded(self):
        r = run_controller(self.ws, "note", "--goal", "one")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Goal:     one", r.stdout)
        r = run_controller(self.ws, "note", "--next", "act")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Next:     act", r.stdout)
        r = run_controller(self.ws, "note", "--core", "c — the fact")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Core:     c — the fact", r.stdout)

    def test_core_slot_two_is_still_reachable(self):
        # --core-slot is one of {1,2} and a single value works, which is
        # how the second core item is recorded in a separate call.
        r = run_controller(self.ws, "note", "--core", "a — f1",
                           "--core-slot", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run_controller(self.ws, "note", "--core", "b — f2",
                           "--core-slot", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run_controller(self.ws, "info", "--json")
        self.assertEqual(json.loads(r.stdout)["ledger"]["core_count"], 2)

    def test_note_dry_run_still_previews(self):
        r = run_controller(self.ws, "note", "--goal", "from a preview",
                           "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("dry run", r.stdout)
        r = run_controller(self.ws, "info", "--json")
        self.assertEqual(json.loads(r.stdout)["ledger"]["goal"], "ship it")

    def test_from_stdin_spec_still_works(self):
        # r199: the stdin spec is parsed by the same note parser, so the
        # append registration must not disturb it.
        r = run_controller(self.ws, "note", "--from-stdin", "--dry-run",
                           stdin='--goal "from stdin" --next "piped"')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("dry run", r.stdout)

    def test_existing_refusals_still_fire(self):
        # An empty needle and a bad confidence are separate refusals and
        # must not be shadowed by the repetition guard.
        r = run_controller(self.ws, "note", "--open", "   ")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("must not be empty", r.stderr)
        r = run_controller(self.ws, "note", "--confidence", "bogus")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("must be strong, thin, or shaky", r.stderr)


class TableTests(unittest.TestCase):
    """The shared table, extended rather than duplicated."""

    def test_note_table_covers_every_write_flag(self):
        dests = {dest for _, dest, _ in mindseam._SINGLE_USE_FLAGS["note"]}
        for dest in ("goal", "next", "core", "core_slot", "check", "memory",
                     "by", "open", "settled_by", "close", "marker",
                     "confidence", "verifier", "error", "outcome",
                     "extra_steps"):
            self.assertIn(dest, dests)

    def test_seam_table_covers_the_message(self):
        self.assertEqual({dest for _, dest, _
                          in mindseam._SINGLE_USE_FLAGS["seam"]},
                         {"message"})

    def test_all_four_commands_are_present(self):
        self.assertEqual(set(mindseam._SINGLE_USE_FLAGS),
                         {"note", "seam", "history", "audit"})

    def test_helper_unwraps_and_reports(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--open", dest="open", action="append",
                            default=None)
        args = parser.parse_args(["--open", "Q?"])
        refused = mindseam.refuse_repeated_single_use(
            args, mindseam._SINGLE_USE_FLAGS["note"])
        self.assertIsNone(refused)
        self.assertEqual(args.open, "Q?")
        args = parser.parse_args(["--open", "Q1?", "--open", "Q2?"])
        refused = mindseam.refuse_repeated_single_use(
            args, mindseam._SINGLE_USE_FLAGS["note"])
        self.assertIsNotNone(refused)
        self.assertIn("CANNOT: --open was given 2 times", refused[0])


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

    def test_entry_present_since_r327_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "write-flag-repetition-refused"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r327")
        self.assertTrue(entry["default"])

    def test_r327_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 327)


if __name__ == "__main__":
    unittest.main()
