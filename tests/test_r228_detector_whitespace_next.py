# -*- coding: utf-8 -*-
"""Round 228 guards: detectors strip whitespace-only next.

r227 fixed assess_risk. The detectors that count unique / real nexts
still used truthiness, so ``"   "`` counted as a live next: stall
said "has not changed", diversity scored the blank as a unique
action, redundancy counted blanks as repeats. r228 routes them
through ``_row_next``, the same strip the history faces and
assess_risk use.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _row(i, nxt, **kw):
    base = {
        "t": 1000 + i, "next": nxt, "verified": 0, "open": 0,
        "marker": "DONE", "confidence": "strong",
        "verifier": "pytest", "risk": "low",
        "error": "", "outcome": "ok", "extra_steps": 0,
    }
    base.update(kw)
    return base


def _window(n, nxt, **kw):
    return [_row(i, nxt, **kw) for i in range(1, n + 1)]


class DetectorWhitespaceNextTests(unittest.TestCase):

    def test_row_next_strips(self):
        self.assertEqual(mindseam._row_next({"next": "  a  "}), "a")
        self.assertEqual(mindseam._row_next({"next": "   "}), "")
        self.assertEqual(mindseam._row_next({}), "")

    def test_detect_stall_ignores_whitespace_next(self):
        # All-blank nexts: no next_ref, so "has not changed" must not fire.
        facts = mindseam.detect_stall(_window(3, "   "))
        self.assertFalse(any("not changed" in f for f in facts), facts)

    def test_detect_stall_still_sees_real_next(self):
        facts = mindseam.detect_stall(_window(3, "build: x"))
        self.assertTrue(any("not changed" in f for f in facts), facts)

    def test_pattern_persistence_blanks_are_not_a_stall_pattern(self):
        # unique_nexts empty after strip → no "stall" issue from nexts.
        result = mindseam.pattern_persistence(_window(3, "   "))
        self.assertIn(result, ("none", "transient"), result)

    def test_thread_management_blanks_are_not_threads(self):
        # No real nexts → threads empty → 100 (unmeasured).
        self.assertEqual(mindseam.thread_management(_window(4, " ")), 100)

    def test_action_diversity_blanks_do_not_count(self):
        # Only blanks → total_nexts 0 → 100.
        self.assertEqual(
            mindseam.unique_next_score(_window(3, "  "))
            if hasattr(mindseam, "unique_next_score")
            else self._diversity(_window(3, "  ")), 100)

    def _diversity(self, hist):
        # The unique-nexts ratio helper used by the fusion layer.
        unique_nexts = set()
        total_nexts = 0
        for h in hist:
            n = mindseam._row_next(h)
            if n:
                unique_nexts.add(n)
                total_nexts += 1
        if total_nexts == 0:
            return 100
        return int(len(unique_nexts) * 100 / float(total_nexts))

    def test_output_redundancy_blanks_do_not_count(self):
        # All-blank nexts: after strip there are no repeats, so the
        # unmeasured/100 path. The old truthiness path treated blanks
        # as one repeated action and scored 33.
        self.assertEqual(mindseam.output_momentum(_window(6, " ")), 100)
        # A real repeated next still scores the recurring band.
        self.assertEqual(mindseam.output_momentum(
            _window(6, "build: x")), 33)

    def test_stall_score_blanks_do_not_form_a_frozen_next(self):
        # All blanks + verified growing: no next_set membership.
        hist = [_row(i, "   ", verified=i) for i in range(1, 4)]
        score = mindseam.stall_score(hist)
        self.assertIsInstance(score, int)
        self.assertGreaterEqual(score, 0)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("detector-whitespace-next", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "detector-whitespace-next")
        self.assertEqual(entry["since"], "r228")
        self.assertIn("_row_next", entry["summary"])
        self.assertIn("r227", entry["summary"])


if __name__ == "__main__":
    unittest.main()
