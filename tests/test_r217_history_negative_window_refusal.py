# -*- coding: utf-8 -*-
"""Round 217 guards: history numeric window flags refuse negatives.

r214 closed the silent no-op for ``--keep -1``. The rest of the
numeric window flags had the same ``value >= 0`` guard and the same
lie: ``--head -1`` / ``--tail -2`` / ``--limit -3`` / ``--since -10``
/ ``--until -10`` all exited 0 reporting the full history, so a host
that asked for a narrowed window got every row and an exit code that
said the call worked.

r217 refuses every negative value in that family with exit 2 before
any history read, matching audit --since and note --extra-steps.
Zero stays legal (``--head 0`` empties, ``--keep 0`` empties).

Also: ``info --check`` now rejects a bool timestamp the way
``read_history``'s repair does. bool is a subclass of int, so a
corrupted ``true`` used to pass the classifier while the repair
would have replaced it.
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


class HistoryNegativeWindowRefusalTests(unittest.TestCase):

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
        } for i in range(1, 6)]
        self.history.write_text(json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _assert_refused(self, flag, value):
        before = self.history.read_bytes()
        r = invoke_cli(self.workspace,
                       ["history", flag, str(value), "--count"])
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn(flag, r.stderr)
        self.assertIn("non-negative", r.stderr)
        self.assertEqual(self.history.read_bytes(), before)

    def test_head_negative_refused(self):
        self._assert_refused("--head", -1)

    def test_tail_negative_refused(self):
        self._assert_refused("--tail", -2)

    def test_limit_negative_refused(self):
        self._assert_refused("--limit", -3)

    def test_since_negative_refused(self):
        self._assert_refused("--since", -10)

    def test_until_negative_refused(self):
        self._assert_refused("--until", -10)

    def test_keep_still_refused(self):
        self._assert_refused("--keep", -1)

    def test_zero_head_still_empties(self):
        r = invoke_cli(self.workspace, ["history", "--head", "0", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "0")

    def test_positive_flags_still_work(self):
        r = invoke_cli(self.workspace, ["history", "--tail", "2", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "2")


class InfoCheckBoolTimestampTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        # t=True is a bool, which isinstance(..., int) accepts.
        (self.ledger / "history.json").write_text(
            json.dumps([{
                "t": True, "next": "a: x", "verified": 0, "open": 0,
                "marker": "", "confidence": "", "verifier": "",
                "risk": "", "error": "", "outcome": "", "extra_steps": 0,
            }]), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_check_flags_bool_timestamp(self):
        # read_history repairs True away; --check must classify it
        # the same way rather than treating bool as a valid int.
        issues = mindseam._info_check_issues(
            mindseam.read_ledger(),
            [{"t": True, "next": "a: x", "verified": 0, "open": 0}],
            gap_seconds=0)
        self.assertTrue(any("not int" in i for i in issues), issues)

    def test_check_accepts_real_int_timestamp(self):
        issues = mindseam._info_check_issues(
            mindseam.read_ledger(),
            [{"t": 1, "next": "a: x", "verified": 0, "open": 0}],
            gap_seconds=0)
        self.assertFalse(any("not int" in i for i in issues), issues)


class HistoryNegativeWindowCatalogTests(unittest.TestCase):

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-negative-window-refusal", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-negative-window-refusal")
        self.assertEqual(entry["since"], "r217")
        self.assertIn("exit 2", entry["summary"])
        self.assertIn("bool", entry["summary"])


if __name__ == "__main__":
    unittest.main()
