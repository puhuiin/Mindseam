# -*- coding: utf-8 -*-
"""Round 209 guards: verify_suite's exit code mirrors its FAIL counter.

The r208 round landed a commit while the doc-drift gate was red,
and the post-mortem FIRST blamed verify_suite ("prints 1 failed,
exits 0"). That was wrong: verify_suite has always ended with
``sys.exit(1 if FAIL else 0)``. The real culprit was the shell
pipeline the round used -- ``python verify_suite.py | tail -2 &&
git commit`` -- where bash's && sees TAIL's exit code, not the
python process's. The tool was correct; the plumbing around it
was not.

r209 pins the exit contract end to end so the tool itself can
never regress silently: a clean repo exits 0 (tail line
"N passed, 0 failed"), and a repo whose gates fail exits 1 (the
empty-shell scenario: layout, interface, and integrity checks
fail against a stub mindseam.py). The failure-path repo also
proves the counter is what drives the code -- 3 passed, 7
failed, exit 1. The pipeline lesson lives in SESSION_LOG; this
file pins the tool half of it.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "mindseam" / "scripts" / "verify_suite.py"


class VerifySuiteExitContractTests(unittest.TestCase):

    def test_clean_repo_exits_zero(self):
        r = subprocess.run(
            [sys.executable, str(VERIFY), "--skip-unittest"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", cwd=str(ROOT), timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout[-800:])
        self.assertIn("0 failed", r.stdout.strip().splitlines()[-1])

    def test_failing_gates_exit_one(self):
        # A stub repo: layout exists, so find_repo anchors there,
        # but the empty mindseam.py fails the interface/integrity
        # gates. Exit must be 1 -- and the tail line must carry
        # the failed count that drove it.
        tmp = Path(tempfile.mkdtemp())
        try:
            repo = tmp / "repo"
            (repo / "mindseam" / "scripts").mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "SKILL.md").write_text(
                "---\nname: x\ndescription: x\n---\n\n# X\n",
                encoding="utf-8")
            (repo / "mindseam" / "scripts" / "mindseam.py").write_text(
                "# empty shell\n", encoding="utf-8")
            shutil.copy(str(VERIFY),
                        str(repo / "mindseam" / "scripts" / "verify_suite.py"))
            r = subprocess.run(
                [sys.executable,
                 str(repo / "mindseam" / "scripts" / "verify_suite.py")],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=300)
            self.assertEqual(r.returncode, 1, r.stdout[-800:])
            tail = r.stdout.strip().splitlines()[-1]
            self.assertIn("failed", tail)
            self.assertNotIn("0 failed", tail)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
