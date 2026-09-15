# -*- coding: utf-8 -*-
"""Round 215 guards: compact archive rollback and note write order.

Two defects on the multi-write paths.

1. **compact_history left a half-done archive on kept-write failure.**
   The function writes the archive first, then the kept HISTORY
   slice. When the kept write failed (disk full, lock), the archive
   already held the slice while HISTORY stayed full — so the next
   compaction re-sent the same rows and duplicated them. r215 rolls
   the archive back to its previous content when the kept write
   fails, so the archive only records rows that actually left
   HISTORY. (Suffix-equality skip was rejected: r56's second
   compaction legitimately re-archives a row still present in a
   different history.)

2. **mode_note wrote telemetry before the ledger.** A mixed
   ``note --next X --marker DONE`` landed --marker first; if the
   ledger write then failed, telemetry said DONE while Next never
   moved. r215 writes the ledger first: a ledger failure skips meta
   entirely (and says so), and a meta failure after a successful
   ledger write is a WARNING on an already-true ledger.
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


def _row(i, nxt=None):
    return {
        "t": i, "next": nxt or ("a: x%d" % i), "verified": i, "open": 0,
        "marker": "DONE", "confidence": "strong", "verifier": "pytest",
        "risk": "low", "error": "", "outcome": "ok", "extra_steps": 0,
    }


class CompactArchiveRetryTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        self.history = self.ledger / "history.json"
        self.archive = self.ledger / "history.archive.json"
        self._orig = mindseam.atomic_write_text
        self._max = mindseam.HISTORY_MAX

    def tearDown(self):
        mindseam.atomic_write_text = self._orig
        mindseam.HISTORY_MAX = self._max
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _write_hist(self, n):
        self.history.write_text(
            json.dumps([_row(i) for i in range(1, n + 1)]),
            encoding="utf-8")

    def _archive_rows(self):
        if not self.archive.exists():
            return []
        return json.loads(self.archive.read_text(encoding="utf-8"))

    def _book(self, nxt):
        return {"Next": [nxt], "Verified": [], "Open": [],
                "Core": [], "Goal": ["g"]}

    def test_archive_rolled_back_when_kept_write_fails(self):
        mindseam.HISTORY_MAX = 2
        self._write_hist(5)
        orig = self._orig
        state = {"fail_kept": True}

        def flaky(path, text):
            name = os.path.basename(str(path))
            if name == "history.json" and state["fail_kept"]:
                state["fail_kept"] = False
                return "disk full"
            return orig(path, text)

        book = self._book("z: after")
        mindseam.atomic_write_text = flaky
        try:
            hist, _, _ = mindseam.read_history()
            hist, reasons, _ = mindseam.append_history(
                book, hist=hist, write=True)
            self.assertEqual(self._archive_rows(), [],
                             "archive was not rolled back")
            self.assertTrue(any("rolled back" in r for r in reasons), reasons)
            # compact returned the full hist, so the caller's write
            # landed 5 original + 1 append, not the kept slice.
            self.assertEqual(len(json.loads(self.history.read_text(
                encoding="utf-8"))), 6)
        finally:
            mindseam.atomic_write_text = orig

    def test_retry_after_rollback_archives_once(self):
        mindseam.HISTORY_MAX = 2
        self._write_hist(5)
        orig = self._orig
        state = {"fail_kept": True}

        def flaky(path, text):
            name = os.path.basename(str(path))
            if name == "history.json" and state["fail_kept"]:
                state["fail_kept"] = False
                return "disk full"
            return orig(path, text)

        mindseam.atomic_write_text = flaky
        try:
            hist, _, _ = mindseam.read_history()
            mindseam.append_history(self._book("z: a"), hist=hist, write=True)
        finally:
            mindseam.atomic_write_text = orig

        hist, _, _ = mindseam.read_history()
        hist, reasons, _ = mindseam.append_history(
            self._book("z: b"), hist=hist, write=True)
        # 6 on disk + 1 append = 7; keep 2, archive 5.
        self.assertEqual(len(self._archive_rows()), 5)
        on_disk = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertEqual(len(on_disk), 2)

    def test_successful_compact_still_archives_once(self):
        mindseam.HISTORY_MAX = 2
        self._write_hist(5)
        hist, _, _ = mindseam.read_history()
        hist, reasons, _ = mindseam.append_history(
            self._book("z: after"), hist=hist, write=True)
        # 5 + 1 append = 6; keep 2, archive 4.
        self.assertEqual(len(self._archive_rows()), 4)
        on_disk = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertEqual(len(on_disk), 2)


class NoteLedgerBeforeMetaTests(unittest.TestCase):

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
        self.meta_path = self.ledger / "metacognition.json"
        self.meta_path.write_text("{}", encoding="utf-8")
        self.order = []
        self._orig_ledger = mindseam.write_ledger
        self._orig_meta = mindseam.write_meta

        def tracking_ledger(book):
            self.order.append("ledger")
            return self._orig_ledger(book)

        def tracking_meta(meta):
            self.order.append("meta")
            return self._orig_meta(meta)

        mindseam.write_ledger = tracking_ledger
        mindseam.write_meta = tracking_meta

    def tearDown(self):
        mindseam.write_ledger = self._orig_ledger
        mindseam.write_meta = self._orig_meta
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_mixed_note_writes_ledger_then_meta(self):
        r = invoke_cli(self.workspace,
                       ["note", "--next", "step-z", "--marker", "DONE"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.order, ["ledger", "meta"])

    def test_ledger_failure_skips_meta(self):
        mindseam.write_ledger = lambda book: "locked"
        # tracking_meta still records if it runs
        r = invoke_cli(self.workspace,
                       ["note", "--next", "step-z", "--marker", "PHEW"])
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.order, [])
        self.assertIn("cannot write the ledger", r.stderr)
        self.assertIn("telemetry was not written", r.stderr)
        # Meta file untouched
        self.assertEqual(json.loads(self.meta_path.read_text(
            encoding="utf-8")), {})

    def test_meta_failure_after_ledger_ok_warns(self):
        mindseam.write_meta = lambda meta: "disk full"
        r = invoke_cli(self.workspace,
                       ["note", "--next", "step-z", "--marker", "PHEW"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.order, ["ledger"])
        self.assertIn("telemetry was not saved", r.stderr)

    def test_meta_only_still_writes_meta(self):
        r = invoke_cli(self.workspace, ["note", "--marker", "OPEN"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.order, ["meta"])


class CompactNoteOrderCatalogTests(unittest.TestCase):

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("compact-archive-retry-and-note-order", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "compact-archive-retry-and-note-order")
        self.assertEqual(entry["since"], "r215")
        self.assertIn("archive", entry["summary"])
        self.assertIn("ledger", entry["summary"])


if __name__ == "__main__":
    unittest.main()
