# -*- coding: utf-8 -*-
"""r323 — the verification-depth fact agrees its noun with the count.

``observations`` surfaces a shallow-verification fact on every seam::

    found.append("Verification depth is shallow (%d unique verifier "
                 "name(s)); ...")

The lazy ``(s)`` idiom never chooses a noun, so a ledger verified by
exactly one name read "1 unique verifier name(s)" — the wrong noun for a
count of one. It is the r281-r291 singular/plural family, this time on a
DETECTOR FACT, the same surface class as r288's ledger-stagnation fact
and r290's stderr warning.

The guard is ``vd <= 1 and first_verified_val is not None``, and
``verification_depth`` returns the number of distinct verifiers in the
STALL_RUN window, so the fact fires only at 0 or 1: 0 fires when the
window has verified rows whose verifier fields are all blank, 1 fires
when one name carries the whole window, and 2+ never reaches the branch.

Single chokepoint: the fact is one string appended to ``found``, and
``found`` is what the text face prints (``· <fact>``), what
``seam --json`` ships as ``facts``, and what an in-process caller reads —
so agreeing the string once agrees every face by construction (the
r254/r259 precedent). "name" pluralizes regularly, so the fix uses the
same ``"" if n == 1 else "s"`` idiom r281 (``--domains``) and r283
(``--span``) use rather than a stem-swap chokepoint.

Probe (before the fix): a STALL_RUN-sized ledger with ``verified=1`` and
verifier ``"alice"`` printed
'· Verification depth is shallow (1 unique verifier name(s))' on the
seam text face and the identical string in ``seam --dry-run --json``
``facts``. After the fix the same runs read "1 unique verifier name".
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _controller_helper import invoke_cli, run_controller  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "mindseam", "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import mindseam  # noqa: E402


def build_history(specs, base_t=1000, step=100):
    """Full history rows for a list of partial row specs.

    Each spec overrides one or more row fields; everything else takes a
    neutral default. ``next`` is deliberately a repeating action so the
    window reaches the STALL_RUN seam count without the next-action
    fact masking the one under test.
    """
    out = []
    for i, spec in enumerate(specs):
        row = {
            "t": base_t + i * step,
            "next": "build: step",
            "msg": "m%d" % i,
            "verified": 0,
            "open": 0,
            "risk": "",
            "marker": "",
            "confidence": "strong",
            "outcome": "",
            "error": "",
            "verifier": "",
        }
        row.update(spec)
        out.append(row)
    return out


def read_ledger_book(ws=None):
    """Read the ledger book the way the controller does.

    ``ws`` defaults to the current directory, which is where the
    in-process controller reads its workspace from.
    """
    prev = os.getcwd()
    try:
        if ws:
            os.chdir(ws)
        return mindseam.read_ledger()
    finally:
        os.chdir(prev)


class FreshWorkspaceMixin:
    """A temp workspace per test, with the ledger already opened."""

    def setUp(self):
        self._workspaces = []
        self.ws = self._fresh()
        r = invoke_cli(self.ws, ["note", "--goal", "ship it",
                                 "--next", "verify it"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def tearDown(self):
        for ws in self._workspaces:
            shutil.rmtree(ws, ignore_errors=True)

    def _fresh(self):
        ws = tempfile.mkdtemp(prefix="r323_")
        self._workspaces.append(ws)
        return ws

    def _write_rows(self, rows):
        """Write ``rows`` as the workspace's .mindseam/history.json."""
        path = os.path.join(self.ws, ".mindseam", "history.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)


def _depth_line(facts):
    return next((f for f in facts if "Verification depth" in f), None)


def _rows(names):
    """A STALL_RUN-sized window whose verifier column is ``names``."""
    return build_history([{"verified": 1, "verifier": n} for n in names])


class VerificationDepthNounTests(FreshWorkspaceMixin, unittest.TestCase):
    """The noun the count renders with, at every reachable count."""

    def test_zero_verifiers_is_plural(self):
        facts = mindseam.observations(
            _rows([""] * mindseam.STALL_RUN), book=read_ledger_book())
        line = _depth_line(facts)
        self.assertIsNotNone(line, facts)
        self.assertIn("(0 unique verifier names)", line)

    def test_one_verifier_is_singular(self):
        facts = mindseam.observations(
            _rows(["alice"] * mindseam.STALL_RUN), book=read_ledger_book())
        line = _depth_line(facts)
        self.assertIsNotNone(line, facts)
        self.assertIn("(1 unique verifier name)", line)
        self.assertNotIn("name(s)", line)

    def test_two_verifiers_never_reach_the_fact(self):
        # The guard is vd <= 1, so a two-name window does not fire this
        # fact at all — the plural branch above one is unreachable.
        names = (["alice", "bob"] * mindseam.STALL_RUN)[:mindseam.STALL_RUN]
        self.assertEqual(len(set(names)), 2)
        facts = mindseam.observations(
            _rows(names), book=read_ledger_book())
        self.assertIsNone(_depth_line(facts), facts)

    def test_lazy_plural_idiom_is_gone(self):
        for names in ([""] * mindseam.STALL_RUN,
                      ["alice"] * mindseam.STALL_RUN):
            facts = mindseam.observations(
                _rows(names), book=read_ledger_book())
            line = _depth_line(facts)
            self.assertIsNotNone(line, facts)
            self.assertNotIn("name(s)", line)

    def test_zero_window_still_quotes_its_real_number(self):
        # The r58 intent survives: the fact reports the number it
        # measured rather than a hardcoded 1.
        rows = _rows([""] * mindseam.STALL_RUN)
        self.assertEqual(mindseam.verification_depth(rows), 0)
        facts = mindseam.observations(rows, book=read_ledger_book())
        line = _depth_line(facts)
        self.assertIsNotNone(line, facts)
        self.assertIn("0 unique verifier", line)
        self.assertNotIn("1 unique verifier", line)

    def test_windows_shorter_than_stall_run_stay_silent(self):
        # verification_depth returns 0 below STALL_RUN, but observations
        # short-circuits first, so no fact renders.
        rows = _rows(["alice", "alice"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            mindseam.observations(rows, book=read_ledger_book()), [])


class FacesAgreeTests(FreshWorkspaceMixin, unittest.TestCase):
    """One chokepoint: the seam text face and the JSON facts array."""

    def test_text_face_and_json_facts_carry_the_same_string(self):
        names = ["alice"] * mindseam.STALL_RUN
        self._write_rows(_rows(names))

        # --quiet prints the bare fact lines, so the string it emits is
        # the one the --json facts array carries.
        text = run_controller(self.ws, "seam", "--quiet", "--dry-run")
        self.assertEqual(text.returncode, 0, text.stdout + text.stderr)
        text_line = next((ln.strip() for ln in text.stdout.splitlines()
                          if "Verification depth" in ln), None)
        self.assertIsNotNone(text_line, text.stdout)
        self.assertIn("1 unique verifier name", text_line)
        self.assertNotIn("name(s)", text_line)

        js = run_controller(self.ws, "seam", "--dry-run", "--json")
        self.assertEqual(js.returncode, 0, js.stdout + js.stderr)
        payload = json.loads(js.stdout)
        json_fact = next((f for f in payload["facts"]
                          if "Verification depth" in f), None)
        self.assertIsNotNone(json_fact, payload["facts"])
        self.assertEqual(json_fact, text_line)

    def test_non_quiet_bullet_face_agrees_with_json(self):
        # The non-quiet seam face prefixes each fact with "· "; the JSON
        # facts array carries the same string unprefixed.
        names = ["alice"] * mindseam.STALL_RUN
        self._write_rows(_rows(names))
        text = run_controller(self.ws, "seam", "--dry-run")
        self.assertEqual(text.returncode, 0, text.stdout + text.stderr)
        bullet = next((ln.strip() for ln in text.stdout.splitlines()
                       if "Verification depth" in ln), None)
        self.assertIsNotNone(bullet, text.stdout)
        self.assertTrue(bullet.startswith("\u00b7 "), bullet)
        bare = bullet[len("\u00b7 "):]

        js = run_controller(self.ws, "seam", "--dry-run", "--json")
        payload = json.loads(js.stdout)
        self.assertIn(bare, payload["facts"])

    def test_zero_case_agrees_across_faces(self):
        self._write_rows(_rows([""] * mindseam.STALL_RUN))
        text = run_controller(self.ws, "seam", "--quiet", "--dry-run")
        self.assertEqual(text.returncode, 0, text.stdout + text.stderr)
        self.assertIn("0 unique verifier names", text.stdout)
        self.assertNotIn("name(s)", text.stdout)

        js = run_controller(self.ws, "seam", "--dry-run", "--json")
        self.assertEqual(js.returncode, 0, js.stdout + js.stderr)
        payload = json.loads(js.stdout)
        self.assertTrue(any("0 unique verifier names)" in f
                            for f in payload["facts"]))

    def test_in_process_facts_match_the_cli_faces(self):
        rows = _rows(["alice"] * mindseam.STALL_RUN)
        self._write_rows(rows)
        facts = mindseam.observations(rows, book=read_ledger_book())
        cli = run_controller(self.ws, "seam", "--quiet", "--dry-run")
        self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)
        self.assertIn("1 unique verifier name", cli.stdout)
        self.assertTrue(any("1 unique verifier name)" in f for f in facts))

    def test_sibling_facts_are_untouched(self):
        # The rest of the fact list is byte-identical: only the one
        # verification-depth sentence changed.
        rows = _rows(["alice"] * mindseam.STALL_RUN)
        facts = mindseam.observations(rows, book=read_ledger_book())
        depth = _depth_line(facts)
        self.assertIsNotNone(depth, facts)
        others = [f for f in facts if f != depth]
        self.assertTrue(others, facts)
        for f in others:
            self.assertNotIn("name(s)", f)


class GuardAndScopeTests(FreshWorkspaceMixin, unittest.TestCase):
    """The branch's own guard, and the surfaces the fix does NOT touch."""

    def test_guard_needs_a_verified_row(self):
        # verified all zero -> first_verified_val is None -> no fact.
        rows = build_history([{"verified": 0, "verifier": "alice"}] *
                             mindseam.STALL_RUN)
        facts = mindseam.observations(rows, book=read_ledger_book())
        self.assertIsNone(_depth_line(facts), facts)

    def test_helper_itself_is_unchanged(self):
        # verification_depth counts distinct names; only the wording
        # layer changed.
        rows = build_history([{"verified": 1, "verifier": "a"},
                              {"verified": 1, "verifier": "b"},
                              {"verified": 1, "verifier": "a"}])
        self.assertEqual(mindseam.verification_depth(rows), 2)
        blank = build_history([{"verified": 1, "verifier": ""}] * 3)
        self.assertEqual(mindseam.verification_depth(blank), 0)

    def test_health_reason_wording_unchanged(self):
        # The score layer renders the same condition as a reason list
        # with no count noun; r323 must not move it.
        rows = _rows(["alice"] * mindseam.STALL_RUN)
        result = mindseam.session_health_score(rows, book=read_ledger_book())
        reasons = getattr(result, "reasons", result)
        self.assertIn("shallow verification depth -5", reasons)


class CatalogPinTests(unittest.TestCase):

    def _since_ints(self):
        out = []
        for e in mindseam._FEATURE_CATALOG:
            since = e.get("since")
            if isinstance(since, str) and since.startswith("r"):
                try:
                    out.append(int(since.lstrip("r")))
                except ValueError:
                    pass
        return out

    def test_entry_present_since_r323_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "verification-depth-verifier-noun"),
                     None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r323")
        self.assertTrue(entry["default"])

    def test_r323_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 323)


if __name__ == "__main__":
    unittest.main()
