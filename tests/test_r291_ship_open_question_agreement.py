# -*- coding: utf-8 -*-
"""r291 — the ship completion gate agrees noun and verb with the open count.

``mode_ship`` builds a list of completion-gate observations. One of
them reports the count of still-open questions before delivery. That
line hardcoded the lazy plural idiom::

    gate.append("%d open question(s) remain" % len(book["Open"]))

so a ledger with exactly one open question read "1 open question(s)
remain" — the wrong noun (``question(s)``) AND the wrong verb
(``remain``) at a count of one. It is the r281-r290 singular/plural
family, this time on the ship gate, a surface that with ``--strict``
flips the exit code from 0 to 2 (r156), so a CI host acts on the
string it carries.

Single chokepoint: the ``gate`` list feeds both the JSON face
(``payload["gate"]``) and the text face (``for g in gate: print(...)``),
so agreeing the string once agrees both faces by construction — the
r254/r259 precedent.

Probe (before the fix): a ledger with one open question and
``ship - --strict`` printed ``· 1 open question(s) remain`` on the
text face and ``["1 open question(s) remain"]`` on the JSON gate.
After the fix the same run reads "1 open question remains"; two open
questions read "2 open questions remain".
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from _controller_helper import run_controller

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _since_ints():
    return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]


class _Base(unittest.TestCase):
    def setUp(self):
        self._workspaces = []

    def tearDown(self):
        for ws in self._workspaces:
            shutil.rmtree(ws, ignore_errors=True)

    def _fresh_workspace(self):
        # A fresh workspace per probe so open questions never accumulate
        # across calls within one test method.
        ws = tempfile.mkdtemp(prefix="r291_")
        self._workspaces.append(ws)
        return ws

    def _build(self, count):
        ws = self._fresh_workspace()
        r = run_controller(ws, "note",
                           "--goal", "Ship verified output",
                           "--next", "Inspect inputs")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # Each --open adds one entry to the Open section. A settle is
        # supplied so the note itself is accepted; the gate reads only
        # the count.
        for i in range(1, count + 1):
            r = run_controller(
                ws, "note", "--next", "nx",
                "--open", "Q%d?" % i, "--settled-by", "b",
                "--confidence", "strong")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return ws

    def _gate_line(self, count):
        ws = self._build(count)
        r = run_controller(ws, "ship", "-", "--strict", stdin="draft text.")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        for line in r.stdout.splitlines():
            if "open question" in line:
                return line.strip()
        self.fail("no open-question gate line in:\n" + r.stdout)

    def _json_gate(self, count):
        ws = self._build(count)
        r = run_controller(ws, "ship", "-", "--json", stdin="draft text.")
        payload = json.loads(r.stdout)
        for g in payload["gate"]:
            if "open question" in g:
                return g
        self.fail("no open-question gate entry in:\n" + r.stdout)


class ShipOpenQuestionAgreementTests(_Base):
    """The gate line pluralizes noun and verb with the open count."""

    def test_single_open_question_is_singular(self):
        self.assertIn("1 open question remains", self._gate_line(1))

    def test_single_open_question_has_no_lazy_plural(self):
        line = self._gate_line(1)
        self.assertNotIn("question(s)", line)
        self.assertNotIn("1 open questions", line)

    def test_single_open_question_verb_agrees(self):
        # "remains" for one; never the plural "remain".
        line = self._gate_line(1)
        self.assertIn("remains", line)
        self.assertNotIn("questions remain", line)

    def test_two_open_questions_stay_plural(self):
        self.assertIn("2 open questions remain", self._gate_line(2))

    def test_three_open_questions_stay_plural(self):
        self.assertIn("3 open questions remain", self._gate_line(3))

    def test_plural_sweep_uses_plural_verb(self):
        for n in (2, 3, 4):
            line = self._gate_line(n)
            self.assertIn("%d open questions remain" % n, line)
            self.assertNotIn("remains", line)


class ShipOpenQuestionFacesAgreeTests(_Base):
    """Text and JSON gate render the one string, so they agree."""

    def test_single_faces_agree(self):
        self.assertEqual(self._json_gate(1), "1 open question remains")

    def test_plural_faces_agree(self):
        self.assertEqual(self._json_gate(2), "2 open questions remain")

    def test_text_and_json_carry_identical_string(self):
        text = self._gate_line(1)
        # The text face prefixes "· "; the JSON face carries the bare
        # string. Strip the marker and compare.
        self.assertTrue(text.endswith("1 open question remains"), text)
        self.assertEqual(self._json_gate(1), "1 open question remains")


class ShipStrictContractPreservedTests(_Base):
    """r156's strict exit contract is untouched by the noun fix."""

    def test_strict_with_open_question_exits_two(self):
        ws = self._build(1)
        r = run_controller(ws, "ship", "-", "--strict",
                           stdin="draft text.")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_non_strict_with_open_question_exits_zero(self):
        # Report-only without --strict: the gate observation is printed
        # but the exit stays 0.
        ws = self._build(1)
        r = run_controller(ws, "ship", "-",
                           stdin="draft text.")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("1 open question remains", r.stdout)

    def test_json_exit_matches_text_exit(self):
        ws = self._build(2)
        r = run_controller(ws, "ship", "-", "--strict", "--json",
                           stdin="draft text.")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["exit"], 2)


class CatalogPinTests(_Base):
    def test_entry_present_since_r291_default_true(self):
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "ship-open-question-agrees-noun-and-verb")
        self.assertEqual(entry["since"], "r291")
        self.assertTrue(entry["default"])

    def test_r291_is_the_highest_round(self):
        # The newest round owns the exact ``max == NNN`` head; it retires to
        # a ``>=`` floor once its successor lands. Retired to a floor when
        # r292 landed.
        self.assertGreaterEqual(max(_since_ints()), 291)

    def test_catalog_grew_to_142(self):
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 142)

    def test_recent_window_is_112(self):
        recent = [n for n in _since_ints() if n >= 170]
        self.assertGreaterEqual(len(recent), 112)


if __name__ == "__main__":
    unittest.main()
