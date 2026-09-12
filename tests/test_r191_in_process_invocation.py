# -*- coding: utf-8 -*-
"""Round 191 guards: the suite runs the controller in-process, not per-test.

A real spawn costs ~400 ms -- ~234 ms of interpreter startup plus ~153 ms
of module import -- and the controller itself does ~30 ms of work. An
instrumented run of the 42 test modules that launched children showed
1100 spawns inside a 448 s subset: 98.8% of the wall time was spent
waiting for processes that did almost nothing. The suite was optimising
algorithms that accounted for the remaining 1.2%.

Those helpers now delegate to ``invoke_cli`` in ``_controller_helper``,
which calls ``mindseam.main`` in-process with the same captured-stdout
contract. The measured effect is 460 s -> 58 s for the full suite, same
1685 tests, same result.

This round pins the invariant a future edit must keep: the environment
staging restores exactly, the result shape stays drop-in, and the set of
modules still allowed to spawn a fresh interpreter does not grow. The
child boundary itself stays covered by the modules on that list.
"""

import ast
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import _controller_helper
from _controller_helper import invoke_cli

# Modules that must keep spawning a real interpreter, and why:
#   r122  asserts a child cannot touch root state it does not own
#   r173  runs the SKILL.md example lines as real shell commands
#   r189  drives verify_suite, which itself spawns its own subprocesses
SPAWNING_ALLOWLIST = {
    "test_r122_suite_hygiene.py",
    "test_r173_dry_run_and_skill_examples.py",
    "test_r189_verify_suite_json.py",
    # r209: verify_suite's exit contract IS the process boundary
    # -- the tool must be observed from outside, like r189.
    "test_r209_verify_suite_exit_contract.py",
}


def _subprocess_call_count(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    count = 0
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("run", "Popen", "check_output",
                                       "call", "check_call")
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"):
            count += 1
    return count


class InProcessInvocationTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_invoke_cli_exists_and_is_callable(self):
        self.assertTrue(hasattr(_controller_helper, "invoke_cli"))
        self.assertTrue(callable(_controller_helper.invoke_cli))

    def test_result_shape_is_drop_in_for_subprocess_run(self):
        r = invoke_cli(self.workspace, ["info", "--json"])
        for attr in ("returncode", "stdout", "stderr"):
            self.assertTrue(hasattr(r, attr), attr)
        self.assertIsInstance(r.stdout, str)
        self.assertIsInstance(r.stderr, str)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("ledger", payload)

    def test_stdin_is_delivered(self):
        r = invoke_cli(self.workspace, ["ship", "-"], stdin="plain text\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("clean", r.stdout)

    def test_env_overrides_are_staged_and_restored(self):
        key = "MINDSEAM_INTENSITY"
        had = key in os.environ
        before = os.environ.get(key)
        try:
            os.environ.pop(key, None)
            invoke_cli(self.workspace, ["info"],
                       drop_env=(key,))
            self.assertNotIn(key, os.environ,
                             "drop_env must not leave the key set")
            invoke_cli(self.workspace, ["info"],
                       env={key: "lite"}, drop_env=(key,))
            self.assertNotIn(
                key, os.environ,
                "an env override must be rolled back, not left in os.environ")
        finally:
            if had:
                os.environ[key] = before
            else:
                os.environ.pop(key, None)

    def test_an_env_override_actually_reaches_the_controller(self):
        key = "MINDSEAM_INTENSITY"
        had = key in os.environ
        before = os.environ.get(key)
        try:
            lite = invoke_cli(self.workspace, ["audit", "--json"],
                              env={key: "lite"}, drop_env=(key,))
            self.assertEqual(lite.returncode, 0, lite.stderr)
            # --intensity off refuses; the staged env must reach the same
            # code path the child used to get it through.
            off = invoke_cli(self.workspace, ["audit", "--intensity", "off"])
            self.assertEqual(off.returncode, 2)
        finally:
            if had:
                os.environ[key] = before
            else:
                os.environ.pop(key, None)

    def test_the_spawning_set_does_not_grow(self):
        spawning = {p.name for p in TESTS.glob("test_*.py")
                    if _subprocess_call_count(p)}
        self.assertEqual(
            spawning, SPAWNING_ALLOWLIST,
            "new subprocess spawns: %s / no longer spawning: %s"
            % (spawning - SPAWNING_ALLOWLIST,
               SPAWNING_ALLOWLIST - spawning))

    def test_converted_helpers_delegate_to_invoke_cli(self):
        # A spot check that the mechanical rewrite held: the baseline
        # modules must route through the shared in-process invoker.
        for name in ("test_seam_json_baseline.py",
                     "test_history_subcommand_baseline.py",
                     "test_r188_audit_at_window_exclusive.py"):
            source = (TESTS / name).read_text(encoding="utf-8")
            self.assertIn("invoke_cli(", source, name)
            self.assertNotIn("subprocess.run(", source, name)


if __name__ == "__main__":
    unittest.main()
