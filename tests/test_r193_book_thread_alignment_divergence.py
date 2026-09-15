# -*- coding: utf-8 -*-
"""Round 193/240 guards: book_thread_alignment vs the Open row format.

r193 pinned the divergence: the controller writes Open rows as
``?NN question — settled by: test`` while the detector compared
``split(":", 1)[0]`` of that string — landing on the colon inside
``settled by:`` — against a next-action domain. The detector could
never fire on any ledger the controller produces.

r240 repaired the detector: it now extracts the question text
(``?NN`` prefix and `` — settled by:`` suffix stripped) and checks
the next-action domain against it. The expectedFailure marker is
removed; the assertions below are real guards.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import mindseam
from _controller_helper import invoke_cli

LEDGER = ("# L\n\n## Goal\nbuild the cache\n\n## Core\n\n## Verified\n\n"
          "## Open\n\n## Next\nn\n")


def _history(domain):
    return [{"t": 1757000000 + i * 60, "next": "%s: step %d" % (domain, i),
             "verified": 1, "open": 0, "confidence": "strong",
             "verifier": "pytest", "risk": "low", "marker": "DONE",
             "error": "", "outcome": "ok", "extra_steps": 0}
            for i in range(6)]


class BookThreadAlignmentDivergenceTests(unittest.TestCase):

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

    def _open_question(self):
        r = invoke_cli(self.workspace,
                       ["note", "--open", "which cache policy",
                        "--settled-by", "a benchmark"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_the_writer_emits_the_numbered_question_form(self):
        # If this ever changes, the divergence below changes with it.
        self._open_question()
        text = (self.ledger / "WORKSPACE.md").read_text(encoding="utf-8")
        self.assertIn("?01 which cache policy — settled by: a benchmark", text)

    def test_the_writer_never_emits_a_bare_domain_row(self):
        # The only shape the detector can match is one the writer cannot
        # produce, which is the whole defect.
        self._open_question()
        book = mindseam.read_ledger()
        for row in book["Open"]:
            self.assertNotEqual(row.strip(), "build")
            self.assertNotIn(row.split(":", 1)[0].strip(), ("build", "review"))

    def test_alignment_fires_on_a_ledger_the_writer_produced(self):
        # What the docstring promises: a live action tracking the live
        # thread scores 100. r240 repaired the detector — it now
        # extracts the question text from the Open row and checks the
        # next-action domain against it, so this assertion is a real
        # guard (the expectedFailure marker is removed).
        self._open_question()
        book = mindseam.read_ledger()
        self.assertEqual(
            mindseam.book_thread_alignment(_history("cache"), book), 100)

    def test_alignment_is_zero_when_domain_diverges(self):
        self._open_question()
        book = mindseam.read_ledger()
        self.assertEqual(
            mindseam.book_thread_alignment(_history("deploy"), book), 0)

    def test_it_is_pinned_to_zero_across_every_domain(self):
        # The observed fact this round is filed against: not "sometimes
        # wrong" but "cannot fire", whatever the session does.
        self._open_question()
        book = mindseam.read_ledger()
        scores = {domain: mindseam.book_thread_alignment(_history(domain), book)
                  for domain in ("build", "review", "test", "docs", "deploy")}
        self.assertEqual(set(scores.values()), {0}, scores)

    def test_the_shape_its_own_tests_use_still_scores_100(self):
        # Confirms the mismatch is the format and not the comparison: the
        # hand-written shape the r38 tests use passes untouched.
        book = {"Open": ["build: which cache policy"]}
        self.assertEqual(
            mindseam.book_thread_alignment(_history("build"), book), 100)


if __name__ == "__main__":
    unittest.main()
