# -*- coding: utf-8 -*-
"""Round 222 guards: seam --quiet and --json refuse to compose.

r202 closed the ``--quiet`` + ``--format`` pair: the format branch
won and dropped quiet without a word. ``--quiet`` + ``--json`` had
the same shape — the dispatcher checked ``json_flag or
format_path`` first, so ``seam --quiet --json`` emitted the full
payload and the one-word-facts request vanished.

r222 refuses the face pair with exit 2 before any ledger work,
naming both flags. ``--format`` still rides ``--json`` (r170).
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


class SeamQuietJsonExclusiveTests(unittest.TestCase):

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
        (self.ledger / "metacognition.json").write_text("{}", encoding="utf-8")
        (self.ledger / "skillbook.md").write_text("[]", encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_quiet_json_refused(self):
        before = self.history.read_bytes()
        r = invoke_cli(self.workspace, ["seam", "--quiet", "--json"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--quiet", r.stderr)
        self.assertIn("--json", r.stderr)
        self.assertIn("mutually exclusive", r.stderr)
        # Refused before any ledger work: history untouched.
        self.assertEqual(self.history.read_bytes(), before)

    def test_quiet_alone_still_works(self):
        r = invoke_cli(self.workspace, ["seam", "--quiet"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(json.loads(self.history.read_text(
            encoding="utf-8"))), 1)

    def test_json_alone_still_works(self):
        r = invoke_cli(self.workspace, ["seam", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("ledger", payload)
        self.assertFalse(payload["dry_run"])

    def test_quiet_format_still_refused(self):
        r = invoke_cli(self.workspace, ["seam", "--quiet", "--format",
                                        "ledger.next"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--quiet", r.stderr)

    def test_json_format_still_composes(self):
        r = invoke_cli(self.workspace, ["seam", "--json", "--format",
                                        "ledger.next"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "n")

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("seam-quiet-json-exclusive", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "seam-quiet-json-exclusive")
        self.assertEqual(entry["since"], "r222")
        self.assertIn("refuse to compose", entry["summary"])
        self.assertIn("r202", entry["summary"])


if __name__ == "__main__":
    unittest.main()
