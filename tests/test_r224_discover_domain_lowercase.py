# -*- coding: utf-8 -*-
"""Round 224 guards: discover lowercases domains like history --domains.

Probe before the fix: three next-actions with domain prefixes
``Build`` / ``build`` / ``BUILD`` produced

    discover:        3 entries, one visit each
    history --domains: 1 entry, count 3, share 1.0

Discover treated casing as a domain identity, so ``suggested_next``
could name ``BUILD`` while ``history --domains`` said ``build``.
r224 lowercases the prefix in discover, matching the history face.
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


class DiscoverDomainLowercaseTests(unittest.TestCase):

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
            "error": "", "outcome": "ok", "extra_steps": 0,
        } for i, nxt in enumerate(
            ("Build: step", "build: other", "BUILD: third"), 1)]
        self.history.write_text(json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_discover_merges_casings(self):
        r = invoke_cli(self.workspace, ["discover", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["domains"],
                         [{"name": "build", "visits": 3}])
        self.assertEqual(payload["suggested_next"], "build")

    def test_discover_matches_history_domains(self):
        d = json.loads(invoke_cli(
            self.workspace, ["discover", "--json"]).stdout)
        h = json.loads(invoke_cli(
            self.workspace, ["history", "--domains", "--json"]).stdout)
        self.assertEqual([x["name"] for x in d["domains"]],
                         [x["domain"] for x in h["domains"]])
        self.assertEqual([x["visits"] for x in d["domains"]],
                         [x["count"] for x in h["domains"]])

    def test_single_casing_still_works(self):
        self.history.write_text(json.dumps([{
            "t": 1, "next": "audit: check", "verified": 0, "open": 0,
            "marker": "DONE", "confidence": "strong",
            "verifier": "pytest", "risk": "low",
            "error": "", "outcome": "ok", "extra_steps": 0,
        }]), encoding="utf-8")
        r = invoke_cli(self.workspace, ["discover", "--json"])
        payload = json.loads(r.stdout)
        self.assertEqual(payload["suggested_next"], "audit")

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("discover-domain-lowercase", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "discover-domain-lowercase")
        self.assertEqual(entry["since"], "r224")
        self.assertIn("lowercase", entry["summary"])
        self.assertIn("history --domains", entry["summary"])


if __name__ == "__main__":
    unittest.main()
