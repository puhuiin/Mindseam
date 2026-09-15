# -*- coding: utf-8 -*-
"""Round 213 guards: note writes meta only when telemetry changed,
and write failures are no longer silent.

Two defects, one acknowledgement theme.

1. ``mode_note`` gated the meta write on ``if meta`` — truthy as soon
   as any prior telemetry existed. Every ``note --next`` therefore
   opened ``metacognition.json``, took the write lock, and compared
   bytes even though no telemetry flag was on the command line. r184
   made the rewrite a no-op; the lock churn remained. A ledger-only
   note should touch WORKSPACE.md alone.

2. ``write_meta``'s return value was discarded in both ``mode_note``
   and ``mode_seam``, and ``write_skillbook`` discarded
   ``atomic_write_text``'s problem after the ``ensure_dir`` check. A
   held lock or a full disk left the host believing --marker landed
   when it did not — the opposite of the history-write WARNING
   family that has spoken up since the early rounds.

Also: ``note --dry-run`` with only a telemetry flag used to print
"No changes would be applied" even though the meta write would have
landed. The plan now names ``~ meta``.
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


class NoteMetaDirtyTests(unittest.TestCase):

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
        # Pre-existing telemetry so the old ``if meta`` gate was truthy.
        self.meta_path.write_text(
            json.dumps({"marker": "OPEN", "confidence": "strong"}),
            encoding="utf-8")
        self.counts = {"write_meta": 0, "write_ledger": 0}
        self._orig_meta = mindseam.write_meta
        self._orig_ledger = mindseam.write_ledger

        def counting_meta(meta):
            self.counts["write_meta"] += 1
            return self._orig_meta(meta)

        def counting_ledger(book):
            self.counts["write_ledger"] += 1
            return self._orig_ledger(book)

        mindseam.write_meta = counting_meta
        mindseam.write_ledger = counting_ledger

    def tearDown(self):
        mindseam.write_meta = self._orig_meta
        mindseam.write_ledger = self._orig_ledger
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _snap(self):
        before = dict(self.counts)
        return before

    def test_next_only_does_not_write_meta(self):
        before = self._snap()
        r = invoke_cli(self.workspace, ["note", "--next", "step-a"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.counts["write_meta"] - before["write_meta"], 0)
        self.assertEqual(self.counts["write_ledger"] - before["write_ledger"], 1)

    def test_marker_writes_meta_not_ledger(self):
        before = self._snap()
        r = invoke_cli(self.workspace, ["note", "--marker", "DONE"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.counts["write_meta"] - before["write_meta"], 1)
        self.assertEqual(self.counts["write_ledger"] - before["write_ledger"], 0)
        meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self.assertEqual(meta["marker"], "DONE")

    def test_mixed_call_writes_both(self):
        before = self._snap()
        r = invoke_cli(self.workspace,
                       ["note", "--next", "step-b", "--confidence", "thin"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.counts["write_meta"] - before["write_meta"], 1)
        self.assertEqual(self.counts["write_ledger"] - before["write_ledger"], 1)

    def test_invalid_marker_does_not_write_meta(self):
        before = self._snap()
        r = invoke_cli(self.workspace, ["note", "--marker", "   "])
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.counts["write_meta"] - before["write_meta"], 0)


class WriteMetaFailureWarnsTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        (self.ledger / "history.json").write_text("[]", encoding="utf-8")
        self._orig_meta = mindseam.write_meta
        self._orig_skill = mindseam.write_skillbook

    def tearDown(self):
        mindseam.write_meta = self._orig_meta
        mindseam.write_skillbook = self._orig_skill
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_note_warns_when_write_meta_fails(self):
        mindseam.write_meta = lambda meta: "disk full"
        r = invoke_cli(self.workspace, ["note", "--marker", "PHEW"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("telemetry was not saved", r.stderr)
        self.assertIn("disk full", r.stderr)

    def test_seam_warns_when_write_meta_fails(self):
        mindseam.write_meta = lambda meta: "locked"
        r = invoke_cli(self.workspace, ["seam", "--quiet"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("telemetry was not saved", r.stderr)
        self.assertIn("locked", r.stderr)

    def test_write_skillbook_returns_and_warns_on_write_failure(self):
        original = mindseam.atomic_write_text

        def failing(path, text):
            if str(path).endswith("skillbook.md"):
                return "held by another writer"
            return original(path, text)

        mindseam.atomic_write_text = failing
        try:
            problem = mindseam.write_skillbook([])
        finally:
            mindseam.atomic_write_text = original
        self.assertEqual(problem, "held by another writer")

    def test_note_dry_run_names_meta_on_telemetry_only(self):
        r = invoke_cli(self.workspace, ["note", "--marker", "OPEN",
                                        "--dry-run"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("~ meta", r.stdout)
        self.assertNotIn("No changes would be applied", r.stdout)

    def test_note_dry_run_no_edits_says_no_changes(self):
        # Goal/Next already exist; a bare note touches neither ledger
        # nor telemetry, so the terraform-plan "No changes" face runs.
        r = invoke_cli(self.workspace, ["note", "--dry-run"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("No changes would be applied", r.stdout)


class NoteMetaCatalogTests(unittest.TestCase):

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("note-meta-dirty-and-warn", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "note-meta-dirty-and-warn")
        self.assertEqual(entry["since"], "r213")
        self.assertIn("meta_dirty", entry["summary"])
        self.assertIn("telemetry was not saved", entry["summary"])


if __name__ == "__main__":
    unittest.main()
