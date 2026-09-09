# -*- coding: utf-8 -*-
"""Round 179 guards: stale write-lock detection and recovery.

r164 introduced ``.mindseam/write.lock`` using the same
``O_CREAT | O_EXCL`` pattern as Git's ``index.lock``. That
prevents concurrent writers, but a process killed between
acquire and release can leave a permanent lock that blocks
every future note / seam. r179 adds conservative stale-lock
recovery.

A lock is stale only when BOTH conditions hold:

1. the PID is missing, malformed, or no longer alive; and
2. the file is at least 300 seconds old.

The two-signal rule prevents a newly-created lock whose PID
line has not flushed yet from being mistaken for a crashed
writer, and never deletes a live process's lock just because
its operation is slow. The next writer deletes a proven-
stale lock once, then retries the same atomic acquire.
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


def _invoke(args, cwd):
    return subprocess.run(
        [sys.executable, str(MINDSEAM), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8")


class StaleLockBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _lock(self, body="pid=99999999\n", age=400):
        path = self.ledger / "write.lock"
        path.write_text(body, encoding="utf-8")
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
        return path

    def _workspace(self):
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn1\n", encoding="utf-8")


class PidLivenessTests(unittest.TestCase):

    def test_current_pid_is_alive(self):
        self.assertTrue(mindseam._pid_is_alive(os.getpid()))

    def test_invalid_pid_is_not_alive(self):
        for value in (None, 0, -1, True, "1"):
            self.assertFalse(mindseam._pid_is_alive(value))

    def test_impossible_pid_is_not_alive(self):
        self.assertFalse(mindseam._pid_is_alive(99999999))


class LockInfoTests(StaleLockBase):

    def test_missing_lock_is_free(self):
        info = mindseam._write_lock_info(str(self.ledger))
        self.assertFalse(info["exists"])
        self.assertFalse(info["stale"])
        self.assertEqual(info["age_seconds"], 0)

    def test_old_dead_lock_is_stale(self):
        self._lock(age=mindseam.WRITE_LOCK_STALE_SECONDS + 10)
        info = mindseam._write_lock_info(str(self.ledger))
        self.assertTrue(info["exists"])
        self.assertFalse(info["owner_alive"])
        self.assertTrue(info["stale"])
        self.assertGreaterEqual(
            info["age_seconds"], mindseam.WRITE_LOCK_STALE_SECONDS)

    def test_fresh_dead_lock_is_not_stale(self):
        self._lock(age=1)
        info = mindseam._write_lock_info(str(self.ledger))
        self.assertFalse(info["owner_alive"])
        self.assertFalse(info["stale"])

    def test_old_live_lock_is_not_stale(self):
        self._lock(body="pid=%d\n" % os.getpid(), age=1000)
        info = mindseam._write_lock_info(str(self.ledger))
        self.assertTrue(info["owner_alive"])
        self.assertFalse(info["stale"])

    def test_old_malformed_lock_is_stale(self):
        self._lock(body="garbage\n", age=400)
        info = mindseam._write_lock_info(str(self.ledger))
        self.assertIsNone(info["holder_pid"])
        self.assertTrue(info["stale"])


class StaleRecoveryTests(StaleLockBase):

    def test_clear_stale_lock(self):
        lock = self._lock(age=400)
        self.assertTrue(mindseam._clear_stale_write_lock(str(self.ledger)))
        self.assertFalse(lock.exists())

    def test_fresh_lock_not_cleared(self):
        lock = self._lock(age=1)
        self.assertFalse(mindseam._clear_stale_write_lock(str(self.ledger)))
        self.assertTrue(lock.exists())

    def test_live_lock_not_cleared(self):
        lock = self._lock(body="pid=%d\n" % os.getpid(), age=1000)
        self.assertFalse(mindseam._clear_stale_write_lock(str(self.ledger)))
        self.assertTrue(lock.exists())

    def test_next_writer_recovers_stale_lock(self):
        self._workspace()
        lock = self._lock(age=400)
        r = _invoke(["note", "--next", "n2"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(lock.exists())
        text = (self.ledger / "WORKSPACE.md").read_text(encoding="utf-8")
        self.assertIn("n2", text)

    def test_next_writer_still_refuses_fresh_dead_lock(self):
        self._workspace()
        lock = self._lock(age=1)
        r = _invoke(["note", "--next", "n2"], self.workspace)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertTrue(lock.exists())
        text = (self.ledger / "WORKSPACE.md").read_text(encoding="utf-8")
        self.assertIn("n1", text)
        self.assertNotIn("n2", text)


class InfoLockStateTests(StaleLockBase):

    def test_info_reports_stale_metadata(self):
        self._workspace()
        self._lock(age=400)
        r = _invoke(["info", "--json"], self.workspace)
        payload = json.loads(r.stdout)
        state = payload["lock_state"]
        self.assertEqual(state["state"], "stale")
        self.assertTrue(state["stale"])
        self.assertFalse(state["owner_alive"])
        self.assertGreaterEqual(state["age_seconds"], 300)
        self.assertEqual(state["stale_after_seconds"], 300)

    def test_health_marks_stale_lock_degraded(self):
        self._workspace()
        self._lock(age=400)
        r = _invoke(["info", "--json", "--health"], self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["health"]["status"], "degraded")
        kinds = [reason["kind"] for reason in payload["health"]["reasons"]]
        self.assertIn("stale_write_lock", kinds)


class CatalogTests(unittest.TestCase):

    def test_feature_in_catalog(self):
        ids = {entry["id"] for entry in mindseam._FEATURE_CATALOG}
        self.assertIn("stale-write-lock-recovery", ids)

    def test_feature_since_r179(self):
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "stale-write-lock-recovery")
        self.assertEqual(entry["since"], "r179")
        self.assertTrue(entry["default"])
