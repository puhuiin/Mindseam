# -*- coding: utf-8 -*-
"""Round 214 guards: history --keep tells the truth about rotation.

Two defects on the destructive rotation path.

1. **Failed write still presented a truncated view.** The old code
   warned "could not rotate history.json" and then did
   ``hist = truncated`` anyway, so ``history --keep 3 --count``
   printed 3 while the file still held 10 rows. A host that trusted
   the count would see the un-rotated history on the next read —
   the keep path's entire purpose is persistence, so a failed
   write must not fake the result.

2. **Negative --keep was a silent no-op.** The ``keep_n >= 0``
   guard skipped the rotation without a word; ``history --keep -1``
   exited 0 on an unrotated file. Every other negative-count flag
   (audit --since, note --extra-steps) refuses with exit 2.

Probe (before the fix): failing atomic_write_text on
``history --keep 3 --count`` printed ``3`` on stdout, empty of any
row-count contradiction, while disk still held 10 rows.
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


class HistoryKeepWriteHonestyTests(unittest.TestCase):

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
        } for i in range(1, 11)]
        self.history.write_text(json.dumps(rows), encoding="utf-8")
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

    def test_failed_keep_reports_full_count_not_truncated(self):
        self._fail_history_writes()
        r = invoke_cli(self.workspace, ["history", "--keep", "3", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        # Disk still has 10 rows; the count must not claim 3.
        self.assertEqual(r.stdout.strip(), "10")
        self.assertIn("could not rotate", r.stderr)
        self.assertIn("unchanged", r.stderr)
        self.assertEqual(len(json.loads(self.history.read_text(
            encoding="utf-8"))), 10)

    def test_failed_keep_json_carries_full_rows(self):
        self._fail_history_writes()
        r = invoke_cli(self.workspace, ["history", "--keep", "3", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 10)

    def test_successful_keep_still_truncates(self):
        r = invoke_cli(self.workspace, ["history", "--keep", "3", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "3")
        self.assertEqual(len(json.loads(self.history.read_text(
            encoding="utf-8"))), 3)

    def test_negative_keep_refused_before_any_write(self):
        before = self.history.read_bytes()
        r = invoke_cli(self.workspace, ["history", "--keep", "-1", "--count"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--keep", r.stderr)
        self.assertIn("non-negative", r.stderr)
        self.assertEqual(self.history.read_bytes(), before)

    def test_zero_keep_still_empties(self):
        r = invoke_cli(self.workspace, ["history", "--keep", "0", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "0")
        self.assertEqual(json.loads(self.history.read_text(
            encoding="utf-8")), [])


class HistoryKeepCatalogTests(unittest.TestCase):

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-keep-write-honesty", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-keep-write-honesty")
        self.assertEqual(entry["since"], "r214")
        self.assertIn("truncated", entry["summary"])
        self.assertIn("negative", entry["summary"])


if __name__ == "__main__":
    unittest.main()
