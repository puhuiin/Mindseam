# -*- coding: utf-8 -*-
"""r333 — an unreadable history is disclosed, not reported as empty.

``read_history`` returns ``(rows, changed, repair_reasons)``. A history
that cannot be READ at all — corrupt JSON, a directory where the file
belongs, a non-list root — comes back as an EMPTY list plus a reason.
``mode_seam`` and ``mode_resume`` already surface those reasons through
``state_repairs``, but five other commands took only ``[0]`` and threw
the reason away:

    mode_ship      hist = read_history()[0]
    mode_history   hist = read_history()[0]
    mode_info      hist = read_history()[0]
    mode_skillbook hist = read_history()[0]
    mode_discover  hist = read_history()[0]

For a ledger holding rows, that turned a read failure into a plausible
empty result. The worst of the five is ``info``, because ``--check`` is
the documented gate — "the exit code is 0 only if the ledger passes;
otherwise 2" — and it answered ``valid: true``, exit 0, for a file it
could not read at all. The classifier walked ``hist``, and an empty
``hist`` has no bad rows to find.

Live before-fix, on a workspace with four history rows:

    history.json is a directory   -> info --check rc=0 "ledger: ok"
    history.json is corrupt JSON  -> info --check rc=0 "ledger: ok"
    history root is not a list    -> info --check rc=0 "ledger: ok"

and ``info --json`` said "no seams recorded yet — the first seam will
populate the digest" with history_count 0, indistinguishable from a
workspace that has never run a seam.

The fix threads the repair reasons into ``mode_info``'s two classifiers:
``_info_check_issues`` reports them first (so ``--check`` gates), and
``_info_warnings`` reports them and stops promising that "the first seam
will populate the digest" — for a damaged file that promise is false.
The genuinely fresh workspace is unchanged: no history file means no
repair reasons, so ``--check`` still exits 0 and the warning is still
the original one.

Scope: ``mode_info`` only. ``history``/``ship``/``skillbook``/``discover``
still discard the reasons — each is a separate disclosure decision with
its own face shape, and the gate is where the wrong answer had teeth.
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

ROWS = [{"t": 1000 + i * 100, "next": "build: step%d" % i, "msg": "m",
         "verified": i, "open": 0, "risk": "high", "marker": "M",
         "confidence": "strong", "outcome": "ok", "error": "",
         "verifier": "a", "extra_steps": 0} for i in range(4)]


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
        ws = tempfile.mkdtemp(prefix="r333_")
        self._workspaces.append(ws)
        return ws

    def _history_path(self):
        return os.path.join(self.ws, ".mindseam", "history.json")

    def _write_rows(self, rows):
        path = self._history_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)

    def _break_history(self, how):
        path = self._history_path()
        # A previous subTest may have left a DIRECTORY here, so clear
        # whichever shape is present before building the next one.
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
        if how == "directory":
            os.makedirs(path)
        elif how == "corrupt":
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{not json")
        elif how == "non-list-root":
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"a": 1}')
        else:
            raise ValueError(how)

    def _check(self):
        return run_controller(self.ws, "info", "--check")

    def _check_json(self):
        r = run_controller(self.ws, "info", "--check", "--json")
        return r, json.loads(r.stdout)

    def _info_json(self):
        r = run_controller(self.ws, "info", "--json")
        return r, json.loads(r.stdout)


class CheckGateTests(_Base):
    """The documented gate must fail on a history it cannot read."""

    def test_check_fails_on_a_directory(self):
        self._break_history("directory")
        r = self._check()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("history:", r.stdout)

    def test_check_fails_on_corrupt_json(self):
        self._break_history("corrupt")
        r = self._check()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_check_fails_on_a_non_list_root(self):
        self._break_history("non-list-root")
        r = self._check()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_check_json_reports_invalid(self):
        for how in ("directory", "corrupt", "non-list-root"):
            with self.subTest(how=how):
                self._break_history(how)
                r, payload = self._check_json()
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertFalse(payload["valid"])
                self.assertTrue(any("history:" in i
                                    for i in payload["issues"]))

    def test_the_issue_names_the_read_failure(self):
        self._break_history("corrupt")
        r, payload = self._check_json()
        blob = " ".join(payload["issues"])
        self.assertIn("unreadable", blob)

    def test_check_still_passes_on_a_healthy_history(self):
        # The fixture rows are stamped in 1970, so a genuinely healthy
        # read still trips the long-gap issue. Re-stamp them as recent
        # so this test isolates the read-failure signal.
        import time
        now = int(time.time())
        self._write_rows([dict(row, t=now - 60) for row in ROWS])
        r = self._check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ledger: ok", r.stdout)

    def test_check_still_passes_with_no_history_file(self):
        # A fresh workspace is not a damaged one.
        os.remove(self._history_path())
        r = self._check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r, payload = self._check_json()
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["issues"], [])


class InfoWarningsTests(_Base):
    """The digest must not promise a fresh start for a damaged file."""

    def test_warning_names_the_read_failure(self):
        self._break_history("corrupt")
        r, payload = self._info_json()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(any("could not be read cleanly" in w
                            for w in payload["warnings"]),
                        payload["warnings"])

    def test_warning_no_longer_promises_a_fresh_start(self):
        self._break_history("corrupt")
        r, payload = self._info_json()
        blob = " ".join(payload["warnings"])
        self.assertNotIn("no seams recorded yet", blob)
        self.assertIn("could not be read", blob)

    def test_text_face_prints_the_warning(self):
        self._break_history("directory")
        r = run_controller(self.ws, "info")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("could not be read cleanly", r.stdout)

    def test_warnings_only_carries_it_too(self):
        self._break_history("corrupt")
        r = run_controller(self.ws, "info", "--warnings-only")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("could not be read cleanly", r.stdout)

    def test_fresh_workspace_keeps_the_original_warning(self):
        os.remove(self._history_path())
        r, payload = self._info_json()
        self.assertIn("no seams recorded yet — the first seam will populate "
                      "the digest", payload["warnings"])

    def test_healthy_history_has_no_repair_warning(self):
        import time
        now = int(time.time())
        self._write_rows([dict(row, t=now - 60) for row in ROWS])
        r, payload = self._info_json()
        blob = " ".join(payload["warnings"])
        self.assertNotIn("could not be read cleanly", blob)


class HelperContractTests(unittest.TestCase):
    """The two classifiers take the reasons and default to none."""

    def test_check_issues_defaults_to_no_repairs(self):
        issues = mindseam._info_check_issues(
            {"Goal": ["g"], "Next": ["n"]}, [], None)
        self.assertEqual(issues, [])

    def test_check_issues_reports_each_reason(self):
        issues = mindseam._info_check_issues(
            {"Goal": ["g"], "Next": ["n"]}, [], None,
            hist_repairs=["history was unreadable and has been restarted"])
        self.assertEqual(len(issues), 1)
        self.assertIn("history:", issues[0])

    def test_warnings_defaults_to_no_repairs(self):
        # No repair reasons means the ordinary empty-history warning,
        # not the read-failure one.
        warns = mindseam._info_warnings({"Goal": ["g"], "Next": ["n"]}, [], None)
        self.assertEqual(len(warns), 1)
        self.assertIn("no seams recorded yet", warns[0])

    def test_warnings_reports_reasons_and_drops_the_fresh_promise(self):
        warns = mindseam._info_warnings(
            {"Goal": ["g"], "Next": ["n"]}, [], None,
            hist_repairs=["history root was not a list and has been restarted"])
        blob = " ".join(warns)
        self.assertIn("could not be read cleanly", blob)
        self.assertIn("could not be read", blob)
        self.assertNotIn("no seams recorded yet", blob)


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

    def test_entry_present_since_r333_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "unreadable-history-disclosed"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r333")
        self.assertTrue(entry["default"])

    def test_r333_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 333)


if __name__ == "__main__":
    unittest.main()
