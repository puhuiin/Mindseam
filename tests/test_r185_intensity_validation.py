# -*- coding: utf-8 -*-
"""Round 185 guards: the intensity ladder is validated.

``resolve_intensity`` resolves the verbosity ladder as
flag > MINDSEAM_INTENSITY > full, but until r185 nothing validated the
resolved value: ``mode_audit`` only checked for the literal ``off``,
so a typo — ``--intensity banana`` or ``MINDSEAM_INTENSITY=banana`` —
fell through and the audit ran at full verbosity. A host that meant
``off`` (a CI gate refusing to run the audit) got the opposite: a
silent full run. The ``INTENSITY_LEVELS`` constant existed since r156
but had never been wired to anything — a dead constant that
documented the exact contract nobody enforced.

r185 refuses an unrecognised level with exit 2 to stderr and lists
the valid ladder, the way ``--tag unknown`` refuses. ``off`` keeps
its dedicated refusal (exit 2 to stdout, "audit intensity is off")
because its message names the fix, and ``lite`` / ``full`` behave
exactly as r156 pinned them.

The r156 resolution order (flag beats environment) is unchanged —
validation happens on the *resolved* value, after the precedence
rules have spoken.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _run(args, cwd, env_extra=None):
    run_env = os.environ.copy()
    run_env.pop("MINDSEAM_INTENSITY", None)
    if env_extra:
        run_env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(MINDSEAM), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        env=run_env,
    )


class IntensityValidationTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_unknown_flag_value_refused_with_exit_2(self):
        r = _run(["audit", "--intensity", "banana"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a recognised level", r.stderr)
        self.assertIn("off, lite, full", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_unknown_env_value_refused_with_exit_2(self):
        r = _run(["audit"], self.workspace,
                 env_extra={"MINDSEAM_INTENSITY": "banana"})
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a recognised level", r.stderr)

    def test_typo_close_to_off_is_refused_not_silently_full(self):
        # The motivating case: "of" is not "off". Before r185 this
        # fell through the off check and ran the audit at full
        # verbosity with exit 0.
        r = _run(["audit", "--intensity", "of"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a recognised level", r.stderr)

    def test_off_keeps_its_dedicated_refusal(self):
        # The off refusal prints to stdout (a ponytail-ism) and names
        # the fix; validation must not swallow it.
        r = _run(["audit", "--intensity", "off"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("audit intensity is off", r.stdout)

    def test_valid_levels_unchanged(self):
        for value, code in (("lite", 0), ("full", 0)):
            r = _run(["audit", "--intensity", value], self.workspace)
            self.assertEqual(r.returncode, code, r.stderr)
        # Case-insensitive as before (resolve_intensity lowercases).
        r = _run(["audit", "--intensity", "LITE"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Lean already. Ship.", r.stdout)

    def test_flag_beats_environment_even_when_env_is_invalid(self):
        # The r156 precedence is untouched: a valid flag wins over an
        # invalid environment value because the invalid value never
        # reaches the caller — the flag resolved first.
        r = _run(["audit", "--intensity", "full"], self.workspace,
                 env_extra={"MINDSEAM_INTENSITY": "banana"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Lean already. Ship.", r.stdout)

    def test_intensity_levels_constant_is_the_validator(self):
        # The dead constant is now load-bearing: the valid levels the
        # refusal lists are exactly INTENSITY_LEVELS, so a future
        # ladder change updates one tuple and the refusal follows.
        self.assertEqual(mindseam.INTENSITY_LEVELS,
                         ("off", "lite", "full"))
        r = _run(["audit", "--intensity", "zzz"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn(", ".join(mindseam.INTENSITY_LEVELS), r.stderr)


if __name__ == "__main__":
    unittest.main()
