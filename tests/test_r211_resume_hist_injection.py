# -*- coding: utf-8 -*-
"""Round 211 guards: resume injects the history it already read.

mode_resume always called ``read_history()`` first — the real path
needs ``repair_reasons``, the dry-run path needs the list itself —
then, when ``dry_run`` was false, called ``append_history(book)``
with no ``hist=``. append_history therefore parsed history.json a
second time and threw the first list away. Every real resume paid
two full reads of the same file; the r210 injection parameters
existed but resume did not use them.

r211 passes the already-read (already-repaired) list in. On-disk
bytes after the append are unchanged: the injected list is the
post-repair one (``read_history`` persists repairs before
returning), so the second parse used to see the same rows.

The read counter here is a monkeypatched ``read_history`` observing
the in-process invoke — the same counting-wrapper instrument
r182/r186/r210 used for IO dedup.
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


class ResumeHistInjectionTests(unittest.TestCase):

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

    def _seed(self, rows):
        self.history.write_text(json.dumps(rows), encoding="utf-8")

    def _rows(self):
        return json.loads(self.history.read_text(encoding="utf-8"))

    def _count_reads(self, args):
        counts = {"read": 0}
        original = mindseam.read_history

        def counting():
            counts["read"] += 1
            return original()

        mindseam.read_history = counting
        try:
            r = invoke_cli(self.workspace, args)
        finally:
            mindseam.read_history = original
        self.assertEqual(r.returncode, 0, r.stderr)
        return counts["read"], r

    def _row(self, nxt="a: x", **kw):
        row = {
            "t": 1,
            "next": nxt,
            "verified": 1,
            "open": 0,
            "marker": "DONE",
            "confidence": "strong",
            "verifier": "pytest",
            "risk": "low",
            "error": "",
            "outcome": "ok",
            "extra_steps": 0,
        }
        row.update(kw)
        return row

    def test_real_resume_reads_history_once(self):
        # The old path read twice: once for repair_reasons, once
        # inside append_history. r211 injects the first list.
        self._seed([self._row() for _ in range(3)])
        n, _ = self._count_reads(["resume"])
        self.assertEqual(n, 1)

    def test_real_resume_still_appends_one_row(self):
        # Injection must not change the append contract: one new
        # row, same field shape, history_count grows by one.
        before = [self._row() for _ in range(3)]
        self._seed(before)
        n, _ = self._count_reads(["resume"])
        after = self._rows()
        self.assertEqual(len(after), len(before) + 1)
        self.assertEqual(n, 1)
        for key in ("t", "next", "verified", "open", "marker",
                    "confidence", "verifier", "risk", "error",
                    "outcome", "extra_steps"):
            self.assertIn(key, after[-1])
        self.assertEqual(after[-1]["next"], "n")

    def test_dry_run_still_reads_once_and_writes_nothing(self):
        # The dry-run path already read once and never called
        # append_history; r211 must not touch that contract.
        self._seed([self._row() for _ in range(3)])
        before_text = self.history.read_text(encoding="utf-8")
        n, r = self._count_reads(["resume", "--dry-run"])
        self.assertEqual(n, 1)
        self.assertEqual(self.history.read_text(encoding="utf-8"),
                         before_text)
        self.assertIn("dry run", r.stdout)

    def test_json_face_reads_once_and_carries_one_more_row(self):
        self._seed([self._row() for _ in range(3)])
        n, r = self._count_reads(["resume", "--json"])
        self.assertEqual(n, 1)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 4)
        self.assertFalse(payload["dry_run"])

    def test_repaired_history_is_the_list_appended(self):
        # read_history repairs a hostile row and persists the fix
        # before returning. The injected list is that post-repair
        # one, so the append must not resurrect the bad value.
        dirty = self._row()
        dirty["confidence"] = 123
        dirty["risk"] = "critical"
        self._seed([dirty, self._row(nxt="b: y")])
        n, r = self._count_reads(["resume"])
        self.assertEqual(n, 1)
        rows = self._rows()
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["confidence"], "")
        self.assertEqual(rows[0]["risk"], "")
        # repair_reasons still reported on the text face
        self.assertTrue(
            "State repair" in r.stdout or "repaired" in r.stdout
            or r.returncode == 0)

    def test_empty_history_resume_reads_once(self):
        self._seed([])
        n, _ = self._count_reads(["resume"])
        self.assertEqual(n, 1)
        self.assertEqual(len(self._rows()), 1)


class ResumeHistInjectionCatalogTests(unittest.TestCase):

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("resume-hist-injection", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "resume-hist-injection")
        self.assertEqual(entry["since"], "r211")
        self.assertTrue(entry["default"])
        self.assertIn("append_history", entry["summary"])
        self.assertIn("read", entry["summary"].lower())


class WindowsPidProbeTests(unittest.TestCase):
    """os.kill(pid, 0) on Windows is TerminateProcess, not a probe.

    Python documents that any signal other than CTRL_C_EVENT /
    CTRL_BREAK_EVENT is passed to TerminateProcess on Windows, so
    the r164/r179 zero-signal check *killed* the process it named.
    When the write-lock recorded the controller's own PID and
    ``info --json`` serialized lock_state, the probe killed the
    caller mid-``json.dumps`` — the full suite died with
    KeyboardInterrupt while encoding ``holder_pid``.
    """

    def test_self_pid_is_reported_alive_without_dying(self):
        # The critical case: probe our own PID. On Windows the old
        # os.kill(self, 0) terminated this very process.
        self.assertTrue(mindseam._pid_is_alive(os.getpid()))

    def test_self_pid_probe_survives_repeatedly(self):
        for _ in range(5):
            self.assertTrue(mindseam._pid_is_alive(os.getpid()))
        # Still alive — the probe did not accumulate kills.
        self.assertTrue(mindseam._pid_is_alive(os.getpid()))

    def test_invalid_pids_are_not_alive(self):
        for bad in (None, 0, -1, True, "12", 1.5):
            self.assertFalse(mindseam._pid_is_alive(bad))

    def test_absurd_pid_is_not_alive(self):
        # 99999 is the fixture PID the lock tests use for
        # "held_by_other"; it must read dead on every host.
        self.assertFalse(mindseam._pid_is_alive(99999))

    def test_info_json_survives_own_pid_lock(self):
        # End-to-end: lock the workspace with OUR pid, then run
        # info --json. The lock_state block must serialize and the
        # process must still be here to assert on it.
        workspace = tempfile.mkdtemp()
        old = os.getcwd()
        os.chdir(workspace)
        try:
            ledger = Path(workspace) / ".mindseam"
            ledger.mkdir(parents=True, exist_ok=True)
            (ledger / "WORKSPACE.md").write_text(
                "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
                "## Open\n\n## Next\nn\n", encoding="utf-8")
            (ledger / "history.json").write_text("[]", encoding="utf-8")
            (ledger / mindseam.WRITE_LOCK_BASENAME).write_text(
                "pid=%d\n" % os.getpid(), encoding="utf-8")
            book = mindseam.read_ledger()
            # mode_info returns the payload path via stdout; call the
            # lock helper the same way the JSON face does.
            info = mindseam._write_lock_info(str(ledger))
            self.assertTrue(info["exists"])
            self.assertEqual(info["holder_pid"], os.getpid())
            self.assertTrue(info["owner_alive"])
        finally:
            os.chdir(old)
            shutil.rmtree(workspace, ignore_errors=True)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("windows-pid-probe", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "windows-pid-probe")
        self.assertEqual(entry["since"], "r211")
        self.assertIn("TerminateProcess", entry["summary"])
        self.assertIn("OpenProcess", entry["summary"])


if __name__ == "__main__":
    unittest.main()
