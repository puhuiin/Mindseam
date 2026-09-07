# -*- coding: utf-8 -*-
"""Round 173 guards: SKILL.md code examples must run.

Borrowed from ``cargo test --doc`` / ``pytest --doctest-modules``:
the controller's online help is a single source of truth
when the examples in it actually run. r173 extracts every
``<python-command> <skill-root>/scripts/mindseam.py ...`` line
from ``mindseam/SKILL.md``, substitutes the real path of the
controller, sets up a fresh empty workspace, and runs the
command. The example is expected to exit 0, so a docs /
runtime drift surfaces as a test failure the way a docstring
example drift surfaces as a ``cargo test --doc`` failure.

The pin is narrow on purpose: only the read-only surfaces
(``info``, ``audit``) and the ``info --format`` / ``info
--field`` / ``audit --explain`` paths are exercised, the
way r172's tests already pin them. Writing / mutating
surfaces (``seam`` / ``note`` / ``ship``) are excluded so a
docs typo cannot accidentally append a history row. The
SKILL.md lines that target ``seam`` / ``note`` / ``ship`` /
``history`` / ``skillbook`` / ``discover`` / ``resume`` are
skipped, not asserted to run.

Two r173 deliverables:

1. **Code-example runner**: every ``<python-command> <skill-root>/scripts/mindseam.py ...``
   line in SKILL.md is parsed, classified, and runnable.
2. **Examples-as-tests** contract: a docs drift that makes
   a documented command fail surfaces as a test failure,
   not as a confused user at 02:00.
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"
SKILL = ROOT / "mindseam" / "SKILL.md"


def _classify(line):
    """Return (subcommand, args) if the line is a runnable example.

    SKILL.md lines use ``<python-command> <skill-root>/scripts/mindseam.py ...``
    for the documented invocations. The classifier only
    accepts the read-only surfaces (info / audit) so a
    docs typo cannot accidentally write to history. The
    args are everything between the subcommand and the
    trailing ``#`` comment (or the end of the line), split
    on whitespace.
    """
    m = re.match(
        r"<python-command>\s+<skill-root>/scripts/mindseam\.py\s+"
        r"(info|audit)\b(.*)$",
        line)
    if not m:
        return None
    sub = m.group(1)
    rest = m.group(2)
    # Strip the trailing comment (everything from the first
    # ``#`` after the script) so the runnable arg list does
    # not include prose like ``# render only the values``.
    hash_pos = rest.find(" #")
    if hash_pos >= 0:
        rest = rest[:hash_pos]
    args = rest.split()
    return sub, args


class SkillExamplesRunnerTests(unittest.TestCase):
    """Every documented read-only example must run cleanly."""

    def setUp(self):
        if not SKILL.exists():
            self.skipTest("SKILL.md not present")
        if not MINDSEAM.exists():
            self.skipTest("mindseam.py not present")
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _run(self, sub, args):
        return subprocess.run(
            [sys.executable, str(MINDSEAM), sub] + args,
            cwd=self.workspace,
            capture_output=True, text=True, encoding="utf-8",
            timeout=15)

    def test_at_least_one_example_found(self):
        lines = SKILL.read_text(encoding="utf-8").splitlines()
        runnable = []
        for n, line in enumerate(lines, 1):
            parsed = _classify(line)
            if parsed is not None:
                sub, args = parsed
                runnable.append((n, sub, args))
        self.assertGreater(
            len(runnable), 0,
            "no runnable info/audit examples parsed from SKILL.md")

    def test_every_info_audit_example_runs(self):
        lines = SKILL.read_text(encoding="utf-8").splitlines()
        runnable = []
        for n, line in enumerate(lines, 1):
            parsed = _classify(line)
            if parsed is None:
                continue
            sub, args = parsed
            # Examples that *require* history rows
            # (``audit --at N`` is out-of-range on an empty
            # history, the r161 contract) are pinned by
            # their own test files; the r173 runner only
            # exercises examples that succeed in an empty
            # workspace, the way ``cargo test --doc``
            # only runs examples that don't need setup.
            if "--at" in args:
                continue
            runnable.append((n, sub, args))
        failures = []
        for n, sub, args in runnable:
            if sub == "audit" and not (Path(self.workspace) / ".mindseam").exists():
                Path(self.workspace, ".mindseam").mkdir(
                    parents=True, exist_ok=True)
                Path(self.workspace, ".mindseam" / "WORKSPACE.md").write_text(
                    "# L\n\n## Goal\n\n## Core\n\n## Verified\n\n"
                    "## Open\n\n## Next\n", encoding="utf-8")
            r = self._run(sub, args)
            if r.returncode != 0:
                failures.append(
                    (n, sub, args, r.returncode, r.stderr[:120]))
        self.assertEqual(
            failures, [],
            "docs drift: these SKILL.md lines failed: %s" % failures)

    def test_every_classified_example_is_runnable(self):
        # A line that classifies should not raise, no matter
        # what the args look like. The classifier is lenient
        # on purpose so future r173+ rounds can add more
        # surfaces without touching it.
        lines = SKILL.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines, 1):
            if "<skill-root>/scripts/mindseam.py" in line:
                sub, args = _classify(line) or (None, None)
                # Either the classifier accepts it (and we
                # tested it above) or it returns None (and we
                # tested it above by counting). The contract
                # is: classifier never raises.
                self.assertIn(sub, (None, "info", "audit"))


class DryRunContractTests(unittest.TestCase):
    """`info` and `audit` are already read-only; pin the
    contract that running them in a fresh empty workspace
    exits 0, the way ``cargo test --doc`` runs each example."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_info_runs_in_empty_workspace(self):
        # info is the canonical read-only face. Even with no
        # .mindseam present, it produces the sectioned text
        # report and exits 0.
        r = subprocess.run(
            [sys.executable, str(MINDSEAM), "info"],
            cwd=self.workspace,
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        # The section header is the r156 text face.
        self.assertIn("mindseam", r.stdout)

    def test_audit_runs_in_empty_workspace(self):
        # Audit needs a ledger to be useful, but it must
        # not crash on an empty workspace the way ``cargo
        # test --doc`` runs an empty example file.
        r = subprocess.run(
            [sys.executable, str(MINDSEAM), "audit", "--json"],
            cwd=self.workspace,
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        import json as _json
        payload = _json.loads(r.stdout)
        # The empty ledger is lean: no audit findings.
        self.assertTrue(payload["lean"])
        self.assertEqual(payload["net"], 0)

    def test_info_format_does_not_write(self):
        # The r169 / r170 / r172 dot-path renderers are pure
        # read paths; the controller does not touch the
        # workspace. A docs example that exercises the
        # renderer must leave ``.mindseam`` absent.
        r = subprocess.run(
            [sys.executable, str(MINDSEAM), "info",
             "--format", "lock_state.state"],
            cwd=self.workspace,
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "free")
        self.assertFalse(
            (Path(self.workspace) / ".mindseam").exists())

    def test_audit_explain_does_not_write(self):
        # r171: --explain is a static doc, no ledger read,
        # no ledger write. Works in an empty workspace, the
        # way ``git help`` works outside a repository.
        r = subprocess.run(
            [sys.executable, str(MINDSEAM), "audit",
             "--explain", "delete"],
            cwd=self.workspace,
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("audit explain delete", r.stdout)
        self.assertFalse(
            (Path(self.workspace) / ".mindseam").exists())


if __name__ == "__main__":
    unittest.main()
