# -*- coding: utf-8 -*-
"""Round 186 guards: one health score per seam.

``session_health_score`` is a pure function of (hist, book) — roughly
thirty detectors over the stall window plus several full-history
scans. The seam payload needs the score, and the premature-convergence
fact inside ``observations`` needs the same score's risk/stall/compound
flags. The old call order ran the full suite twice per seam on the
same inputs: once inside ``observations`` (via
``premature_convergence``'s internal call) and once in ``mode_seam``
for the payload.

r186 computes the score once in ``mode_seam`` and passes the result
down: ``observations`` gains an optional ``health`` parameter and
``premature_convergence`` (fact mode) an optional ``health_result``.
Without the precomputed result, both fall back to the internal
computation, so every direct caller — and every existing test — sees
byte-identical behaviour.

These tests pin the observable contract: a seam invokes the scorer
exactly once, the payload number equals a direct recomputation, and
the fallback path still scores.
"""

import io
import json
import contextlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


class SeamHealthScoreCountTests(unittest.TestCase):
    """The seam computes the health score exactly once."""

    def setUp(self):
        self._old_cwd = os.getcwd()
        self.workspace = tempfile.mkdtemp()
        os.chdir(self.workspace)
        ledger = Path(self.workspace) / ".mindseam"
        ledger.mkdir(parents=True)
        (ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        self.ledger = ledger

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _capture(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mindseam.main(list(args))
        return buf.getvalue()

    def _counting(self):
        real = mindseam.session_health_score
        calls = []

        def wrapper(hist, book=None, run=None):
            calls.append(1)
            return real(hist, book=book, run=run)

        return real, wrapper, calls

    def test_seam_scores_once_with_sufficient_history(self):
        # Below STALL_RUN the premature-convergence fact short-circuits
        # before scoring, so the double-run only shows with enough
        # history to reach it. Four rows guarantee the fact path runs.
        self._capture("note", "--next", "dom: step 0")
        for _ in range(3):
            self._capture("seam", "--json")
            self._capture("note", "--next", "dom: step 0")
        real, wrapper, calls = self._counting()
        mindseam.session_health_score = wrapper
        try:
            self._capture("seam", "--json")
        finally:
            mindseam.session_health_score = real
        self.assertEqual(len(calls), 1,
                         "the seam must score the session exactly once")

    def test_seam_payload_score_matches_direct_recomputation(self):
        # Sharing the result must not change the number: the payload's
        # score equals a fresh score over the persisted history.
        for i in range(4):
            self._capture("note", "--next", "dom: step %d" % i)
            self._capture("seam", "--json")
        out = self._capture("seam", "--json")
        payload = json.loads(out[out.index("{"):])
        hist = json.loads(
            (self.ledger / "history.json").read_text(encoding="utf-8"))
        result = mindseam.session_health_score(
            hist, book=mindseam.read_ledger())
        self.assertEqual(payload["trend"]["score"]["value"], result.score)
        self.assertEqual(payload["trend"]["score"]["factors"],
                         list(result.reasons or []))


class PrecomputedResultTests(unittest.TestCase):
    """premature_convergence reuses a passed-in score and falls back."""

    def setUp(self):
        rows = [{"t": i + 1, "next": "dom: step %d" % i,
                 "verified": i + 1, "open": 0}
                for i in range(mindseam.STALL_RUN + 1)]
        self.hist = rows
        self.book = {"Goal": ["g"], "Core": [], "Verified": [],
                     "Open": [], "Next": ["n"]}

    def test_precomputed_result_skips_the_scorer(self):
        real = mindseam.session_health_score
        calls = []

        def wrapper(hist, book=None, run=None):
            calls.append(1)
            return real(hist, book=book, run=run)

        precomputed = real(self.hist, book=self.book)
        mindseam.session_health_score = wrapper
        try:
            facts = mindseam.premature_convergence(
                self.hist, book=self.book,
                health_result=precomputed)
        finally:
            mindseam.session_health_score = real
        self.assertEqual(calls, [])
        # The fact list is byte-identical to the recomputed path.
        self.assertEqual(
            facts,
            mindseam.premature_convergence(self.hist, book=self.book))

    def test_fallback_still_scores_without_health(self):
        # Direct callers without a precomputed result keep the old
        # behaviour: the internal session_health_score call runs.
        real = mindseam.session_health_score
        calls = []

        def wrapper(hist, book=None, run=None):
            calls.append(1)
            return real(hist, book=book, run=run)

        mindseam.session_health_score = wrapper
        try:
            mindseam.premature_convergence(self.hist, book=self.book)
        finally:
            mindseam.session_health_score = real
        self.assertEqual(len(calls), 1)

    def test_observations_passes_health_through(self):
        # observations forwards the health result to the fact, so a
        # caller holding a score pays for it once.
        real = mindseam.session_health_score
        calls = []

        def wrapper(hist, book=None, run=None):
            calls.append(1)
            return real(hist, book=book, run=run)

        precomputed = real(self.hist, book=self.book)
        mindseam.session_health_score = wrapper
        try:
            with_health = mindseam.observations(
                self.hist, book=self.book, health=precomputed)
            calls.clear()
            without_health = mindseam.observations(
                self.hist, book=self.book)
        finally:
            mindseam.session_health_score = real
        self.assertEqual(calls, [1], "fallback scores exactly once")
        self.assertEqual(with_health, without_health)


if __name__ == "__main__":
    unittest.main()
