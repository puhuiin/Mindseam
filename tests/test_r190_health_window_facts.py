# -*- coding: utf-8 -*-
"""Round 190 guards: the health score's window facts are a named unit.

session_health_score had grown to 670 lines, and its first ~120 were not
scoring at all: they were a scan over the run window that produced 22
boolean presence flags the scoring half then consulted. That scan
mutated nothing in the running total, so it was lifted out whole into
_health_window_facts, which returns a _WindowFacts namedtuple.

The lift is behaviour-preserving by construction -- the block moved
verbatim -- and was checked against the pre-lift implementation over
20,000 randomly generated histories: identical score, reasons,
vol_changes, decay, st_score, compound, risk_esc and has_stall on every
one. This round pins the contract a future edit must keep: the field set
and order, the pure-function property, and the caller's unpacking order,
so the namedtuple and the unpack can never drift apart silently.
"""

import inspect
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam

EXPECTED_FIELDS = (
    "adjacent_next_pair_in_run",
    "conf_label_in_run",
    "domain_in6",
    "done_any3",
    "effort_or_delivery3",
    "err_events3x2",
    "err_events4",
    "err_pairs6",
    "err_recoverable",
    "esc6",
    "hi_conf_in_run",
    "high_low_risk6",
    "marker_pair_in_run",
    "next_in3",
    "next_in4",
    "strong_conf_in_run",
    "thread_evt4",
    "va_measured",
    "verified6",
    "verified_in_run",
    "verifier_in_run",
    "vt6",
)


class HealthWindowFactsTests(unittest.TestCase):

    def test_field_set_and_order_are_pinned(self):
        self.assertTrue(hasattr(mindseam, "_WindowFacts"))
        self.assertTrue(hasattr(mindseam, "_health_window_facts"))
        self.assertEqual(mindseam._WindowFacts._fields, EXPECTED_FIELDS)

    def test_caller_unpacks_in_the_declared_field_order(self):
        # The namedtuple and the unpack are two halves of one contract;
        # if they drift, every flag silently shifts by one position.
        source = inspect.getsource(mindseam.session_health_score)
        match = re.search(
            r"\(([^)]*)\)\s*=\s*_health_window_facts\(hist\)", source, re.S)
        self.assertIsNotNone(
            match, "session_health_score no longer unpacks _health_window_facts")
        names = tuple(n.strip() for n in match.group(1).split(",") if n.strip())
        self.assertEqual(names, EXPECTED_FIELDS)

    def test_empty_history_yields_every_flag_false(self):
        facts = mindseam._health_window_facts([])
        for name in EXPECTED_FIELDS:
            self.assertFalse(getattr(facts, name), name)

    def test_facts_are_pure_and_repeatable(self):
        hist = [
            {"next": "build: a", "verified": 1, "confidence": "shaky",
             "marker": "OPEN", "verifier": "pytest", "risk": "high"},
            {"next": "build: b", "verified": 0, "confidence": "thin",
             "marker": "DONE", "error": "db timeout", "risk": "low"},
            {"next": "build: c", "verified": 2, "confidence": "strong",
             "verifier": "pytest", "outcome": "ok"},
            {"next": "test: d", "verified": 0, "confidence": "shaky"},
        ]
        first = mindseam._health_window_facts(list(hist))
        second = mindseam._health_window_facts(list(hist))
        self.assertEqual(first, second)
        self.assertIsInstance(first, tuple)

    def test_the_scan_no_longer_lives_in_the_scoring_function(self):
        # The whole point of the lift: the scoring half reads a bundle
        # instead of re-running the window scan inline.
        source = inspect.getsource(mindseam.session_health_score)
        self.assertIn("_health_window_facts(hist)", source)
        self.assertNotIn('win6 = hist[-(STALL_RUN * 2):]', source)
        self.assertLess(len(source.splitlines()), 600)


if __name__ == "__main__":
    unittest.main()
