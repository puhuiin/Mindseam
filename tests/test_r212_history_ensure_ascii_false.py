# -*- coding: utf-8 -*-
"""Round 212 guards: every history/meta JSON write keeps raw UTF-8.

mode_seam's r210 batch and ``history --keep`` already wrote history
with ``ensure_ascii=False``. Four other writers still used the
default ``True``:

- ``append_history`` (the path resume and every non-batch seam write
  takes)
- ``read_history``'s repair save
- ``compact_history``'s archive and kept slices
- ``write_meta``

A Chinese next-action therefore landed as raw UTF-8 under seam, then
was re-escaped to ``\\uXXXX`` on the next resume — the file's bytes
flipped between writers for the same semantic content, and r184's
identical-write short-circuit never fired for unchanged non-ASCII
rows because the two encodings are different bytes.

r212 unifies every disk write on ``ensure_ascii=False``, the way
skillbook and the audit baseline already did.
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


class EnsureAsciiFalseTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\n中文下一步\n", encoding="utf-8")
        self.history = self.ledger / "history.json"
        self.history.write_text("[]", encoding="utf-8")
        self.meta_path = self.ledger / "metacognition.json"
        self.meta_path.write_text("{}", encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _raw(self):
        return self.history.read_bytes()

    def _has_raw_cjk(self):
        return "中文".encode("utf-8") in self._raw()

    def _has_escaped(self):
        return b"\\u" in self._raw()

    def test_resume_keeps_raw_cjk(self):
        r = invoke_cli(self.workspace, ["resume"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self._has_raw_cjk())
        self.assertFalse(self._has_escaped())

    def test_seam_keeps_raw_cjk(self):
        r = invoke_cli(self.workspace, ["seam", "--quiet"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self._has_raw_cjk())
        self.assertFalse(self._has_escaped())

    def test_resume_after_seam_does_not_reescape(self):
        # The flip-flop: seam wrote raw UTF-8, the next resume used
        # to re-escape the whole file. After r212 both writers agree.
        r = invoke_cli(self.workspace, ["seam", "--quiet"])
        self.assertEqual(r.returncode, 0, r.stderr)
        after_seam = self._raw()
        self.assertTrue(self._has_raw_cjk())
        r = invoke_cli(self.workspace, ["resume"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self._has_raw_cjk())
        self.assertFalse(self._has_escaped())
        # The resume append adds one row; the pre-existing rows must
        # still be raw, not silently rewritten as escapes.
        rows = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(rows), 2)
        self.assertIn("中文", rows[0]["next"])

    def test_from_stdin_then_resume_stays_raw(self):
        r = invoke_cli(self.workspace,
                       ["seam", "--from-stdin", "--quiet"],
                       stdin="中文任务\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self._has_raw_cjk())
        r = invoke_cli(self.workspace, ["resume"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self._has_escaped())
        rows = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertTrue(any("中文" in (row.get("next") or "")
                            for row in rows))

    def test_write_meta_keeps_raw_cjk_verifier(self):
        r = invoke_cli(
            self.workspace,
            ["note", "--verifier", "中文验证器退出零"])
        self.assertEqual(r.returncode, 0, r.stderr)
        raw = self.meta_path.read_bytes()
        self.assertIn("中文".encode("utf-8"), raw)
        self.assertNotIn(b"\\u", raw)

    def test_repair_save_keeps_raw_cjk(self):
        # Hostile next (non-string) is repaired to ""; a CJK neighbour
        # must survive the repair write as raw UTF-8, not escapes.
        dirty = [{
            "t": 1, "next": 123, "verified": 0, "open": 0,
            "marker": "", "confidence": "", "verifier": "",
            "risk": "", "error": "", "outcome": "", "extra_steps": 0,
        }, {
            "t": 2, "next": "中文保留", "verified": 0, "open": 0,
            "marker": "", "confidence": "", "verifier": "",
            "risk": "", "error": "", "outcome": "", "extra_steps": 0,
        }]
        self.history.write_text(json.dumps(dirty, ensure_ascii=True),
                                encoding="utf-8")
        r = invoke_cli(self.workspace, ["info", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertEqual(rows[0]["next"], "")
        self.assertEqual(rows[1]["next"], "中文保留")
        self.assertTrue(self._has_raw_cjk())
        self.assertFalse(self._has_escaped())

    def test_identical_cjk_write_is_still_idempotent(self):
        # r184 short-circuit must fire for raw CJK: two resumes that
        # produce the same bytes must not bump mtime. (The second
        # resume appends a new row, so use two info reads of an
        # already-written file via atomic_write_text directly.)
        path = self.ledger / "probe.json"
        text = json.dumps({"next": "中文"}, ensure_ascii=False)
        self.assertIsNone(mindseam.atomic_write_text(str(path), text))
        mtime = path.stat().st_mtime_ns
        self.assertIsNone(mindseam.atomic_write_text(str(path), text))
        self.assertEqual(path.stat().st_mtime_ns, mtime)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-ensure-ascii-false", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-ensure-ascii-false")
        self.assertEqual(entry["since"], "r212")
        self.assertIn("ensure_ascii=False", entry["summary"])


if __name__ == "__main__":
    unittest.main()
