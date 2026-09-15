# -*- coding: utf-8 -*-
"""Round 225 guards: skillbook hard domains lowercase like discover.

r224 made discover lowercase the next-action domain. extract_skillbook
still kept the raw prefix for ``hard`` patterns, so ``Build`` and
``build`` mined as two entries — each below
SKILLBOOK_MIN_RECURRENCE (2) alone, so neither shipped. Probe shape:
two extra-step rows with mixed-case domains produced an empty
skillbook; after the fix one hard pattern with count 2 ships.
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


class SkillbookHardDomainLowercaseTests(unittest.TestCase):

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
            "t": i, "next": nxt, "verified": 0, "open": 0,
            "marker": "DONE", "confidence": "strong",
            "verifier": "pytest", "risk": "low",
            "error": "", "outcome": "ok", "extra_steps": 2,
        } for i, nxt in enumerate(("Build: a", "build: b"), 1)]
        self.history.write_text(json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_mixed_case_hard_domains_merge(self):
        entries = mindseam.extract_skillbook(
            json.loads(self.history.read_text(encoding="utf-8")))
        hard = [e for e in entries if e["kind"] == "hard"]
        self.assertEqual(len(hard), 1, entries)
        self.assertEqual(hard[0]["text"], "build")
        self.assertEqual(hard[0]["count"], 2)

    def test_skillbook_command_shows_merged_pattern(self):
        r = invoke_cli(self.workspace, ["skillbook", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        entries = json.loads(r.stdout)
        hard = [e for e in entries if e["kind"] == "hard"]
        self.assertEqual(len(hard), 1)
        self.assertEqual(hard[0]["text"], "build")

    def test_single_casing_still_works(self):
        self.history.write_text(json.dumps([{
            "t": 1, "next": "audit: x", "verified": 0, "open": 0,
            "marker": "DONE", "confidence": "strong",
            "verifier": "pytest", "risk": "low",
            "error": "", "outcome": "ok", "extra_steps": 1,
        }, {
            "t": 2, "next": "audit: y", "verified": 0, "open": 0,
            "marker": "DONE", "confidence": "strong",
            "verifier": "pytest", "risk": "low",
            "error": "", "outcome": "ok", "extra_steps": 1,
        }]), encoding="utf-8")
        entries = mindseam.extract_skillbook(
            json.loads(self.history.read_text(encoding="utf-8")))
        hard = [e for e in entries if e["kind"] == "hard"]
        self.assertEqual(hard[0]["text"], "audit")

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("skillbook-hard-domain-lowercase", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "skillbook-hard-domain-lowercase")
        self.assertEqual(entry["since"], "r225")
        self.assertIn("lowercase", entry["summary"])
        self.assertIn("SKILLBOOK_MIN_RECURRENCE", entry["summary"])


if __name__ == "__main__":
    unittest.main()
