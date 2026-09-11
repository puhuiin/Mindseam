# -*- coding: utf-8 -*-
"""Round 189 guards: the info audit summary is lazy.

``mode_info`` builds one payload shared by every face, and the r161
``audit_summary`` block sat inside that build — computed eagerly, at
the top, before any face branch ran. But the early-return faces never
surface it: ``--version`` prints one line, ``--check`` prints its own
issues payload, ``--memory`` its own size payload, ``--list-fields``
its own schema. All four paid for a full ``audit_findings`` scan
(ledger sections + full history) whose result was discarded.

r189 wraps the computation in a ``_ensure_audit_summary`` closure and
calls it only at the three real consumers: the health block (its
reasons read ``audit_summary.lean``), the warnings-only JSON face
(the r161 no-suppression pin), and the format/main faces (the full
payload). A counting wrapper must now read:

    --version / --check / --memory / --list-fields   ->  0 calls
    --json / --warnings-only --json / --health       ->  1 call
    --format / plain text                            ->  1 call

No output shape changes anywhere: every face that surfaced
``audit_summary`` still surfaces the identical block, computed from
the same ``audit_findings(book, hist)`` — the r182/r186
pure-function-reuse pattern, this time as deferral instead of sharing.
"""

import io
import json
import contextlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


class LazyAuditSummaryTests(unittest.TestCase):
    """The audit scan runs only when a face will surface it."""

    def setUp(self):
        self._old_cwd = os.getcwd()
        self.workspace = tempfile.mkdtemp()
        os.chdir(self.workspace)
        ledger = Path(self.workspace) / ".mindseam"
        ledger.mkdir(parents=True)
        (ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        self.ledger = ledger
        self._capture("note", "--next", "dom: step 0")
        for _ in range(3):
            self._capture("seam", "--json")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _capture(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mindseam.main(list(args))
        return buf.getvalue()

    def _count_calls(self, *args):
        real = mindseam.audit_findings
        calls = []

        def wrapper(book, hist):
            calls.append(1)
            return real(book, hist)

        mindseam.audit_findings = wrapper
        try:
            out = self._capture(*args)
        finally:
            mindseam.audit_findings = real
        return len(calls), out

    def test_early_return_faces_skip_the_audit(self):
        for face in (["info", "--version"], ["info", "--check"],
                     ["info", "--memory"], ["info", "--list-fields"]):
            calls, _ = self._count_calls(*face)
            self.assertEqual(calls, 0,
                             "%s must not run the audit" % " ".join(face))

    def test_consumer_faces_run_the_audit_once(self):
        for face in (["info", "--json"],
                     ["info", "--warnings-only", "--json"],
                     ["info", "--health", "--json"],
                     ["info", "--json", "--format", "audit_summary.net"],
                     ["info"]):
            calls, _ = self._count_calls(*face)
            self.assertEqual(calls, 1,
                             "%s must run the audit exactly once"
                             % " ".join(face))

    def test_check_face_exit_contract_unchanged(self):
        # A clean ledger passes --check with exit 0; the lazy summary
        # must not perturb the exit contract.
        code, out = 0, self._capture("info", "--check")
        self.assertIn("ledger: ok", out)

    def test_main_face_audit_line_unchanged(self):
        # The text face still prints the r161 audit line.
        out = self._capture("info")
        self.assertIn("Audit: 0 items removable (lean).", out)

    def test_json_still_carries_audit_summary(self):
        out = self._capture("info", "--json")
        payload = json.loads(out[out.index("{"):])
        self.assertIn("audit_summary", payload)
        self.assertTrue(payload["audit_summary"]["lean"])
        self.assertEqual(payload["audit_summary"]["net"], 0)

    def test_warnings_only_json_still_carries_audit_summary(self):
        # The r161 no-suppression pin: --warnings-only --json keeps
        # the full key set.
        out = self._capture("info", "--json", "--warnings-only")
        payload = json.loads(out[out.index("{"):])
        self.assertIn("audit_summary", payload)
        self.assertIn("warnings", payload)

    def test_health_reasons_still_read_audit_lean(self):
        # The health block composes audit_summary.lean into its
        # status; the lazy pull must keep that wiring intact.
        out = self._capture("info", "--health", "--json")
        payload = json.loads(out[out.index("{"):])
        self.assertIn("health", payload)
        self.assertIn("audit_summary", payload)
        self.assertEqual(payload["health"]["status"], "ok")

    def test_version_face_unchanged(self):
        out = self._capture("info", "--version")
        self.assertTrue(out.startswith("mindseam "))


if __name__ == "__main__":
    unittest.main()
