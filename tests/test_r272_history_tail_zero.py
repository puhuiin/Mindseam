# -*- coding: utf-8 -*-
"""Round 272: ``history --tail 0`` / ``-n 0`` / ``--limit 0`` empty the
window instead of returning the whole history.

The untrusted-framing / tag-stranding family (r239-r271) reached every
line-oriented model-authored echo surface — each now routes through
``_oneline`` with its ``[untrusted: ...]`` tag on one physical line.
r272 turns to a different KIND of defect: a slicing-correctness bug on
history's own window selectors.

``mode_history`` borrows ``head -n N`` / ``tail -n N``: ``--head N`` keeps
the first N rows, ``--tail N`` (aliased by ``-n`` / ``--limit``) keeps the
last N. r217 already refuses every negative value with exit 2 before the
read, so the branch guards only ever see 0 or a positive. The head branch
was correct — ``hist[:0]`` empties — but the tail branch did::

    hist = hist[-tail_n:] if hist else []

and ``hist[-0:]`` is ``hist[0:]``, the WHOLE list.

LIVE DEFECT (``history`` with a five-row ``history.json``): ``--tail 0`` /
``-n 0`` / ``--limit 0`` printed all five rows at exit 0 — the opposite of
coreutils ``tail -n 0`` (which prints nothing) and of the correct
``--head 0`` (which empties). A host that asked for a zero-width tail
window got every row and an exit code that said the call worked, the same
silent-full-result lie r214/r217 closed for the negative case, one value
(zero) further in.

The inconsistency made it a genuine defect and not a design choice: the
``--keep`` rotation sibling a few lines up already guards
``truncated = hist[-keep_n:] if keep_n > 0 else []``, and ``--head 0``
already empties, so tail was the one selector letting the negative-zero
slice through. The fix guards ``tail_n`` too —
``hist = hist[-tail_n:] if (hist and tail_n) else []`` — so the zero
window empties the way the head and keep siblings do; a clean positive
window and the r217 negative refusal are both untouched.
"""

import ast
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from _controller_helper import invoke_cli

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


class HistoryTailZeroTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r272_")
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        self.history = self.ledger / "history.json"
        # The on-disk root is a bare LIST of row dicts (read_history
        # requires it), not a {"rows": [...]} wrapper.
        rows = [{
            "t": i, "next": "a: x%d" % i, "verified": i, "open": 0,
            "marker": "DONE", "confidence": "strong",
            "verifier": "pytest", "risk": "low",
            "error": "", "outcome": "ok", "extra_steps": 0,
        } for i in range(1, 6)]
        self.history.write_text(json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _count(self, *flags):
        r = invoke_cli(self.workspace, ["history", *flags, "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_tail_zero_empties(self):
        # The bug: hist[-0:] is the whole list.
        self.assertEqual(self._count("--tail", "0"), "0")

    def test_dash_n_zero_empties(self):
        self.assertEqual(self._count("-n", "0"), "0")

    def test_limit_zero_empties(self):
        self.assertEqual(self._count("--limit", "0"), "0")

    def test_head_zero_still_empties(self):
        # The correct sibling — kept as a regression guard.
        self.assertEqual(self._count("--head", "0"), "0")

    def test_tail_zero_json_face_is_empty(self):
        r = invoke_cli(self.workspace, ["history", "--tail", "0", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 0)
        self.assertEqual(payload["rows"], [])

    def test_positive_tail_still_works(self):
        self.assertEqual(self._count("--tail", "2"), "2")

    def test_positive_head_still_works(self):
        self.assertEqual(self._count("--head", "2"), "2")

    def test_dash_n_positive_still_works(self):
        self.assertEqual(self._count("-n", "3"), "3")

    def test_no_window_returns_all(self):
        # No selector at all still shows every row — the zero guard
        # must not leak into the unwindowed path.
        self.assertEqual(self._count(), "5")

    def test_negative_tail_still_refused(self):
        # r217 contract preserved: a negative value is refused with
        # exit 2 before any read, not treated as a zero window.
        before = self.history.read_bytes()
        r = invoke_cli(self.workspace, ["history", "--tail", "-1", "--count"])
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("non-negative", r.stderr)
        self.assertEqual(self.history.read_bytes(), before)


class HistoryTailZeroLargeHistoryTests(unittest.TestCase):
    """A larger history makes the whole-list regression unmissable."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r272big_")
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        ledger = Path(self.workspace) / ".mindseam"
        ledger.mkdir(parents=True, exist_ok=True)
        (ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        rows = [{
            "t": i, "next": "a: x%d" % i, "verified": i, "open": 0,
            "marker": "DONE", "confidence": "strong",
            "verifier": "pytest", "risk": "low",
            "error": "", "outcome": "ok", "extra_steps": 0,
        } for i in range(1, 41)]
        (ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_tail_zero_empties_forty_rows(self):
        r = invoke_cli(self.workspace, ["history", "--tail", "0", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "0")

    def test_tail_full_count_still_forty(self):
        r = invoke_cli(self.workspace, ["history", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "40")


class HistoryTailZeroSourceGuardTests(unittest.TestCase):
    """The tail branch must guard the count, not only ``if hist``."""

    def test_tail_branch_guards_the_count(self):
        src = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(
            encoding="utf-8")
        # The fixed slice guards ``tail_n`` so ``hist[-0:]`` cannot
        # reach the whole list. Scan the AST for the assignment rather
        # than the prose so a comment mentioning the old form cannot
        # satisfy the pin.
        tree = ast.parse(src)

        def is_guarded_tail_slice(node):
            # Match: hist = hist[-tail_n:] if (hist and tail_n) else []
            if not (isinstance(node, ast.Assign)
                    and isinstance(node.value, ast.IfExp)):
                return False
            test = node.value.test
            if not (isinstance(test, ast.BoolOp)
                    and isinstance(test.op, ast.And)):
                return False
            names = {v.id for v in ast.walk(test)
                     if isinstance(v, ast.Name)}
            return {"hist", "tail_n"}.issubset(names)

        self.assertTrue(
            any(is_guarded_tail_slice(n) for n in ast.walk(tree)),
            "the --tail branch no longer guards tail_n against the "
            "hist[-0:] whole-list slice")


class HistoryTailZeroCatalogTests(unittest.TestCase):

    def _since_ints(self):
        return [int(e["since"].lstrip("r"))
                for e in mindseam._FEATURE_CATALOG]

    def test_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-tail-zero", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-tail-zero")
        self.assertEqual(entry["since"], "r272")
        self.assertIn("tail -n 0", entry["summary"])
        self.assertIn("hist[-0:]", entry["summary"])

    def test_r272_is_the_highest_round(self):
        # The newest round owns the exact ``max == NNN`` head; it retires
        # to a ``>=`` floor once its successor lands.
        self.assertEqual(max(self._since_ints()), 272)

    def test_catalog_grew_to_123(self):
        self.assertEqual(len(mindseam._FEATURE_CATALOG), 123)

    def test_recent_window_is_93(self):
        recent = [i for i in self._since_ints() if i >= 170]
        self.assertEqual(len(recent), 93)


if __name__ == "__main__":
    unittest.main()
