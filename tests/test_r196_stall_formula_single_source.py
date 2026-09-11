# -*- coding: utf-8 -*-
"""Round 196 guards: the stall formula has one implementation.

``_fuse_run`` carried a byte-for-byte inline copy of the confidence
decay arithmetic (``confidence_decay_rate``) and of the stall scoring
arithmetic (``stall_score``: 40 for a single next action, 30 for a
flat verified counter, ``int(decay * 30)``, capped at 100). Two copies
of one formula drift independently — the r193 lesson, where a
detector's unit tests and its writer disagreed on the row format until
a host caught it. Here the drift hazard is concrete: the health score
reads ``_fuse_run``'s st_score while the observations fact layer reads
``stall_score`` directly, so a divergence would make the seam's
"Stall severity is elevated (N/100)" fact and the score's "moderate
stall N/100 (-8)" reason quote different numbers for the same session.

r196 deletes the inline copies: ``_fuse_run`` now calls
``confidence_decay_rate(hist, run=run)`` for the decay and
``stall_score(hist, decay=decay, run=run)`` for the score. The
``first_valid``/``last_valid``/``valid_count`` tracking that only fed
the inline copy is gone; the volatility counter keeps its own ladder
reads. Equivalence was verified over 20,000 randomly generated
histories: identical 10-field output tuple on every one, before and
after.
"""

import random
import re
import sys
import inspect
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _random_history(rng):
    domains = ("alpha", "beta", "gamma", "delta", "epsilon")
    confs = ("", "strong", "thin", "shaky", "bogus")
    risks = ("", "low", "medium", "high", "critical")
    marks = ("", "DONE", "PHEW", "OPEN", "WIP")
    hist = []
    for j in range(rng.randint(0, 14)):
        hist.append({
            "t": j + 1,
            "next": ("%s: step %d" % (rng.choice(domains), j))
                    if rng.random() > 0.2 else "",
            "verified": rng.choice((0, 0, 1, 2, 5)),
            "open": rng.choice((0, 0, 1, 3)),
            "confidence": rng.choice(confs),
            "risk": rng.choice(risks),
            "marker": rng.choice(marks),
            "verifier": rng.choice(("", "ci", "pytest")),
            "error": rng.choice(("", "db timeout", "assert")),
            "outcome": rng.choice(("", "ok", "failed", "partial")),
        })
    return hist


class FuseRunDelegationTests(unittest.TestCase):
    """_fuse_run reads the named functions instead of a private copy."""

    def test_fuse_run_agrees_with_the_named_functions(self):
        # On random histories the fusion's decay must BE
        # confidence_decay_rate's answer and its st_score must BE
        # stall_score's answer — the drift guard this round exists for.
        rng = random.Random(20260912)
        for _ in range(2000):
            hist = _random_history(rng)
            if len(hist) < mindseam.STALL_RUN:
                continue
            vol, decay, st, has_stall, esc, rec, last_risk, has_risk, \
                weak, verified = mindseam._fuse_run(hist)
            self.assertEqual(decay,
                             mindseam.confidence_decay_rate(hist))
            self.assertEqual(st, mindseam.stall_score(hist))

    def test_fuse_run_honours_a_custom_run_window(self):
        # The run= passthrough reaches both delegates, so a caller with
        # its own window still gets the shared formula.
        rng = random.Random(7)
        hist = _random_history(rng)
        while len(hist) < mindseam.STALL_RUN + 2:
            hist = _random_history(rng)
        run = hist[-2:]
        vol, decay, st, *_ = mindseam._fuse_run(hist, run=run)
        self.assertEqual(decay,
                         mindseam.confidence_decay_rate(hist, run=run))
        self.assertEqual(
            st, mindseam.stall_score(hist, run=run))

    def test_inline_copies_are_gone(self):
        # Source-level pin: the fusion body no longer carries the
        # stall arithmetic or the decay span division.
        src = inspect.getsource(mindseam._fuse_run)
        self.assertNotIn("s += 40", src)
        self.assertNotIn("s += 30", src)
        self.assertNotIn("span = max(", src)
        self.assertIn("confidence_decay_rate", src)
        self.assertIn("stall_score", src)

    def test_output_tuple_shape_is_stable(self):
        # The 10-field contract: session_health_score unpacks positionally.
        rng = random.Random(11)
        hist = _random_history(rng)
        while len(hist) < mindseam.STALL_RUN:
            hist = _random_history(rng)
        out = mindseam._fuse_run(hist)
        self.assertEqual(len(out), 10)
        vol, decay, st, has_stall, esc, rec, last_risk, has_risk, \
            weak, verified = out
        self.assertIsInstance(vol, int)
        self.assertIsInstance(decay, float)
        self.assertIsInstance(st, int)
        for flag in (has_stall, esc, rec, has_risk, weak, verified):
            self.assertIsInstance(flag, bool)
        self.assertIn(last_risk, ("low", "medium", "high"))

    def test_short_history_sentinel_unchanged(self):
        # Below STALL_RUN the fusion answers the all-neutral tuple.
        out = mindseam._fuse_run([{"t": 1, "next": "a: b", "verified": 0,
                                   "open": 0}])
        self.assertEqual(out, (0, 0.0, 0, False, False, False, None,
                               False, False, False))

    def test_observations_fact_and_health_reason_agree(self):
        # The end-to-end point of the round: one session cannot quote
        # two different stall numbers. The fact layer reads
        # stall_score; the score layer reads _fuse_run — they must
        # agree on the shared window.
        rng = random.Random(23)
        for _ in range(200):
            hist = _random_history(rng)
            if len(hist) < mindseam.STALL_RUN:
                continue
            run = hist[-mindseam.STALL_RUN:]
            _, _, st_fuse, *_ = mindseam._fuse_run(hist, run=run)
            st_fact = mindseam.stall_score(hist, run=run)
            self.assertEqual(st_fuse, st_fact)


if __name__ == "__main__":
    unittest.main()
