# -*- coding: utf-8 -*-
"""r330 — an alias could shadow a subcommand and disable it.

``_expand_alias_argv`` resolves a bare alias name before argparse sees
the argv (r168, borrowing ``git co`` -> ``git checkout``). The lookup
consulted only the alias catalog, which is BUILT-IN aliases merged with
the host-authored ``.mindseam/aliases.json``. A user alias therefore won
over a registered subcommand of the same name.

Live before-fix (workspace with ``.mindseam/aliases.json`` holding
``{"info": {"command": "audit", "args": ["--json"]}}``)::

    mindseam.py info    -> runs audit --json, the info report is gone
    {"note": {"command": "resume"}}:
    mindseam.py note --goal g --next n  -> runs resume, note is gone

A host-authored config file could silently disable any subcommand, and
the caller gets a successful run of the wrong command — the r188/r205
silent-wrong-at-exit-0 family, one layer out: not a dropped flag inside
a call but a dropped COMMAND before the parser sees it.

``git config alias.add ...`` does not shadow ``git add`` — the built-in
wins — so the fix mirrors the borrower: a subcommand name is never
expanded, whatever the catalog says. User aliases may still override
BUILT-IN aliases (r168's ``user_overrides`` contract), which is why the
guard is on subcommand names only.

Found by the same coverage-shaped sweep as r329: ``_expand_alias_argv``
was one of the module's sixteen functions never named in any test.
"""

import ast
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
        ws = tempfile.mkdtemp(prefix="r330_")
        self._workspaces.append(ws)
        return ws

    def _write_aliases(self, mapping):
        path = os.path.join(self.ws, ".mindseam", "aliases.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(mapping, fh)

    def _remove_aliases(self):
        path = os.path.join(self.ws, ".mindseam", "aliases.json")
        if os.path.exists(path):
            os.remove(path)


class SubcommandWinsTests(_Base):
    """A subcommand name is never replaced by an alias."""

    def test_user_alias_named_info_does_not_shadow_info(self):
        self._write_aliases({"info": {"command": "audit",
                                      "args": ["--json"]}})
        r = run_controller(self.ws, "info")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("── mindseam ─ info", r.stdout)
        self.assertIn("Version:", r.stdout)

    def test_user_alias_named_note_does_not_shadow_note(self):
        self._write_aliases({"note": {"command": "resume", "args": []}})
        r = run_controller(self.ws, "note", "--goal", "one")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Goal:     one", r.stdout)

    def test_user_alias_named_history_does_not_shadow_history(self):
        self._write_aliases({"history": {"command": "audit", "args": []}})
        r = run_controller(self.ws, "history", "--count")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "0")

    def test_user_alias_named_ship_does_not_shadow_ship(self):
        self._write_aliases({"ship": {"command": "resume", "args": []}})
        r = run_controller(self.ws, "ship", "-", stdin="draft.")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_every_subcommand_survives_an_alias_of_its_name(self):
        self._write_aliases({name: {"command": "resume", "args": []}
                             for name in mindseam._SUBCOMMANDS})
        for name in sorted(mindseam._SUBCOMMANDS):
            with self.subTest(cmd=name):
                r = run_controller(self.ws, name, "--help")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class UserOverrideStillWorksTests(_Base):
    """r168: user aliases override BUILT-IN aliases."""

    def test_builtin_alias_still_expands(self):
        self._remove_aliases()
        r = run_controller(self.ws, "audit-ci")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["intensity"], "lite")

    def test_user_alias_overrides_a_builtin_name(self):
        # The guard is on subcommand names only, so a user alias that
        # redefines a built-in ALIAS still wins over the built-in.
        self._write_aliases({"audit-ci": {"command": "audit",
                                         "args": ["--json",
                                                  "--intensity",
                                                  "full"]}})
        r = run_controller(self.ws, "audit-ci")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["intensity"], "full")

    def test_custom_alias_name_still_expands(self):
        self._write_aliases({"probe": {"command": "info",
                                       "args": ["--version"]}})
        r = run_controller(self.ws, "probe")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("3.6.0", r.stdout)

    def test_unknown_first_token_is_not_expanded(self):
        self._write_aliases({})
        r = run_controller(self.ws, "no-such-command")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


class DriftProofTests(unittest.TestCase):
    """The subcommand set must match the parser registration."""

    def _registered(self):
        src = open(os.path.join(SCRIPTS, "mindseam.py"), encoding="utf-8").read()
        tree = ast.parse(src)
        names = set()
        for node in ast.walk(tree):
            if type(node).__name__ != "Call":
                continue
            func = node.func
            if (type(func).__name__ == "Attribute"
                    and func.attr == "add_parser" and node.args
                    and type(node.args[0]).__name__ == "Constant"):
                names.add(node.args[0].value)
        return names

    def test_subcommand_set_matches_the_registration(self):
        self.assertEqual(set(mindseam._SUBCOMMANDS), self._registered())

    def test_no_subcommand_is_missing_from_the_guard(self):
        for name in self._registered():
            self.assertIn(name, mindseam._SUBCOMMANDS, name)

    def test_expansion_returns_argv_unchanged_for_a_subcommand(self):
        original = ["info", "--version"]
        self.assertEqual(mindseam._expand_alias_argv(original), original)

    def test_expansion_returns_empty_argv_unchanged(self):
        self.assertEqual(mindseam._expand_alias_argv([]), [])

    def test_expansion_still_resolves_an_alias(self):
        # The built-in catalog alone, with no user file: the alias's own
        # args come first and the caller's argv is appended after.
        argv = ["audit-ci", "--tag", "delete"]
        expanded = mindseam._expand_alias_argv(argv)
        self.assertEqual(expanded[0], "audit")
        self.assertIn("--json", expanded)
        self.assertIn("--intensity", expanded)
        self.assertIn("--tag", expanded)
        self.assertEqual(expanded[-2:], ["--tag", "delete"])


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

    def test_entry_present_since_r330_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "alias-cannot-shadow-subcommand"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r330")
        self.assertTrue(entry["default"])

    def test_r330_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 330)


if __name__ == "__main__":
    unittest.main()
