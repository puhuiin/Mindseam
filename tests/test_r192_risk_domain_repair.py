# -*- coding: utf-8 -*-
"""Round 192 guards: an out-of-domain ``risk`` value cannot kill a command.

``read_history`` typed every string field but never bounded ``risk``,
which is not free text — it is a closed domain that ``session_health_score``
indexes a penalty table with:

    risk_penalty = {"high": -20, "medium": -10, "low": 0}
    if last_risk != "low":
        score += risk_penalty[last_risk]      # KeyError on "critical"

A perfectly good string like ``"critical"`` — a typo, a value from some
other tool, a hand-edited row — therefore passed the sanitizer and raised
KeyError out of ``info --health``, taking the whole command down with a
traceback and exit 1. ``_fuse_run`` already guarded the same table with
``if r and r in levels``; this one lookup did not.

r192 repairs the domain at the boundary, the way ``extra_steps``'
non-negative domain is already repaired, and adds the membership guard at
the use site for callers that never went through the boundary. Valid
values are untouched: a 4000-case differential against the pre-fix
implementation produced identical score, reasons, vol_changes, decay,
st_score, compound, risk_esc and has_stall on every one.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam
from _controller_helper import invoke_cli

LEDGER = ("# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n## Open\n\n## Next\nn\n")


def _rows(risk):
    return [{"t": 1757000000 + i, "next": "a: %d" % i, "verified": 0,
             "open": 0, "confidence": "strong", "risk": risk, "marker": "",
             "error": "", "outcome": "", "verifier": "", "extra_steps": 0}
            for i in range(6)]


class RiskDomainRepairTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        ledger = Path(self.workspace) / ".mindseam"
        ledger.mkdir(parents=True, exist_ok=True)
        (ledger / "WORKSPACE.md").write_text(LEDGER, encoding="utf-8")
        os.chdir(self.workspace)
        self.ledger = ledger

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _write_history(self, risk):
        (self.ledger / "history.json").write_text(
            json.dumps(_rows(risk)), encoding="utf-8")

    def test_the_domain_is_declared_once(self):
        self.assertEqual(mindseam.RISK_LEVELS, ("low", "medium", "high"))

    def test_out_of_domain_risk_is_repaired_to_absent(self):
        self._write_history("critical")
        rows, changed, reasons = mindseam.read_history()
        self.assertTrue(changed)
        self.assertTrue(all(r["risk"] == "" for r in rows), rows)
        # The repair is persisted, so the next reader sees a clean domain.
        on_disk = json.loads(
            (self.ledger / "history.json").read_text(encoding="utf-8"))
        self.assertTrue(all(r["risk"] == "" for r in on_disk), on_disk)

    def test_in_domain_values_survive_untouched(self):
        for value in ("low", "medium", "high", ""):
            self._write_history(value)
            rows, changed, _ = mindseam.read_history()
            self.assertFalse(changed, value)
            self.assertEqual(rows[0]["risk"], value)

    def test_an_unknown_value_cannot_reach_the_penalty_table(self):
        # Direct caller, no boundary: the use-site guard must hold.
        result = mindseam.session_health_score(_rows("critical"))
        self.assertIsInstance(result.score, int)
        self.assertFalse(any("critical risk" in r for r in result.reasons))

    def test_in_domain_risk_still_earns_its_penalty(self):
        # The score itself clamps at 0 on a uniform six-row history, so
        # the penalty is read off the reasons rather than the total.
        medium = mindseam.session_health_score(_rows("medium"))
        low = mindseam.session_health_score(_rows("low"))
        self.assertTrue(any("medium risk (-10)" in r for r in medium.reasons),
                        medium.reasons)
        self.assertFalse(any("risk (" in r for r in low.reasons),
                         low.reasons)

    def test_info_health_survives_a_corrupted_history(self):
        # The original failure: KeyError escaped as a traceback + exit 1.
        self._write_history("critical")
        r = invoke_cli(self.workspace, ["info", "--health"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertNotIn("KeyError", r.stderr)

    def test_seam_survives_a_corrupted_history(self):
        self._write_history("critical")
        r = invoke_cli(self.workspace, ["seam"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_every_string_field_survives_a_plausible_unknown_value(self):
        # The same class of defect in any other closed-domain field would
        # show up here as a non-zero exit rather than a silent repair.
        for field in ("risk", "marker", "confidence", "outcome", "verifier",
                      "error"):
            rows = _rows("low")
            for row in rows:
                row[field] = "ZZZ-unknown"
            (self.ledger / "history.json").write_text(
                json.dumps(rows), encoding="utf-8")
            for args in (["info", "--health"], ["info", "--json"], ["seam"],
                         ["audit"]):
                r = invoke_cli(self.workspace, args)
                self.assertEqual(r.returncode, 0,
                                 "%s with %s=ZZZ-unknown" % (args, field))
                self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
