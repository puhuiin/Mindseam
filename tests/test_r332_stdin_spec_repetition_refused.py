# -*- coding: utf-8 -*-
"""r332 — pin the repetition guard through the --from-stdin re-parse.

r327 registered every note write flag with ``action="append"`` and moved
the refusal into ``mode_note``, which is the one guard that still has a
per-command call. The reason it survived r328's consolidation is that
``note --from-stdin`` builds its spec through a SECOND ``parse_args``
inside ``read_note_stdin_spec`` (r199), which the universal hook in
``main()`` never sees — and ``mode_note`` receives that merged namespace
whatever produced it.

Probed live this round, and correct: a repeated flag smuggled in
through stdin is refused with exit 2 naming both values, nothing is
written, and a single flag still applies. But NOTHING PINS IT. r199 has
eight tests and r210 six, and none of them drives a repeated flag
through the stdin spec — so if a later round moved the guard to the
argv namespace only (the natural simplification, since that is where
every other command is guarded), the stdin path would silently last-win
again and the suite would stay green.

This round also pins the neighbouring stdin contracts the same probe
verified live and which lack a test: a bad confidence through stdin,
an unknown flag through stdin, and ``--close`` through stdin actually
closing a question.
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

BY = "brute force, n <= 6, including empty"


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
        ws = tempfile.mkdtemp(prefix="r332_")
        self._workspaces.append(ws)
        return ws

    def _book(self):
        prev = os.getcwd()
        try:
            os.chdir(self.ws)
            return mindseam.read_ledger()
        finally:
            os.chdir(prev)

    def _stdin(self, spec, *argv):
        return run_controller(self.ws, "note", "--from-stdin", *argv,
                              stdin=spec)

    def _open_numbers(self):
        out = []
        for row in self._book().get("Open", []):
            m = re.match(r"\?(\d+)", row)
            if m:
                out.append(int(m.group(1)))
        return out


class StdinRepetitionRefusedTests(_Base):
    """A repeated flag in the stdin spec is refused, not last-won."""

    def test_repeated_goal_through_stdin(self):
        r = self._stdin('--goal "a" --goal "b" --next "n"')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --goal was given 2 times", r.stderr)

    def test_repeated_next_through_stdin(self):
        r = self._stdin('--next "one" --next "two"')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --next was given 2 times", r.stderr)

    def test_repeated_open_through_stdin(self):
        r = self._stdin('--open "Q1?" --open "Q2?"')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --open was given 2 times", r.stderr)

    def test_repeated_core_through_stdin(self):
        r = self._stdin('--core "a - f" --core "b - f"')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --core was given 2 times", r.stderr)

    def test_repeated_typed_flag_through_stdin(self):
        r = self._stdin('--next "n" --extra-steps 1 --extra-steps 2')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --extra-steps was given 2 times", r.stderr)
        self.assertIn("(1, 2)", r.stderr)

    def test_repeated_close_through_stdin(self):
        r = self._stdin('--close 1 --close 2 --check "c" --by "%s"' % BY)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --close was given 2 times", r.stderr)

    def test_refusal_names_both_stdin_values(self):
        r = self._stdin('--goal "first" --goal "second" --next "n"')
        self.assertEqual(r.returncode, 2)
        first = r.stderr.splitlines()[0]
        self.assertIn("'first'", first)
        self.assertIn("'second'", first)

    def test_nothing_is_written_on_a_refused_stdin_call(self):
        before = json.dumps(self._book(), sort_keys=True)
        r = self._stdin('--goal "a" --goal "b" --next "n"')
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.dumps(self._book(), sort_keys=True), before)

    def test_three_repeats_report_the_count(self):
        r = self._stdin('--goal "a" --goal "b" --goal "c"')
        self.assertEqual(r.returncode, 2)
        self.assertIn("3 times", r.stderr)


class StdinSingleUseStillAppliesTests(_Base):
    """The guard must not over-reach into the stdin path."""

    def test_single_goal_through_stdin_applies(self):
        r = self._stdin('--goal "from stdin" --next "piped"')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Goal:     from stdin", r.stdout)
        self.assertEqual(self._book()["Goal"], ["from stdin"])

    def test_single_open_through_stdin_applies(self):
        r = self._stdin('--next "nx" --open "Q?" --settled-by "s" '
                        '--confidence strong')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self._open_numbers(), [1])

    def test_single_close_through_stdin_closes(self):
        self._stdin('--next "nx" --open "Q?" --settled-by "s" '
                    '--confidence strong')
        r = self._stdin('--close 1 --check "what holds" --by "%s"' % BY)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self._open_numbers(), [])
        verified = self._book().get("Verified", [])
        self.assertTrue(any("closes: ?01" in row for row in verified),
                        verified)

    def test_single_dry_run_through_stdin_writes_nothing(self):
        before = json.dumps(self._book(), sort_keys=True)
        r = self._stdin('--goal "from stdin" --next "piped"', "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("dry run", r.stdout)
        self.assertEqual(json.dumps(self._book(), sort_keys=True), before)


class StdinOtherRefusalsTests(_Base):
    """The neighbouring stdin refusals the probe verified live."""

    def test_bad_confidence_through_stdin_is_refused(self):
        r = self._stdin('--next "nx" --confidence nope')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("must be strong, thin, or shaky", r.stderr)

    def test_core_without_a_separator_through_stdin_is_refused(self):
        r = self._stdin('--next "nx" --core "no separator"')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Mentioning is not loading", r.stderr)

    def test_empty_stdin_spec_is_refused(self):
        r = self._stdin("")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("read no flags from stdin", r.stderr)

    def test_whitespace_only_stdin_spec_is_refused(self):
        r = self._stdin("   \n  ")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("read no flags from stdin", r.stderr)

    def test_unparseable_stdin_spec_is_refused(self):
        r = self._stdin('--goal "unterminated')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("could not split stdin", r.stderr)

    def test_argv_flag_alongside_stdin_is_refused(self):
        # r199: the argv spec is replaced, not merged, so its flags are
        # named rather than dropped.
        r = self._stdin('--next "piped"', "--goal", "argv goal")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("would be silently dropped", r.stderr)
        self.assertIn("--goal", r.stderr)


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

    def test_entry_present_since_r332_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "stdin-spec-repetition-refused"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r332")
        self.assertTrue(entry["default"])

    def test_r332_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 332)


if __name__ == "__main__":
    unittest.main()
