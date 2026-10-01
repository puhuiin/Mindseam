# -*- coding: utf-8 -*-
"""r335 — an alias could replace a FLAG, not just a subcommand.

r330 made a subcommand win over an alias: the alias catalog is
host-authored config, so a user alias named ``info`` must not be able to
disable the ``info`` subcommand. That rule was applied to subcommand
names only, and the same hole stayed open one layer out — a FLAG name.

``_expand_alias_argv`` expanded any first token found in the catalog, so
an alias named ``--help`` replaced the help flag:

    aliases.json = {"--help": {"command": "info", "args": ["--version"]}}
      mindseam.py --help  ->  "mindseam 3.6.0"

with no usage text and no indication that a config file had taken the
flag. ``-h`` was reachable the same way. Every flag-shaped name is
affected — ``--help``, ``-h``, ``--json``, ``--strict``, ``--version``
— and so are the two positional separators ``-`` and ``--``.

Live before-fix, with the catalog above:

    expand(['--help'])  -> ['info', '--version']   # the flag is gone
    expand(['-h'])      -> ['info', '--version']
    expand(['--'])      -> ['info', '--version']
    expand(['-'])       -> ['info', '--version']
    mindseam.py --help  -> rc 0, "mindseam 3.6.0"

The fix is one guard, from the same rule r330 states: host-authored
config may ADD names, never REMOVE a built-in one. A name beginning with
``-`` is never expanded, which covers every flag and both separators.

Scope: the ``-`` prefix test. A non-flag alias name is untouched, the
built-in catalog is untouched, and user aliases still override built-in
aliases (r168's ``user_overrides`` contract) — that is a name that
already exists in the catalog, not a built-in flag.
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

FLAG_SHAPED = ("--help", "-h", "--json", "--strict", "--version", "--",
               "-", "--quiet", "--dry-run")


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
        ws = tempfile.mkdtemp(prefix="r335_")
        self._workspaces.append(ws)
        return ws

    def _aliases(self, mapping):
        path = os.path.join(self.ws, ".mindseam", "aliases.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(mapping, fh)


class HelpFlagTests(_Base):
    """The help flag is a built-in: config must not take it."""

    def test_help_alias_does_not_take_the_flag(self):
        self._aliases({"--help": {"command": "info",
                                  "args": ["--version"]}})
        r = run_controller(self.ws, "--help")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("usage:", r.stdout)
        self.assertNotIn("3.6.0", r.stdout.split("usage:")[0])

    def test_short_help_alias_does_not_take_the_flag(self):
        self._aliases({"-h": {"command": "info", "args": ["--version"]}})
        r = run_controller(self.ws, "-h")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("usage:", r.stdout)

    def test_help_still_works_without_any_alias(self):
        r = run_controller(self.ws, "--help")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("usage:", r.stdout)


class ExpansionTests(_Base):
    """The expansion itself: a flag-shaped head is never expanded."""

    def _write_and_expand(self, name, argv):
        self._aliases({name: {"command": "info", "args": ["--version"]}})
        prev = os.getcwd()
        try:
            os.chdir(self.ws)
            return mindseam._expand_alias_argv(list(argv))
        finally:
            os.chdir(prev)

    def test_every_flag_shaped_name_is_returned_unchanged(self):
        for name in FLAG_SHAPED:
            with self.subTest(name=name):
                self.assertEqual(self._write_and_expand(name, [name]), [name])

    def test_a_flag_shaped_name_with_trailing_args(self):
        self.assertEqual(
            self._write_and_expand("--json", ["--json", "extra"]),
            ["--json", "extra"])

    def test_a_normal_alias_still_expands(self):
        self.assertEqual(self._write_and_expand("v", ["v"]),
                         ["info", "--version"])

    def test_a_normal_alias_still_takes_caller_args(self):
        self.assertEqual(self._write_and_expand("v", ["v", "--json"]),
                         ["info", "--version", "--json"])

    def test_a_builtin_alias_still_expands(self):
        prev = os.getcwd()
        try:
            os.chdir(self.ws)
            expanded = mindseam._expand_alias_argv(["audit-ci"])
        finally:
            os.chdir(prev)
        self.assertEqual(expanded[0], "audit")

    def test_empty_argv_is_untouched(self):
        prev = os.getcwd()
        try:
            os.chdir(self.ws)
            self.assertEqual(mindseam._expand_alias_argv([]), [])
        finally:
            os.chdir(prev)


class OtherFlagsSurviveTests(_Base):
    """The guard covers every flag, not only help."""

    def test_a_json_alias_does_not_take_the_flag(self):
        self._aliases({"--json": {"command": "audit", "args": []}})
        # ``--json`` with no subcommand is an argparse error either way,
        # but it must be argparse's error, not a silent audit run.
        r = run_controller(self.ws, "--json")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("usage:", r.stderr)

    def test_a_subcommand_still_wins_over_an_alias(self):
        # r330's rule, re-pinned here so the r335 guard did not break it.
        self._aliases({"info": {"command": "audit", "args": ["--json"]}})
        r = run_controller(self.ws, "info")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("── mindseam ─ info", r.stdout)

    def test_user_override_of_a_builtin_alias_still_wins(self):
        # r168's user_overrides contract: a NAME in the catalog may be
        # redefined. Only built-in FLAGS and SUBCOMMANDS are protected.
        self._aliases({"audit-ci": {"command": "audit",
                                    "args": ["--json", "--intensity",
                                             "full"]}})
        r = run_controller(self.ws, "audit-ci")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["intensity"], "full")


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

    def test_entry_present_since_r335_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "alias-cannot-shadow-a-flag"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r335")
        self.assertTrue(entry["default"])

    def test_r335_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 335)


if __name__ == "__main__":
    unittest.main()
