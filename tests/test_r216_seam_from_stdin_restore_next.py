# -*- coding: utf-8 -*-
"""Round 216 guards: seam --from-stdin restores the ledger Next.

The from-stdin batch loop temporarily sets ``book["Next"]`` so each
history row records the line it came from. That mutation leaked past
the loop into everything that ran afterwards:

- the JSON face reported ``payload.ledger.next`` as the *last stdin
  line* while the on-disk Next was unchanged (probe: disk
  ``ledger-next``, payload ``line-b``);
- the ledger-aware detectors that score after the append (goal
  alignment, ledger plan) compared recent next-actions against the
  mutated Next instead of the real one.

r216 saves the original Next before the loop and restores it before
any report or score is built. History rows still record each line.
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


class SeamFromStdinRestoreNextTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nledger-next\n", encoding="utf-8")
        self.history = self.ledger / "history.json"
        self.history.write_text("[]", encoding="utf-8")
        (self.ledger / "metacognition.json").write_text("{}", encoding="utf-8")
        (self.ledger / "skillbook.md").write_text("[]", encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_json_next_is_the_ledger_next_not_the_last_line(self):
        r = invoke_cli(self.workspace, ["seam", "--from-stdin", "--json"],
                       stdin="line-a\nline-b\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["ledger"]["next"], "ledger-next")

    def test_history_rows_still_record_each_line(self):
        r = invoke_cli(self.workspace, ["seam", "--from-stdin", "--json"],
                       stdin="line-a\nline-b\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = json.loads(self.history.read_text(encoding="utf-8"))
        self.assertEqual([row["next"] for row in rows],
                         ["line-a", "line-b"])

    def test_on_disk_ledger_next_unchanged(self):
        r = invoke_cli(self.workspace, ["seam", "--from-stdin", "--quiet"],
                       stdin="line-a\nline-b\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (self.ledger / "WORKSPACE.md").read_text(encoding="utf-8")
        self.assertIn("ledger-next", text)
        self.assertNotIn("line-b", text)

    def test_clean_seam_json_next_still_ledger_next(self):
        r = invoke_cli(self.workspace, ["seam", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["ledger"]["next"], "ledger-next")

    def test_single_stdin_line_also_restores(self):
        r = invoke_cli(self.workspace, ["seam", "--from-stdin", "--json"],
                       stdin="only-line\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["ledger"]["next"], "ledger-next")

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("seam-from-stdin-restore-next", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "seam-from-stdin-restore-next")
        self.assertEqual(entry["since"], "r216")
        self.assertIn("Next", entry["summary"])
        self.assertIn("last stdin line", entry["summary"])


if __name__ == "__main__":
    unittest.main()
