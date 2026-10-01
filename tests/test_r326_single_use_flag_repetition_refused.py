# -*- coding: utf-8 -*-
"""r326 — every single-use flag refuses a repetition instead of last-winning.

r325 fixed history's text filters: ``--exclude build --exclude deploy``
had exited 0 with the "build: alpha" row still in the output, because
argparse's default ``store`` action keeps only the LAST value. That was
never a filter-specific bug — every single-value flag in the tool
registered the same way, and r325 named the rest as the remaining
carriers.

Live before-fix (fresh workspace, four hand-written rows)::

    history --head 2 --head 5      -> rc=0, 5 rows      # "5" won
    history --tail 4 --tail 2      -> rc=0, 2 rows      # "2" won
    history --row-id 4 --row-id 2  -> rc=0, "row 2 of 4"
    history --fields msg --fields next -> rc=0, header "next"
    history --format %t --format %next -> rc=0, renders %next
    history --since 200000 --since 100000 -> rc=0, last 100000 s
    history --until 2 --until 1    -> rc=0, older than 1 s
    history --keep 1 --keep 2      -> rc=0, rotated to 2 rows
    history --limit 1 --limit 4    -> rc=0, 4 rows
    history -n 4 -n 1              -> rc=0, 1 row
    audit --since 7200 --since 3600 -> rc=0, window 3600

The contrast that proved it was a defect rather than a convention:
``--head`` and ``--tail`` were ALREADY refused when given together
(r208, "mutually exclusive truncation selectors"), so the tool refused
two *different* selectors while silently dropping a *repeated* one —
the same ambiguity, two different answers.

``--keep`` is the worst of the set: it is destructive, so
``--keep 100 --keep 0`` would rotate the file to nothing while the host
believed it had asked to keep 100 rows.

The fix is one shared table (``_SINGLE_USE_FLAGS``) and one shared
helper (``refuse_repeated_single_use``): each flag registers with
``action="append"`` so the repetition is VISIBLE at all — under
``store`` the earlier value is already gone by the time the mode runs —
then the mode refuses with exit 2 naming every value given, and unwraps
the surviving single value back to the scalar every reader expects.

The refusal and the unwrap happen at the TOP of ``mode_history``,
before every other reader of those dests and before the destructive
``--keep`` rotation. That ordering is load-bearing, not stylistic:
``args.row_id`` reaches the r276 ``--row-id`` refusal message as a
formatted value, and the r214/r217 negative-count check compares
``args.keep``/``args.head`` to an integer — a list in either place
crashes or mis-reports. r326's first cut placed the unwrap just above
the negative check, which left ``--row-id 1 --head 2`` printing
"--row-id ['1']" and ``--keep 2`` raising TypeError.

Scope: history's nine single-use flags plus audit's ``--since``/``--until``.
The other subcommands' store flags (``note --message``, ``seam --marker``,
``info --field`` and the rest) still last-win — each is a one-shot value
with no selector semantics, so the harm is lower, and they are the
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

ROWS = [
    {"t": 1000, "next": "build: alpha", "msg": "m1", "verified": 1,
     "open": 0, "risk": "high", "marker": "M1", "confidence": "strong",
     "outcome": "ok", "error": "", "verifier": "alice"},
    {"t": 2000, "next": "deploy: beta", "msg": "m2", "verified": 0,
     "open": 2, "risk": "", "marker": "", "confidence": "shaky",
     "outcome": "", "error": "boom", "verifier": "bob"},
    {"t": 3000, "next": "test: gamma", "msg": "m3", "verified": 3,
     "open": 1, "risk": "high", "marker": "M2", "confidence": "thin",
     "outcome": "ok", "error": "", "verifier": "alice"},
    {"t": 4000, "next": "ship: delta", "msg": "m4", "verified": 2,
     "open": 0, "risk": "", "marker": "", "confidence": "strong",
     "outcome": "ok", "error": "", "verifier": "carol"},
]


class _Base(unittest.TestCase):
    def setUp(self):
        self._workspaces = []
        self.ws = self._fresh()
        invoke_cli(self.ws, ["note", "--goal", "ship it",
                             "--next", "verify it"])
        self._write_rows(ROWS)

    def tearDown(self):
        for ws in self._workspaces:
            shutil.rmtree(ws, ignore_errors=True)

    def _fresh(self):
        ws = tempfile.mkdtemp(prefix="r326_")
        self._workspaces.append(ws)
        return ws

    def _write_rows(self, rows):
        path = os.path.join(self.ws, ".mindseam", "history.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)

    def _history_path(self):
        return os.path.join(self.ws, ".mindseam", "history.json")

    def _json(self, *extra):
        r = run_controller(self.ws, "history", "--json", *extra)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def _header(self, *extra):
        r = run_controller(self.ws, "history", *extra)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        self.assertTrue(lines, r.stdout)
        return lines[0]


class EveryHistoryFlagRefusesRepetitionTests(_Base):
    """The whole history single-use table, one probe per flag."""

    CASES = (
        (["--head", "2", "--head", "5"], "--head"),
        (["--tail", "4", "--tail", "2"], "--tail"),
        (["--limit", "1", "--limit", "4"], "--limit"),
        (["-n", "4", "-n", "1"], "--limit"),
        (["--row-id", "4", "--row-id", "2"], "--row-id"),
        (["--fields", "msg", "--fields", "next"], "--fields"),
        (["--format", "%t", "--format", "%next"], "--format"),
        (["--since", "200000", "--since", "100000"], "--since"),
        (["--until", "2", "--until", "1"], "--until"),
        (["--keep", "1", "--keep", "2"], "--keep"),
        (["--grep", "build", "--grep", "deploy"], "--grep"),
        (["--exclude", "build", "--exclude", "deploy"], "--exclude"),
    )

    def test_every_flag_refuses_a_repetition(self):
        for extra, flag in self.CASES:
            with self.subTest(flag=flag):
                r = run_controller(self.ws, "history", *extra)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("CANNOT: %s was given 2 times" % flag,
                              r.stderr)

    def test_refusal_names_every_value_given(self):
        r = run_controller(self.ws, "history", "--head", "2", "--head", "5")
        self.assertEqual(r.returncode, 2)
        first = r.stderr.splitlines()[0]
        # --head is type=int, so repr() renders bare digits rather than
        # quoted strings — the same for every numeric flag.
        self.assertIn("2", first)
        self.assertIn("5", first)

    def test_text_flags_name_their_strings(self):
        r = run_controller(self.ws, "history", "--fields", "msg",
                           "--fields", "next")
        first = r.stderr.splitlines()[0]
        self.assertIn("'msg'", first)
        self.assertIn("'next'", first)

    def test_typed_flags_name_their_ints(self):
        # --head/--tail/--limit/--keep are type=int, so the values arrive
        # as ints; the message still renders them.
        r = run_controller(self.ws, "history", "--keep", "1", "--keep", "2")
        first = r.stderr.splitlines()[0]
        self.assertIn("CANNOT: --keep was given 2 times", first)
        self.assertIn("1", first)
        self.assertIn("2", first)

    def test_three_repeats_report_the_count(self):
        r = run_controller(self.ws, "history", "--head", "2", "--head", "3",
                           "--head", "4")
        self.assertEqual(r.returncode, 2)
        self.assertIn("3 times", r.stderr)
        for value in ("2", "3", "4"):
            self.assertIn(value, r.stderr.splitlines()[0])

    def test_json_face_refuses_identically(self):
        r = run_controller(self.ws, "history", "--json", "--head", "2",
                           "--head", "5")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertIn("CANNOT: --head was given 2 times", r.stderr)

    def test_refusal_is_stderr_only(self):
        r = run_controller(self.ws, "history", "--tail", "2", "--tail", "3")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")


class AuditWindowTests(_Base):
    """Audit is the other command the probe found last-winning."""

    def test_audit_since_refuses_a_repetition(self):
        r = run_controller(self.ws, "audit", "--since", "7200",
                           "--since", "3600")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --since was given 2 times", r.stderr)

    def test_audit_until_refuses_a_repetition(self):
        r = run_controller(self.ws, "audit", "--until", "7200",
                           "--until", "3600")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --until was given 2 times", r.stderr)

    def test_audit_single_window_still_works(self):
        r = run_controller(self.ws, "audit", "--since", "3600")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Lean already", r.stdout)

    def test_audit_inverted_window_still_refuses(self):
        # r222 is a different refusal and must not be shadowed.
        r = run_controller(self.ws, "audit", "--since", "3600",
                           "--until", "7200")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("is after", r.stderr)

    def test_audit_at_still_works(self):
        r = run_controller(self.ws, "audit", "--at", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class PlacementTests(_Base):
    """The refusal and unwrap run before any other reader."""

    def test_refusal_precedes_the_keep_rotation(self):
        before = open(self._history_path(), encoding="utf-8").read()
        r = run_controller(self.ws, "history", "--keep", "100",
                           "--keep", "0")
        self.assertEqual(r.returncode, 2)
        after = open(self._history_path(), encoding="utf-8").read()
        self.assertEqual(before, after,
                         "a refused call must not rotate history on disk")

    def test_row_id_message_is_not_a_list(self):
        # The r276 --row-id refusal interpolates args.row_id; with the
        # unwrap after it the message rendered "--row-id ['1']".
        r = run_controller(self.ws, "history", "--row-id", "1",
                           "--head", "2")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --row-id 1 composes with none of --head.",
                      r.stderr)
        self.assertNotIn("['1']", r.stderr)

    def test_keep_two_does_not_raise(self):
        # keep_n is read as an int by the negative check and the
        # rotation; a list there raised TypeError.
        r = run_controller(self.ws, "history", "--keep", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("(2 entries)", r.stdout)

    def test_negative_counts_still_refuse(self):
        for case in (["--keep", "-1"], ["--head", "-1"], ["--tail", "-2"],
                     ["--limit", "-3"]):
            with self.subTest(case=case):
                r = run_controller(self.ws, "history", *case)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("non-negative count", r.stderr)

    def test_cross_selector_refusal_not_shadowed(self):
        # r208: --head/--tail/--limit are mutually exclusive when given
        # together, which is what proved the repetition case was a bug.
        r = run_controller(self.ws, "history", "--head", "2", "--tail", "2")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("mutually exclusive truncation", r.stderr)


class SingleUseUnchangedTests(_Base):
    """One value keeps every existing contract byte-identical."""

    def test_text_faces(self):
        cases = (
            (["--head", "2"], "(2 entries)"),
            (["--head", "0"], "(0 entries)"),
            (["--tail", "2"], "(2 entries)"),
            (["--limit", "3"], "(3 entries)"),
            (["-n", "3"], "(3 entries)"),
            (["--row-id", "2"], "(row 2 of 4)"),
            (["--since", "100000"], "last 100000 s"),
            (["--until", "7200"], "older than 7200 s"),
            (["--keep", "2"], "(2 entries)"),
            (["--grep", "build"], "grep 'build'"),
            (["--exclude", "deploy"], "exclude 'deploy'"),
        )
        for extra, expected in cases:
            with self.subTest(extra=extra):
                self.assertIn(expected, self._header(*extra))

    def test_projection_faces(self):
        r = run_controller(self.ws, "history", "--fields", "next,verified")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], "next\tverified")
        r = run_controller(self.ws, "history", "--format", "%h %next")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], "1 build: alpha")

    def test_payload_scalars(self):
        payload = self._json()
        self.assertIsNone(payload["since"])
        self.assertIsNone(payload["until"])
        self.assertIsNone(payload["grep"])
        self.assertIsNone(payload["exclude"])
        payload = self._json("--head", "2")
        self.assertEqual(len(payload["rows"]), 2)
        payload = self._json("--since", "100000")
        self.assertEqual(payload["since"], 100000)
        self.assertIsNone(payload["until"])
        payload = self._json("--grep", "build")
        self.assertEqual(payload["grep"], "build")
        self.assertIsNone(payload["exclude"])

    def test_payload_key_set_is_unchanged(self):
        payload = self._json()
        self.assertEqual(sorted(payload.keys()),
                         ["exclude", "grep", "history_count", "limit",
                          "reverse", "rows", "since", "until", "untrusted"])

    def test_single_values_still_filter(self):
        # --head takes from the oldest end and --tail from the newest, so
        # the two selectors are distinguishable after the unwrap.
        payload = self._json("--head", "2")
        self.assertEqual([r["next"] for r in payload["rows"]],
                         ["build: alpha", "deploy: beta"])
        payload = self._json("--tail", "2")
        self.assertEqual([r["next"] for r in payload["rows"]],
                         ["test: gamma", "ship: delta"])
        payload = self._json("--row-id", "3")
        # the single-row face carries its own shape, not a rows array
        self.assertEqual(payload["row"]["next"], "test: gamma")

    def test_head_zero_is_not_a_false_positive(self):
        # 0 is a real value; the default is None, so only a second
        # occurrence trips the refusal.
        r = run_controller(self.ws, "history", "--head", "0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("(0 entries)", r.stdout)

    def test_limit_alias_shares_one_dest(self):
        # --limit and -n share dest=limit, so mixing them twice is a
        # repetition, not a composition.
        r = run_controller(self.ws, "history", "--limit", "3", "-n", "2")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --limit was given 2 times", r.stderr)


class SharedHelperTests(unittest.TestCase):
    """The helper is the one mechanism, not eleven copies."""

    def test_helper_unwraps_a_single_value(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--head", dest="head", type=int,
                            action="append", default=None)
        args = parser.parse_args(["--head", "2"])
        refused = mindseam.refuse_repeated_single_use(
            args, [("--head", "head", "the kept rows are wrong")])
        self.assertIsNone(refused)
        self.assertEqual(args.head, 2)

    def test_helper_reports_a_repetition(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--head", dest="head", type=int,
                            action="append", default=None)
        args = parser.parse_args(["--head", "2", "--head", "5"])
        refused = mindseam.refuse_repeated_single_use(
            args, [("--head", "head", "the kept rows are wrong")])
        self.assertIsNotNone(refused)
        self.assertIn("CANNOT: --head was given 2 times", refused[0])
        self.assertIn("the kept rows are wrong", refused[1])

    def test_helper_leaves_a_plain_scalar_alone(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--head", dest="head", type=int, default=None)
        args = parser.parse_args(["--head", "2"])
        refused = mindseam.refuse_repeated_single_use(
            args, [("--head", "head", "unused")])
        self.assertIsNone(refused)
        self.assertEqual(args.head, 2)

    def test_table_covers_every_history_single_use_flag(self):
        dests = {dest for _, dest, _ in
                 mindseam._SINGLE_USE_FLAGS["history"]}
        for dest in ("head", "tail", "limit", "row_id", "fields", "format",
                     "since", "until", "keep", "grep", "exclude"):
            self.assertIn(dest, dests)

    def test_audit_table_covers_its_window(self):
        # r326 shipped audit with its two window flags; r328 completed the
        # command's whole single-use set. The window pair is still in.
        dests = {dest for _, dest, _ in mindseam._SINGLE_USE_FLAGS["audit"]}
        self.assertIn("since", dests)
        self.assertIn("until", dests)
        self.assertEqual(dests, {"since", "until", "intensity", "tag", "at",
                                 "baseline", "baseline_write", "format_path",
                                 "explain"})

    def test_filter_is_deliberately_absent(self):
        # --filter is genuinely repeatable (ANDed); it must never join
        # the single-use table.
        for cmd in ("history", "audit"):
            dests = {dest for _, dest, _
                     in mindseam._SINGLE_USE_FLAGS[cmd]}
            self.assertNotIn("filter", dests)


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

    def test_entry_present_since_r326_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "single-use-flag-repetition-refused"),
                     None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r326")
        self.assertTrue(entry["default"])

    def test_r326_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 326)


if __name__ == "__main__":
    unittest.main()
