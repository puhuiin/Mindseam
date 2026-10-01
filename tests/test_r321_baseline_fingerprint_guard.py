# -*- coding: utf-8 -*-
"""Round 321 guards: _fingerprint_findings skips non-dict baseline items.

A host-authored baseline JSON with non-dict items crashed
finding.get() out of audit --baseline.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam
from _controller_helper import invoke_cli


class BaselineFingerprintTypeGuardTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])
        invoke_cli(self.workspace, ["note", "--open", "same",
                                    "--settled-by", "all cases covered"])
        invoke_cli(self.workspace, ["note", "--open", "same",
                                    "--settled-by", "all cases covered"])

    def test_mixed_baseline_skips_non_dicts(self):
        p = os.path.join(self.workspace, "b.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump([1, "x", {"tag": "delete",
                                "what": "Open #2 repeats Open #1"}], fh)
        r = invoke_cli(self.workspace,
                       ["audit", "--baseline", "b.json", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(len(d["findings"]), 0)
        self.assertEqual(len(d["baselined_findings"]), 1)

    def test_all_nondict_baseline_matches_nothing(self):
        p = os.path.join(self.workspace, "b.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump([1, "x", None, True], fh)
        r = invoke_cli(self.workspace,
                       ["audit", "--baseline", "b.json", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(len(d["findings"]), 1)

    def test_dict_baseline_unchanged(self):
        r = invoke_cli(self.workspace,
                       ["audit", "--baseline-write", "b.json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        r = invoke_cli(self.workspace,
                       ["audit", "--baseline", "b.json", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(len(d["baselined_findings"]), 1)

    def test_fingerprint_findings_skips_non_dicts(self):
        fps = mindseam._fingerprint_findings(
            [1, "x", {"tag": "delete", "what": "w"}, None])
        self.assertEqual(len(fps), 1)

    def test_fingerprint_findings_empty(self):
        self.assertEqual(mindseam._fingerprint_findings([]), set())
        self.assertEqual(mindseam._fingerprint_findings(None), set())
        self.assertEqual(mindseam._fingerprint_findings([1, 2]), set())

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("baseline-fingerprint-type-guard", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "baseline-fingerprint-type-guard")
        self.assertEqual(entry["since"], "r321")
        self.assertIn("fingerprint", entry["summary"])


if __name__ == "__main__":
    unittest.main()
