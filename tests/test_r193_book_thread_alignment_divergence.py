# -*- coding: utf-8 -*-
"""Round 193 guards: a detector whose tests and writer disagree on the format.

``book_thread_alignment`` compares the last action's domain prefix against
the most recent ``Open`` ledger row. Its eleven unit tests in
``test_r38_detectors.py`` feed it rows shaped ``"alpha:task1"`` — a
hand-written ``domain: text`` form.

The controller never writes that form. ``note --open`` appends

    "?%02d %s — settled by: %s" % (num, args.open, settle)

so a real row reads ``?01 which cache policy — settled by: a benchmark``.
The detector takes ``split(":", 1)[0]`` of that, which lands on the colon
inside ``settled by:`` and yields ``"?01 which cache policy — settled by"``.
That can never equal a next-action domain, so the detector returns 0 for
every ledger the controller can produce, whatever the session does.

It is not dead in the statistical sense — it returns 100 whenever there is
no Open row to compare against — which is exactly why a corpus of random
sessions does not settle it, and why the unit tests stayed green. The
divergence is only visible when a real ledger meets the real detector, so
that is what this round pins.

The first test states the behaviour the docstring promises and is marked
as an expected failure. When someone repairs the detector it will start
passing unexpectedly, which is the signal to delete the marker and keep
the assertion as a real guard.
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

    @unittest.expectedFailure
    def test_alignment_fires_on_a_ledger_the_writer_produced(self):
        # What the docstring promises: a live action tracking the live
        # thread scores 100. It does not, on any domain, for any ledger
        # the controller writes.
        self._open_question()
        book = mindseam.read_ledger()
        self.assertEqual(
            mindseam.book_thread_alignment(_history("build"), book), 100)

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
