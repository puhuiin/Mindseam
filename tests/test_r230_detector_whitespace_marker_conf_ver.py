# -*- coding: utf-8 -*-
"""Round 230 guards: detectors strip whitespace-only marker/confidence/verifier.

The r228/r229 strip family reaches the tag fields. A window of
``marker="   "`` / ``confidence="  "`` / ``verifier="  "`` used to
count as tagged steps: observations reported "the same marker has
been recorded", assess_risk saw a stuck confidence, and ship's
gate treated a blank confidence as a real tag that needed settling.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from _controller_helper import invoke_cli

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _row(i, **kw):
    base = {
        "t": i, "next": "build: x", "verified": 0, "open": 0,
        "marker": "", "confidence": "", "verifier": "",
        "risk": "low", "error": "", "outcome": "ok", "extra_steps": 0,
    }
    base.update(kw)
    return base


class DetectorWhitespaceTagTests(unittest.TestCase):

    def test_helpers_strip(self):
        self.assertEqual(mindseam._row_marker({"marker": " PHEW "}), "PHEW")
        self.assertEqual(mindseam._row_marker({"marker": "   "}), "")
        self.assertEqual(mindseam._row_confidence({"confidence": " shaky "}),
                         "shaky")
        self.assertEqual(mindseam._row_confidence({"confidence": "\t"}), "")
        self.assertEqual(mindseam._row_verifier({"verifier": " pytest "}),
                         "pytest")
        self.assertEqual(mindseam._row_verifier({"verifier": " "}), "")

    def test_observations_ignores_whitespace_marker(self):
        hist = [_row(i, marker="   ") for i in range(1, 5)]
        facts = mindseam.observations(hist, meta={}, book=None)
        self.assertFalse(
            any("same marker" in f.lower() for f in facts), facts)

    def test_observations_still_sees_real_marker(self):
        hist = [_row(i, marker="GRRR") for i in range(1, 5)]
        facts = mindseam.observations(hist, meta={}, book=None)
        self.assertTrue(
            any("same marker" in f.lower() for f in facts), facts)

    def test_assess_risk_ignores_whitespace_confidence(self):
        hist = [_row(i, confidence="  ") for i in range(1, 5)]
        _, reasons = mindseam.assess_risk(hist)
        self.assertFalse(
            any("confidence is stuck" in r for r in reasons), reasons)

    def test_assess_risk_still_sees_stuck_thin(self):
        hist = [_row(i, confidence="thin") for i in range(1, 5)]
        _, reasons = mindseam.assess_risk(hist)
        self.assertTrue(
            any("confidence is stuck" in r for r in reasons), reasons)

    def test_ship_gate_ignores_whitespace_confidence(self):
        workspace = tempfile.mkdtemp()
        old = os.getcwd()
        os.chdir(workspace)
        try:
            led = Path(workspace) / ".mindseam"
            led.mkdir()
            (led / "WORKSPACE.md").write_text(
                "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
                "## Open\n\n## Next\nn\n", encoding="utf-8")
            rows = [_row(i, confidence="  ") for i in range(1, 3)]
            (led / "history.json").write_text(
                __import__("json").dumps(rows), encoding="utf-8")
            out = Path(workspace) / "out.md"
            out.write_text("clean prose.\n", encoding="utf-8")
            r = invoke_cli(workspace, ["ship", str(out), "--json"])
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = __import__("json").loads(r.stdout)
            self.assertFalse(
                any("shaky confidence" in g for g in payload["gate"]),
                payload["gate"])
        finally:
            os.chdir(old)
            import shutil
            shutil.rmtree(workspace, ignore_errors=True)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("detector-whitespace-marker-conf-ver", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "detector-whitespace-marker-conf-ver")
        self.assertEqual(entry["since"], "r230")
        self.assertIn("_row_marker", entry["summary"])
        self.assertIn("ship", entry["summary"])


if __name__ == "__main__":
    unittest.main()
