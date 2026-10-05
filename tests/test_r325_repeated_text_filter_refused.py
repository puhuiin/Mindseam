# -*- coding: utf-8 -*-
"""r325 — a repeated --grep / --exclude is refused, not silently dropped.

``mode_history`` registered ``--grep`` and ``--exclude`` with argparse's
default ``store`` action, so a second value simply overwrote the first::

    history --exclude build --exclude deploy

exited 0 reading ``exclude 'deploy'`` and LEFT THE "build: alpha" ROW IN
THE OUTPUT — the exact row the first flag asked to drop. The caller sees
rows it explicitly ruled out and cannot tell, because the header and the
``exclude`` payload key both report only the value that won.

 Unlike a purely undisclosed flag, this is a WRONG ANSWER: the result
 contradicts the instruction it was given. It is the r188/r205
 silent-wrong-at-exit-0 family, on the text-filter pair r310 already
 refuses as a pair (an empty needle from either flag is refused the same
 way).

The fix registers both flags with ``action="append"`` so the repetition
is visible at all, then refuses it with exit 2 before anything is read —
and ahead of the destructive ``--keep`` rotation, so a refused call never
touches disk. A single needle unwraps back to the scalar the rest of
``mode_history`` and both faces expect, so the payload key and the
header clause keep their shape byte-for-byte.

Scope: only ``history``'s two text filters are fixed. ``audit`` has no
``--grep``/``--exclude`` (argparse rejects them), and the other
single-value flags on ``history`` (``--since``, ``--until``, ``--head``,
``--tail``, ``--limit``, ``--fields``, ``--format``, ``--row-id``) still
last-win — pre-identified as the family's remaining carriers, each of
which needs the same treatment but only the text-filter pair loses a ROW
the caller explicitly excluded.

Probe (before the fix), on a three-row history::

    history --grep build --grep deploy
      -> rc=0, "── mindseam ─ history (1 entry, grep 'deploy')"
         rows: [deploy: beta]      # "build: alpha" silently dropped
    history --exclude build --exclude deploy
      -> rc=0, "── mindseam ─ history (2 entries, exclude 'deploy')"
         rows: [build: alpha, test: gamma]   # the row it excluded

After the fix both exit 2 with a message naming every value given.
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
        ws = tempfile.mkdtemp(prefix="r325_")
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


class RepeatedFlagRefusedTests(_Base):
    """The defect: a second value was silently dropped."""

    def test_repeated_grep_is_refused(self):
        r = run_controller(self.ws, "history", "--grep", "build",
                           "--grep", "deploy")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --grep was given 2 times", r.stderr)

    def test_repeated_exclude_is_refused(self):
        r = run_controller(self.ws, "history", "--exclude", "build",
                           "--exclude", "deploy")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --exclude was given 2 times", r.stderr)

    def test_refusal_names_every_value_given(self):
        # The host can see exactly what it passed, so the message is
        # actionable rather than a bare count.
        r = run_controller(self.ws, "history", "--exclude", "build",
                           "--exclude", "deploy")
        self.assertEqual(r.returncode, 2)
        first = r.stderr.splitlines()[0]
        self.assertIn("'build'", first)
        self.assertIn("'deploy'", first)

    def test_three_repeats_report_the_count(self):
        r = run_controller(self.ws, "history", "--grep", "a",
                           "--grep", "b", "--grep", "c")
        self.assertEqual(r.returncode, 2)
        self.assertIn("3 times", r.stderr)
        for needle in ("'a'", "'b'", "'c'"):
            self.assertIn(needle, r.stderr.splitlines()[0])

    def test_refusal_goes_to_stderr_with_empty_stdout(self):
        r = run_controller(self.ws, "history", "--grep", "a",
                           "--grep", "b")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertTrue(r.stderr.strip())

    def test_json_face_refuses_too(self):
        r = run_controller(self.ws, "history", "--json", "--grep", "a",
                           "--grep", "b")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertIn("CANNOT: --grep was given 2 times", r.stderr)

    def test_both_flags_repeated_is_refused(self):
        r = run_controller(self.ws, "history", "--grep", "a", "--grep", "b",
                           "--exclude", "c", "--exclude", "d")
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT: --grep was given 2 times", r.stderr)


class RefusalPrecedesDestructionTests(_Base):
    """The refusal fires before the --keep rotation, per r276."""

    def test_keep_rotation_never_runs_on_a_refused_call(self):
        before = open(self._history_path(), encoding="utf-8").read()
        r = run_controller(self.ws, "history", "--grep", "a", "--grep", "b",
                           "--keep", "0")
        self.assertEqual(r.returncode, 2)
        after = open(self._history_path(), encoding="utf-8").read()
        self.assertEqual(before, after,
                         "a refused call must not rotate history on disk")

    def test_refusal_fires_before_any_row_selection(self):
        # --row-id composes with neither flag, but whichever guard
        # answers, the call must refuse rather than silently narrow.
        r = run_controller(self.ws, "history", "--row-id", "1",
                           "--grep", "a", "--grep", "b")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


class SingleNeedleUnchangedTests(_Base):
    """A single needle keeps every existing contract byte-identical."""

    def test_single_grep_text_face_unchanged(self):
        self.assertEqual(self._header("--grep", "build"),
                         "── mindseam ─ history (1 entry, grep 'build')")

    def test_single_exclude_text_face_unchanged(self):
        self.assertEqual(self._header("--exclude", "deploy"),
                         "── mindseam ─ history (2 entries, "
                         "exclude 'deploy')")

    def test_single_grep_payload_key_is_a_scalar(self):
        payload = self._json("--grep", "build")
        self.assertEqual(payload["grep"], "build")
        self.assertIsNone(payload["exclude"])
        self.assertEqual(len(payload["rows"]), 1)

    def test_single_exclude_payload_key_is_a_scalar(self):
        payload = self._json("--exclude", "deploy")
        self.assertEqual(payload["exclude"], "deploy")
        self.assertIsNone(payload["grep"])
        self.assertEqual(len(payload["rows"]), 2)

    def test_no_flag_payload_keys_and_values_unchanged(self):
        payload = self._json()
        self.assertEqual(sorted(payload.keys()),
                         ["empty", "exclude", "filter", "grep", "head",
                          "history_count", "keep", "limit", "reverse",
                          "rows", "since", "until", "untrusted"])
        for key in ("grep", "exclude", "since", "until"):
            self.assertIsNone(payload[key])

    def test_single_needle_still_filters(self):
        payload = self._json("--grep", "build")
        self.assertEqual([r["next"] for r in payload["rows"]],
                         ["build: alpha"])
        payload = self._json("--exclude", "deploy")
        self.assertEqual([r["next"] for r in payload["rows"]],
                         ["build: alpha", "test: gamma"])

    def test_empty_single_needle_still_refuses(self):
        # r310: the empty-needle refusal is independent of this fix.
        for flag in ("--grep", "--exclude"):
            r = run_controller(self.ws, "history", flag, "")
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("received an empty value", r.stderr)

    def test_row_id_still_refuses_both_flags(self):
        for flag in ("--grep", "--exclude"):
            r = run_controller(self.ws, "history", "--row-id", "1",
                               flag, "a")
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("composes with none of %s" % flag, r.stderr)


class RegistrationTests(unittest.TestCase):
    """The flags are append-registered, which is what makes the refusal
    possible at all."""

    def test_grep_and_exclude_use_append(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--grep", dest="grep", action="append",
                            default=None)
        ns = parser.parse_args(["--grep", "a", "--grep", "b"])
        self.assertEqual(ns.grep, ["a", "b"])
        ns = parser.parse_args([])
        self.assertIsNone(ns.grep)
        ns = parser.parse_args(["--grep", "a"])
        self.assertEqual(ns.grep, ["a"])

    def test_source_registers_both_with_append(self):
        path = os.path.join(SCRIPTS, "mindseam.py")
        src = open(path, encoding="utf-8").read()
        for flag in ("--grep", "--exclude"):
            self.assertIn('"%s", dest="%s", action="append"'
                          % (flag, flag.lstrip("-")), src,
                          "%s must register with action=append" % flag)


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

    def test_entry_present_since_r325_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "repeated-text-filter-refused"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r325")
        self.assertTrue(entry["default"])

    def test_r325_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 325)


if __name__ == "__main__":
    unittest.main()
