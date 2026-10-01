# -*- coding: utf-8 -*-
"""Round 315 guards: escalation_likelihood handles an empty run.

The unguarded avg / float(total) raised ZeroDivisionError out of
observations(run=[]) and session_health_score(run=[]).
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _row(**kw):
    d = {"t": 1, "next": "a: one", "verified": 0, "open": 0,
         "marker": "", "confidence": "", "verifier": "", "error": "",
         "outcome": "", "extra_steps": 0, "msg": "", "risk": "low"}
    d.update(kw)
    return d


class EscalationEmptyRunGuardTests(unittest.TestCase):

    def setUp(self):
        self.hist = [_row(next="x: %d" % i) for i in range(5)]

    def test_escalation_empty_run_returns_zero(self):
        self.assertEqual(mindseam.escalation_likelihood(self.hist, run=[]), 0)

    def test_escalation_empty_hist_returns_zero(self):
        self.assertEqual(mindseam.escalation_likelihood([]), 0)

    def test_observations_empty_run_no_crash(self):
        facts = mindseam.observations(self.hist, run=[])
        self.assertIsInstance(facts, list)

    def test_health_score_empty_run_no_crash(self):
        r = mindseam.session_health_score(self.hist, run=[])
        self.assertIsNotNone(r.score)

    def test_all_subcalls_tolerate_empty_run(self):
        for name in (
                "detect_stall", "detect_risk_escalation", "detect_recovery",
                "confidence_volatility", "detect_volatility", "stall_score",
                "recovery_quality", "entropy_reservoir", "drift_velocity",
                "resolution_rate", "loop_detection", "escalation_likelihood",
                "tension_resolution", "goal_alignment_score",
                "assumption_diversity", "output_momentum",
                "confidence_verification_alignment",
                "incomplete_verification"):
            fn = getattr(mindseam, name)
            try:
                fn(self.hist, run=[])
            except Exception as exc:
                self.fail("%s crashed on empty run: %s" % (name, exc))

    def test_nonempty_path_unchanged(self):
        run = self.hist[-3:]
        run[-1] = _row(risk="high", next="y: 1")
        run[-2] = _row(risk="medium", next="y: 2")
        run[-3] = _row(risk="low", next="y: 3")
        score = mindseam.escalation_likelihood(self.hist, run=run)
        self.assertGreater(score, 0)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("escalation-empty-run-guard", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "escalation-empty-run-guard")
        self.assertEqual(entry["since"], "r315")
        self.assertIn("ZeroDivision", entry["summary"])


if __name__ == "__main__":
    unittest.main()
