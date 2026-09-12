# -*- coding: utf-8 -*-
"""Round 203 guards: seam --from-stdin --dry-run speaks in the conditional.

The r183 dry-run contract is "write nothing": the history append
loop is gated on ``not dry_run``. The JSON face honoured that with
its ``dry-run: history.json was not updated`` warning — and then
lied next to it: ``from-stdin: 2 next actions recorded``. A host
reading only the warnings list got both statements, and the one
about the write claimed the opposite of the marker. The message
warning above it already carried the ``not dry_run`` gate; the
from-stdin branch simply forgot it existed.

r203 keeps the count (a preview's row count is real information —
the test docstring that pinned the old wording said as much: "the
row count is in the from-stdin warning") and fixes the tense:
``N next actions would be recorded`` under ``--dry-run``,
``N next actions recorded`` (byte-identical, incl. the 0-line
case) otherwise.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from _controller_helper import invoke_cli

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _invoke(args, cwd, stdin=None):
    return invoke_cli(cwd, args, stdin=stdin)


class SeamFromStdinDryRunTenseTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        rows = [{"t": i + 1, "next": "dom: step %d" % i,
                 "verified": i + 1, "open": 0} for i in range(3)]
        (self.ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _warnings(self, args, stdin=None):
        r = _invoke(args, self.workspace, stdin=stdin)
        self.assertEqual(r.returncode, 0, r.stderr)
        return " ".join(json.loads(r.stdout).get("warnings", []))

    def _rows(self):
        return json.loads(
            (self.ledger / "history.json").read_text(encoding="utf-8"))

    def test_dry_run_uses_conditional_tense(self):
        joined = self._warnings(["seam", "--from-stdin", "--dry-run",
                                 "--json"], stdin="a\nb\nc\n")
        self.assertIn("from-stdin: 3 next actions would be recorded",
                      joined)
        self.assertNotIn("3 next actions recorded", joined)

    def test_dry_run_markers_agree(self):
        # The whole point: one payload, one tense. A host that
        # parses the warnings list must not find a completed write
        # and a denied write side by side.
        joined = self._warnings(["seam", "--from-stdin", "--dry-run",
                                 "--json"], stdin="a\nb\n")
        self.assertIn("dry-run: history.json was not updated", joined)
        self.assertIn("would be recorded", joined)

    def test_dry_run_zero_line_conditional(self):
        joined = self._warnings(["seam", "--from-stdin", "--dry-run",
                                 "--json"], stdin="")
        self.assertIn("from-stdin: 0 next actions would be recorded",
                      joined)

    def test_dry_run_writes_nothing(self):
        before = self._rows()
        self._warnings(["seam", "--from-stdin", "--dry-run", "--json"],
                       stdin="a\nb\nc\n")
        self.assertEqual(self._rows(), before)

    def test_real_run_keeps_past_tense(self):
        # The non-dry wording is byte-identical to the pre-r203
        # contract — the pins that asserted it outside a preview
        # stay true. (The append itself is pinned by
        # test_seam_from_stdin_baseline; only the tense matters
        # here, and compaction could trim the ancient seed rows.)
        joined = self._warnings(["seam", "--from-stdin", "--json"],
                                stdin="a\nb\nc\n")
        self.assertIn("from-stdin: 3 next actions recorded", joined)
        self.assertNotIn("would be", joined)

    def test_real_run_zero_line_keeps_past_tense(self):
        joined = self._warnings(["seam", "--from-stdin", "--json"],
                                stdin="")
        self.assertIn("from-stdin: 0 next actions recorded", joined)
        self.assertNotIn("would be", joined)

    def test_no_stdin_flag_no_warning(self):
        joined = self._warnings(["seam", "--dry-run", "--json"])
        self.assertNotIn("from-stdin", joined)

    def test_format_face_carries_the_same_payload(self):
        # The warnings feed the shared payload; --format renders
        # from it, so the tense is consistent across machine faces.
        r = _invoke(["seam", "--from-stdin", "--dry-run", "--json",
                     "--format", "warnings"], self.workspace,
                    stdin="a\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("would be recorded", r.stdout)

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("seam-from-stdin-dry-run-tense", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "seam-from-stdin-dry-run-tense")
        self.assertEqual(entry["since"], "r203")
        self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
