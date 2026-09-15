# -*- coding: utf-8 -*-
"""Round 218 guards: a failed history write reports disk truth.

r214 closed the keep-path lie (failed rotation still presented a
truncated view). The append path had the same class of bug:
``append_history`` warned "recent seam history was not saved" and
then returned the in-memory hist *with* the unsaved row, so
``resume --json`` claimed ``history_count: 4`` while the file still
held 3 (probe). ``mode_seam``'s batch write had the same shape —
rows_written counted lines that never landed.

r218 makes ``append_history`` return
``(hist, compact_reasons, write_problem)``; on a failed write it
re-reads history from disk so the caller's report matches what
actually landed. ``mode_seam`` does the same after its own batch
write and zeroes ``rows_written``.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from _controller_helper import invoke_cli

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


class AppendWriteFailureDiskTruthTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        self.history = self.ledger / "history.json"
        rows = [{
            "t": i, "next": "a: x%d" % i, "verified": i, "open": 0,
            "marker": "DONE", "confidence": "strong",
            "verifier": "pytest", "risk": "low",
            "error": "", "outcome": "ok", "extra_steps": 0,
        } for i in range(1, 4)]
        self.history.write_text(json.dumps(rows), encoding="utf-8")
        (self.ledger / "metacognition.json").write_text("{}", encoding="utf-8")
        (self.ledger / "skillbook.md").write_text("[]", encoding="utf-8")
        self._orig = mindseam.atomic_write_text

    def tearDown(self):
        mindseam.atomic_write_text = self._orig
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _fail_history_writes(self):
        orig = self._orig

        def failing(path, text):
            if str(path).endswith("history.json"):
                return "disk full"
            return orig(path, text)

        mindseam.atomic_write_text = failing

    def _disk_len(self):
        return len(json.loads(self.history.read_text(encoding="utf-8")))

    def test_append_history_returns_write_problem_and_disk_hist(self):
        self._fail_history_writes()
        book = {"Next": ["z: x"], "Verified": [], "Open": [],
                "Core": [], "Goal": ["g"]}
        hist, _, problem = mindseam.append_history(book, hist=None, write=True)
        self.assertEqual(problem, "disk full")
        self.assertEqual(len(hist), 3)
        self.assertEqual(len(hist), self._disk_len())

    def test_resume_json_history_count_matches_disk(self):
        self._fail_history_writes()
        r = invoke_cli(self.workspace, ["resume", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("not saved", r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 3)
        self.assertEqual(payload["history_count"], self._disk_len())

    def test_seam_json_history_count_matches_disk_on_write_failure(self):
        self._fail_history_writes()
        r = invoke_cli(self.workspace, ["seam", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("not write seam history", r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 3)
        self.assertEqual(payload["history_count"], self._disk_len())

    def test_seam_from_stdin_write_failure_drops_unsaved_rows(self):
        self._fail_history_writes()
        r = invoke_cli(self.workspace, ["seam", "--from-stdin", "--json"],
                       stdin="line-a\nline-b\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 3)
        self.assertEqual(self._disk_len(), 3)

    def test_successful_append_still_reports_new_count(self):
        r = invoke_cli(self.workspace, ["resume", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 4)
        self.assertEqual(self._disk_len(), 4)

    def test_write_false_returns_none_problem(self):
        book = {"Next": ["z: x"], "Verified": [], "Open": [],
                "Core": [], "Goal": ["g"]}
        hist, _, problem = mindseam.append_history(
            book, hist=None, write=False)
        self.assertIsNone(problem)
        self.assertEqual(len(hist), 4)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("append-write-failure-disk-truth", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "append-write-failure-disk-truth")
        self.assertEqual(entry["since"], "r218")
        self.assertIn("write_problem", entry["summary"])
        self.assertIn("history_count", entry["summary"])


if __name__ == "__main__":
    unittest.main()
