# -*- coding: utf-8 -*-
"""Round 181 guards: the health velocity trend.

Borrowed from open-gsd/gsd-core's STATE.md health block: a
velocity line that recomputes the score at each of the last
few work-unit boundaries and classifies the movement as
``Improving / Stable / Degrading``. Mindseam's health score
is a pure function of (hist, book), so re-slicing the same
history at earlier boundaries is a faithful replay of what
the score would have been at each seam — no new state, no
new counters, just a projection of the existing function.

The classifier splits the score window into two halves (the
older run and the recent run, the way gsd-core prints its
"Last 5 plans" bracket), takes the mean of each, and calls
the movement ``improving`` when the recent mean exceeds the
older mean by ``VELOCITY_DELTA`` or more, ``degrading`` when
it is lower by ``delta`` or more, and ``stable`` otherwise.
Fewer than ``VELOCITY_WINDOW`` rows is ``insufficient`` —
not enough boundaries to measure, the way the health score
itself returns a neutral 100 below ``STALL_RUN``.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from _controller_helper import invoke_cli

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _invoke(args, cwd):
    return invoke_cli(cwd, args)


def _row(i, confidence=None, next_action="dom: step"):
    # Monotonically growing ``verified`` and distinct domains:
    # the score's pattern detectors penalise repeated actions
    # and stale verification, so flat fixtures would
    # manufacture penalties unrelated to the trend under
    # test. The confidence signal is the only variable.
    row = {"t": i + 1,
           "next": "%s step %d" % (
               ("alpha", "beta", "gamma", "delta", "epsilon",
                "zeta", "eta", "theta")[i % 8], i),
           "verified": i + 1, "open": 0}
    if confidence:
        row["confidence"] = confidence
    return row


class VelocityBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _history(self, rows):
        (self.ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def _velocity(self):
        r = _invoke(["info", "--json", "--health"], self.workspace)
        return json.loads(r.stdout)["health"]["velocity"]


class VelocityClassifierTests(unittest.TestCase):
    """The half-window mean split and the delta threshold."""

    def test_insufficient_below_window(self):
        rows = [_row(i) for i in range(mindseam.VELOCITY_WINDOW - 1)]
        trend, scores = mindseam.velocity_trend(rows)
        self.assertEqual(trend, "insufficient")
        self.assertEqual(scores, [])

    def test_stable_when_flat(self):
        rows = [_row(i) for i in range(mindseam.VELOCITY_WINDOW)]
        trend, scores = mindseam.velocity_trend(rows)
        self.assertEqual(trend, "stable", scores)
        # Unmeasurable prefixes (len < STALL_RUN) are skipped, so
        # a 5-row window yields STALL_RUN measured boundaries.
        self.assertEqual(len(scores),
                         mindseam.VELOCITY_WINDOW
                         - mindseam.STALL_RUN + 1)

    def test_improving_when_late_scores_higher(self):
        # Early shaky confidence pulls the older half down;
        # the recent half is clean, so the mean rises.
        rows = [_row(0, confidence="shaky"),
                _row(1, confidence="shaky"),
                _row(2), _row(3), _row(4)]
        trend, scores = mindseam.velocity_trend(rows, delta=5)
        self.assertEqual(trend, "improving", scores)
        self.assertEqual(scores[0], min(scores))

    def test_degrading_when_late_scores_lower(self):
        # The opposite ordering: clean early, shaky late.
        rows = [_row(0), _row(1), _row(2, confidence="shaky"),
                _row(3, confidence="shaky"), _row(4)]
        trend, scores = mindseam.velocity_trend(rows, delta=5)
        self.assertEqual(trend, "degrading", scores)

    def test_small_drift_is_stable(self):
        # One shaky row mid-window is not enough movement to
        # cross the delta; the trend must stay stable rather
        # than flapping on a single seam.
        rows = [_row(0), _row(1, confidence="shaky"),
                _row(2), _row(3), _row(4)]
        trend, _ = mindseam.velocity_trend(rows, delta=5)
        self.assertEqual(trend, "stable")


class VelocitySurfaceTests(VelocityBase):
    """The velocity block rides on info --health."""

    def test_velocity_block_present(self):
        self._history([_row(i) for i in range(6)])
        velocity = self._velocity()
        self.assertIn(velocity["trend"],
                      ("improving", "stable", "degrading",
                       "insufficient"))
        self.assertEqual(velocity["window"],
                         mindseam.VELOCITY_WINDOW)
        self.assertEqual(velocity["delta"], mindseam.VELOCITY_DELTA)
        self.assertIsInstance(velocity["scores"], list)

    def test_velocity_insufficient_on_short_history(self):
        self._history([_row(i) for i in range(3)])
        velocity = self._velocity()
        self.assertEqual(velocity["trend"], "insufficient")
        self.assertEqual(velocity["scores"], [])

    def test_velocity_scores_are_ints(self):
        self._history([_row(i) for i in range(6)])
        velocity = self._velocity()
        for score in velocity["scores"]:
            self.assertIsInstance(score, int)

    def test_text_face_still_prints_health_without_velocity(self):
        # The r165 text face is unchanged: the velocity block
        # is JSON-only (a host reading text gets the same
        # sectioned report as before), the way every r161+
        # additive block has been JSON-face only.
        self._history([_row(i) for i in range(6)])
        r = _invoke(["info", "--health"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("velocity", r.stdout)


class VelocityCatalogTests(unittest.TestCase):

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("health-velocity-trend", ids)

    def test_feature_since_r181(self):
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "health-velocity-trend")
        self.assertEqual(entry["since"], "r181")
        self.assertTrue(entry["default"])
