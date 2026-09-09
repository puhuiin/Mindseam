# -*- coding: utf-8 -*-
"""Round 184 guards: atomic_write_text is idempotent.

The old ``atomic_write_text`` always rewrote the target — temp file,
os.replace — even when the new text was byte-identical to the on-disk
content. Any content-identical write churned mtime-based change
detection (r165 ``info --mtime``, r166 ``info --changed``) for no
information gain, and any same-text rewrite of ``metacognition.json``
/ ``skillbook.md`` invalidated a host's "did the ledger change?"
answer every time a seam ran.

r184 short-circuits the write when ``text.encode("utf-8")`` equals
the existing bytes: no temp file, no os.replace, no mtime bump. The
on-disk content is untouched, so every contract that observes the
artefact's *bytes or mtime* — ``info --changed``, ``info --mtime``,
``audit --baseline`` fingerprinting, a git watcher on ``.mindseam/`` —
reads the same answer before and after an identical write.

Two invariants must hold for the short-circuit to be safe:

1. Lock hygiene: the advisory write lock is acquired *before* the
   dedup check, so the no-op branch must release it before returning,
   or a lingering ``write.lock`` (EEXIST) would refuse every later
   write as "locked by another writer (pid=?)".

2. Byte fidelity: a changed write still lands byte-for-byte, and a
   write to a *missing* target still creates it (the first write is
   never a no-op).
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


class AtomicWriteIdempotencyTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        self.target = self.ledger / "probe.txt"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_identical_write_is_a_noop(self):
        # First write creates the file; the identical rewrite must
        # not bump mtime, so change detectors stay quiet.
        err = mindseam.atomic_write_text(str(self.target), "hello")
        self.assertIsNone(err)
        mtime = self.target.stat().st_mtime_ns
        time.sleep(0.02)
        err = mindseam.atomic_write_text(str(self.target), "hello")
        self.assertIsNone(err)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "hello")
        self.assertEqual(self.target.stat().st_mtime_ns, mtime)

    def test_noop_does_not_leak_write_lock(self):
        # The no-op branch sits inside the lock scope; an unsent
        # write.lock would poison every later write. After an
        # identical rewrite, the lock must be gone and a changed
        # write must still succeed.
        err = mindseam.atomic_write_text(str(self.target), "a")
        self.assertIsNone(err)
        err = mindseam.atomic_write_text(str(self.target), "a")
        self.assertIsNone(err)
        self.assertFalse((self.ledger / "write.lock").exists())
        err = mindseam.atomic_write_text(str(self.target), "b")
        self.assertIsNone(err)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "b")
        self.assertFalse((self.ledger / "write.lock").exists())

    def test_changed_write_still_lands(self):
        err = mindseam.atomic_write_text(str(self.target), "one")
        self.assertIsNone(err)
        err = mindseam.atomic_write_text(str(self.target), "two")
        self.assertIsNone(err)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "two")

    def test_first_write_never_noop(self):
        # A missing target cannot be compared; the first write must
        # always create the file.
        err = mindseam.atomic_write_text(str(self.target), "first")
        self.assertIsNone(err)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "first")

    def test_unicode_identical_still_noop(self):
        # Non-ASCII content: the byte comparison must still recognise
        # an identical rewrite even though the writer's text mode maps
        # LF to CRLF on Windows. Sleep past NTFS's mtime granularity
        # (~100ms) so a real rewrite would definitely bump mtime; the
        # identical write must not.
        text = "验证:\n✓ 已完成\n深字串内容"
        err = mindseam.atomic_write_text(str(self.target), text)
        self.assertIsNone(err)
        mtime = self.target.stat().st_mtime_ns
        time.sleep(0.3)
        err = mindseam.atomic_write_text(str(self.target), text)
        self.assertIsNone(err)
        self.assertEqual(self.target.read_text(encoding="utf-8"), text)
        self.assertEqual(self.target.stat().st_mtime_ns, mtime)
        # The write path is still alive: a changed write bumps mtime.
        time.sleep(0.3)
        err = mindseam.atomic_write_text(str(self.target), "changed")
        self.assertIsNone(err)
        self.assertNotEqual(self.target.stat().st_mtime_ns, mtime)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "changed")

    def test_seam_meta_match_skips_rewrite_when_content_identical(self):
        # A real seam changes the meta (the risk trend appends each
        # run), so two consecutive seams legitimately differ. The
        # contract r184 protects is narrower: a byte-identical
        # write to the same path must not churn the file. Drive that
        # through the seam surface by writing the same meta bytes
        # back through atomic_write_text and asserting the mtime is
        # untouched — the seam test in r183 already covers the
        # dry-run side.
        meta = {
            "risk": {"level": "low", "reasons": []},
            "trend": {"risk": ["low"]},
            "schema_version": 1,
        }
        meta_path = self.ledger / "metacognition.json"
        err = mindseam.atomic_write_text(
            str(meta_path), json.dumps(meta, ensure_ascii=False))
        self.assertIsNone(err)
        mtime = meta_path.stat().st_mtime_ns
        time.sleep(0.3)
        err = mindseam.atomic_write_text(
            str(meta_path), json.dumps(meta, ensure_ascii=False))
        self.assertIsNone(err)
        self.assertEqual(meta_path.stat().st_mtime_ns, mtime)


if __name__ == "__main__":
    unittest.main()