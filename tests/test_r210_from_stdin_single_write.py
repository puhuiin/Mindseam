# -*- coding: utf-8 -*-
"""Round 210 guards: seam --from-stdin lands the batch with ONE write.

The r174 batch loop called ``append_history`` per input line — each
call doing its own read+write — and rewrote the file again per line
when ``--message`` was set. A 3-line batch cost up to 6 history
writes, and an interrupted batch left a PARTIAL commit on disk:
rows 1-2 persisted, row 3 lost, the transcript lying about what
was recorded — the opposite of the ``kubectl apply -f -``
transaction the flag borrows from.

r210 gives append_history two injection parameters (``hist=`` to
supply the already-read history, ``write=False`` to keep the row
math — entry, risk, compaction — in memory) and moves the single
persistence call to after the loop. Final on-disk bytes are
identical for any batch: the per-line math runs exactly as before,
only when it lands changed. Standalone callers (resume, plain
``seam``) keep the default read+write path byte for byte.

The write counter here is a monkeypatched ``atomic_write_text``
observing the in-process invoke — the same counting-wrapper
instrument r182/r186 used for IO dedup.
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


class FromStdinSingleWriteTests(unittest.TestCase):

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

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _rows(self):
        return json.loads(self.history.read_text(encoding="utf-8"))

    def _counting(self, args, stdin=None):
        # Wrap the module-level atomic_write_text so every history
        # write is counted; everything else runs the real thing.
        import io
        counts = {"history": 0}
        original = mindseam.atomic_write_text

        def counting(path, text):
            name = os.path.basename(str(path))
            if name == "history.json":
                counts["history"] += 1
            return original(path, text)

        mindseam.atomic_write_text = counting
        try:
            r = invoke_cli(self.workspace, args, stdin=stdin)
        finally:
            mindseam.atomic_write_text = original
        self.assertEqual(r.returncode, 0, r.stderr)
        return counts["history"]

    def test_three_line_batch_writes_history_once(self):
        n = self._counting(["seam", "--from-stdin", "--quiet"],
                           stdin="a\nb\nc\n")
        self.assertEqual(n, 1)
        self.assertEqual([row["next"] for row in self._rows()],
                         ["a", "b", "c"])

    def test_message_batch_still_writes_once(self):
        # The old --message path doubled the writes (append + rewrite
        # per line). The message now rides the single batch write.
        n = self._counting(["seam", "--from-stdin", "--message", "T-1",
                            "--quiet"], stdin="a\nb\nc\n")
        self.assertEqual(n, 1)
        self.assertEqual([row.get("msg") for row in self._rows()],
                         ["T-1", "T-1", "T-1"])

    def test_single_row_seam_writes_once(self):
        # The standalone path kept its shape: one write, same bytes.
        n = self._counting(["seam", "--quiet"])
        self.assertEqual(n, 1)
        self.assertEqual(len(self._rows()), 1)

    def test_batch_rows_carry_per_line_math(self):
        # The row math (next from the line, verified/open counts,
        # per-line risk) still runs inside the loop exactly as the
        # old per-write path: the batch rows differ line by line
        # only in next/t, and every field the row-by-row path
        # produced is present.
        self._counting(["seam", "--from-stdin", "--quiet"],
                       stdin="dom: x\ndom: y\n")
        rows = self._rows()
        self.assertEqual([r["next"] for r in rows],
                         ["dom: x", "dom: y"])
        for row in rows:
            for field in ("t", "next", "verified", "open", "marker",
                          "confidence", "verifier", "risk", "error",
                          "outcome", "extra_steps"):
                self.assertIn(field, row)
        # Strictly non-decreasing timestamps, chronological order.
        self.assertLessEqual(rows[0]["t"], rows[1]["t"])

    def test_dry_run_batch_writes_zero(self):
        n = self._counting(["seam", "--from-stdin", "--dry-run",
                            "--quiet"], stdin="a\nb\nc\n")
        self.assertEqual(n, 0)
        self.assertEqual(self._rows(), [])

    def test_empty_stdin_writes_one_row(self):
        # 0 stdin lines still records the ordinary seam row — and
        # it lands in the single batch write (r174 semantics kept).
        n = self._counting(["seam", "--from-stdin", "--quiet"],
                           stdin="")
        self.assertEqual(n, 1)
        self.assertEqual(len(self._rows()), 1)

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("seam-from-stdin-single-write", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "seam-from-stdin-single-write")
        self.assertEqual(entry["since"], "r210")
        self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
