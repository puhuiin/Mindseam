# -*- coding: utf-8 -*-
"""Round 240 guards: book_thread_alignment repaired for the Open row format.

r193 pinned the divergence (the detector compared ``split(":", 1)[0]``
of a ``?NN question — settled by: test`` row against a next-action
domain, landing on the colon inside ``settled by:``, so it could never
fire on any ledger the controller writes) and marked its assertion as
an expected failure — the r193 docstring said the marker would come
off when someone repaired the detector, and that removal would be the
signal.

r240 is that repair: the question text is extracted (``?NN`` prefix
and the `` — settled by:`` suffix stripped) before the domain check.
These tests are the real guards the xfail was standing in for, filed
under the round that made them true so the suite's round numbering
stays gap-free — a round that changes behaviour owns a test file, and
the r112 guard enforces exactly that.
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


def _history(domain):
    return [{"t": i + 1, "next": "%s: step %d" % (domain, i),
             "verified": i + 1, "open": 1} for i in range(4)]


class RepairedAlignmentTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _open_question(self):
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ntrack the cache\n\n## Core\n\n"
            "## Verified\n\n## Open\n?01 cache: the index is stale — "
            "settled by: a rebuild\n\n## Next\ndom: step\n",
            encoding="utf-8")

    def test_alignment_fires_on_a_ledger_the_writer_produced(self):
        # What the docstring promises: a live action tracking the live
        # thread scores 100 (r240 repaired the detector; the
        # expectedFailure marker r193 set is gone).
        self._open_question()
        book = mindseam.read_ledger()
        self.assertEqual(
            mindseam.book_thread_alignment(_history("cache"), book), 100)

    def test_alignment_is_zero_when_domain_diverges(self):
        self._open_question()
        book = mindseam.read_ledger()
        self.assertEqual(
            mindseam.book_thread_alignment(_history("deploy"), book), 0)

    def test_the_marker_is_gone_and_the_assertion_is_real(self):
        # r193's own closing note: the day the repair lands, the
        # marker must be deleted rather than left in place quietly.
        # Assert on the DECORATORS, not the prose (both files quote
        # the marker's name while explaining its removal).
        import ast as _ast
        for name in ("test_r193_book_thread_alignment_divergence.py",
                     "test_r240_book_thread_alignment_repaired.py"):
            tree = _ast.parse(
                (ROOT / "tests" / name).read_text(encoding="utf-8"))
            decorators = []
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.ClassDef)):
                    for dec in node.decorator_list:
                        decorators.append(_ast.unparse(dec))
            self.assertNotIn("expectedFailure", " ".join(decorators), name)
            self.assertNotIn("xfail", " ".join(decorators), name)

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("book-thread-alignment-open-format", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "book-thread-alignment-open-format")
        self.assertEqual(entry["since"], "r240")
        self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
