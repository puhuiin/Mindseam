# -*- coding: utf-8 -*-
"""Round 219 guards: seam only consumes event keys when history lands.

``METACOGNITION_EVENT_KEYS`` (error / outcome / extra_steps) are
one-shot: ``note`` writes them into metacognition.json, the next
seam copies them into the history row, then clears them.

When the seam's history write failed, r218 re-read disk so the
report matched — but the event keys were still popped and written
back. The rows that would have carried the events never landed,
and the events themselves were gone from meta, so the next seam
could not consume them either. One-shot events were lost twice.

r219 gates the clear on ``history_write_ok``: a failed history
write leaves the events in meta for the next successful seam.
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


class SeamEventKeysHistoryWriteTests(unittest.TestCase):

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
        self.history.write_text("[]", encoding="utf-8")
        self.meta_path = self.ledger / "metacognition.json"
        self.meta_path.write_text(
            json.dumps({"error": "db: timeout", "outcome": "failed: retry"}),
            encoding="utf-8")
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

    def _meta(self):
        return json.loads(self.meta_path.read_text(encoding="utf-8"))

    def test_failed_history_write_keeps_event_keys(self):
        self._fail_history_writes()
        r = invoke_cli(self.workspace, ["seam", "--quiet"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("not write seam history", r.stderr)
        meta = self._meta()
        self.assertEqual(meta.get("error"), "db: timeout")
        self.assertEqual(meta.get("outcome"), "failed: retry")

    def test_successful_history_write_clears_event_keys(self):
        r = invoke_cli(self.workspace, ["seam", "--quiet"])
        self.assertEqual(r.returncode, 0, r.stderr)
        meta = self._meta()
        self.assertNotIn("error", meta)
        self.assertNotIn("outcome", meta)
        rows = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("error"), "db: timeout")
        self.assertEqual(rows[0].get("outcome"), "failed: retry")

    def test_events_survive_failed_then_succeed_on_retry(self):
        self._fail_history_writes()
        r = invoke_cli(self.workspace, ["seam", "--quiet"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self._meta().get("error"), "db: timeout")

        mindseam.atomic_write_text = self._orig
        r = invoke_cli(self.workspace, ["seam", "--quiet"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("error", self._meta())
        rows = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertTrue(any(row.get("error") == "db: timeout"
                            for row in rows), rows)

    def test_dry_run_does_not_write_meta_or_clear_events(self):
        r = invoke_cli(self.workspace, ["seam", "--dry-run", "--quiet"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self._meta().get("error"), "db: timeout")
        self.assertEqual(json.loads(self.history.read_text(
            encoding="utf-8")), [])

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("seam-event-keys-need-history-write", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "seam-event-keys-need-history-write")
        self.assertEqual(entry["since"], "r219")
        self.assertIn("error", entry["summary"])
        self.assertIn("history", entry["summary"])


if __name__ == "__main__":
    unittest.main()
