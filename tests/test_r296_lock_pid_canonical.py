# -*- coding: utf-8 -*-
"""Round 296 guards: the write.lock PID is canonical ASCII on the first line.

_write_lock_held_by is supposed to read "a single pid=N line" out of
.mindseam/write.lock. It used to do ``int(entire_file.strip())``, so:

* a trailing annotation (``pid=42\\nstarted=1``) raised ValueError and
  reported holder_pid=None for a lock that names a holder;
* ``pid=+42`` and a fullwidth ``pid=０４２`` folded to 42 (the r294
  round-tag looseness);
* ``pid=42 extra`` refused even though the pid is right there.

The writer emits ``pid=%d\\n`` and never produces the loose forms.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


class LockPidCanonicalTests(unittest.TestCase):

    def setUp(self):
        self.ledger = os.path.join(tempfile.mkdtemp(), ".mindseam")
        os.makedirs(self.ledger, exist_ok=True)
        self.lock = os.path.join(self.ledger, "write.lock")

    def _write(self, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        with open(self.lock, "wb") as fh:
            fh.write(body)

    def test_canonical_pid_line(self):
        for body, expected in (
                (b"pid=42", 42),
                (b"pid=42\n", 42),
                (b"pid=42\r\n", 42),
                (b"  pid=42  ", 42),
                (b"pid=42\n\n", 42),
                (b"pid=0\n", 0),
                (b"pid=99999\n", 99999)):
            self._write(body)
            self.assertEqual(
                mindseam._write_lock_held_by(self.ledger), expected, body)

    def test_trailing_annotation_keeps_holder(self):
        # The live-before-fix lie: int("42\\nstarted=1") raised and the
        # holder vanished from info --json lock_state.
        self._write(b"pid=42\nstarted=1\n")
        self.assertEqual(mindseam._write_lock_held_by(self.ledger), 42)
        self._write(b"pid=42\n# human comment\n")
        self.assertEqual(mindseam._write_lock_held_by(self.ledger), 42)

    def test_plus_sign_refused(self):
        self._write(b"pid=+42")
        self.assertIsNone(mindseam._write_lock_held_by(self.ledger))

    def test_fullwidth_digits_refused(self):
        self._write("pid=０４２".encode("utf-8"))
        self.assertIsNone(mindseam._write_lock_held_by(self.ledger))

    def test_leading_zeros_refused(self):
        self._write(b"pid=042")
        self.assertIsNone(mindseam._write_lock_held_by(self.ledger))
        self._write(b"pid=00042")
        self.assertIsNone(mindseam._write_lock_held_by(self.ledger))

    def test_trailing_garbage_refused(self):
        self._write(b"pid=42 extra")
        self.assertIsNone(mindseam._write_lock_held_by(self.ledger))

    def test_uppercase_refused(self):
        self._write(b"PID=42")
        self.assertIsNone(mindseam._write_lock_held_by(self.ledger))

    def test_malformed_refused(self):
        for body in (b"", b"pid=", b"pid=abc", b"junk\npid=42\n"):
            self._write(body)
            self.assertIsNone(mindseam._write_lock_held_by(self.ledger), body)

    def test_lock_info_reports_holder(self):
        self._write(b"pid=42\nstarted=1\n")
        info = mindseam._write_lock_info(self.ledger)
        self.assertEqual(info["holder_pid"], 42)
        self.assertFalse(info["owner_alive"])

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("lock-pid-canonical", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "lock-pid-canonical")
        self.assertEqual(entry["since"], "r296")
        self.assertIn("FIRST", entry["summary"])
        self.assertIn("canonical", entry["summary"])


if __name__ == "__main__":
    unittest.main()
