# -*- coding: utf-8 -*-
"""Round 189 guards: the integrity verifier has a machine-readable face.

verify_suite.py only ever printed a human line per check and a
"``N passed, M failed``" summary, so a CI job or an editor plugin had to
scrape stdout to learn which check failed. Every other surface in the
suite already answers this way (``info --json``, ``seam --json``,
``audit --json``), and the verifier was the last one that did not.

r189 adds ``--json``: the same checks, emitted as
``{"passed", "failed", "checks": [{"name", "ok"}]}`` on stdout with the
human lines suppressed, so stdout parses cleanly. The default text face
is untouched byte-for-byte, and the exit contract is unchanged --
non-zero only when a check failed.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "mindseam" / "scripts" / "verify_suite.py"


def _invoke(args):
    return subprocess.run(
        [sys.executable, str(VERIFY), *args],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120)


class VerifySuiteJsonFaceTests(unittest.TestCase):

    def test_json_face_parses_and_carries_every_check(self):
        r = _invoke(["--skip-unittest", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["failed"], 0)
        self.assertGreaterEqual(payload["passed"], 1)
        self.assertIsInstance(payload["checks"], list)
        for entry in payload["checks"]:
            self.assertEqual(set(entry), {"name", "ok"})
            self.assertIsInstance(entry["name"], str)
            self.assertIsInstance(entry["ok"], bool)
        self.assertEqual(len(payload["checks"]), payload["passed"])

    def test_json_stdout_carries_nothing_but_the_payload(self):
        # The human PASS/FAIL lines must not leak into the JSON face, or
        # stdout stops being parseable by the host reading it.
        r = _invoke(["--skip-unittest", "--json"])
        self.assertNotIn("PASS ", r.stdout)
        self.assertNotIn("passed, ", r.stdout)

    def test_text_face_is_unchanged(self):
        r = _invoke(["--skip-unittest"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PASS ", r.stdout)
        self.assertIn("passed, 0 failed", r.stdout)
        with self.assertRaises(ValueError):
            json.loads(r.stdout)

    def test_both_faces_agree_on_the_check_count(self):
        text = _invoke(["--skip-unittest"])
        payload = json.loads(_invoke(["--skip-unittest", "--json"]).stdout)
        text_lines = [ln for ln in text.stdout.splitlines()
                      if ln.startswith(("PASS ", "FAIL "))]
        self.assertEqual(len(text_lines), len(payload["checks"]))


if __name__ == "__main__":
    unittest.main()
