# -*- coding: utf-8 -*-
"""r334 — the four commands r333 left still discarding the read reasons.

r333 fixed ``mode_info``, whose ``--check`` gate was passing on a
history it could not read. It deliberately scoped the fix to ``info``
and named the rest as carriers. This round closes them.

Remaining before-fix, on a workspace whose ``history.json`` is corrupt
JSON (a directory or a non-list root behave the same), every one at
exit 0 with no signal:

    ship        -> "clean — the outgoing register holds."
                   (its completion gate reads the most-recent row, so a
                    failed read drops every marker/settle observation)
    history     -> "history (0 entries)" / --count "0"
    skillbook   -> "No skillbook yet — run a seam to start harvesting"
                   (false: the patterns may well exist)
    discover    -> "No history yet — run a seam and the domain map
                   appears." (false, and the r280 lie one layer out)
    audit       -> "Lean already. Ship." at exit 0, and --strict exited 0
                   too — the SECOND documented gate passing on a file it
                   could not read.

The fix adds one shared helper pair and wires it in:

``history_read_failed(hist, hist_repairs)`` names the state — an EMPTY
history whose emptiness came from a failed read, as opposed to a
workspace that has never run a seam. ``history_read_warning(reasons)``
renders the one-line stderr warning, the r290/r1015 idiom for an I/O
problem, and returns None for a clean read so nothing is emitted.

Per command: ``ship``/``history``/``skillbook``/``discover`` print the
warning to stderr, and the two commands with an empty-state message stop
claiming a fresh start — "No skillbook available — history.json could
not be read" / "No domain map available — ...".

``audit`` is different in kind, and the difference is the round's real
finding. An audit IS a statement about the history, so a history it
cannot read is a REFUSAL (exit 2, the r188/r205 CANNOT idiom), not a
finding. The first cut made it a finding and was wrong: a finding is a
projection, and ``--tag delete`` drops projections — so
``audit --strict --tag delete`` still exited 0 on the unreadable file.
A gate a projection can switch off is not a gate. The refusal fires
before the tag filter and before any finding is computed.

Every healthy case is unchanged: no repair reasons means no warning,
``audit --strict`` still exits 1 on real findings, and the fresh
workspace keeps its original empty-state messages (pinned).
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

# 12 rows with a blank-next front half and a repeated action back half, so
# a HEALTHY audit has shrink findings and its --strict exits 1.
ROWS = [{"t": 1000 + i * 100, "next": "" if i < 6 else "build: same",
         "msg": "m", "verified": 0, "open": 0, "risk": "high",
         "marker": "M", "confidence": "strong", "outcome": "ok",
         "error": "secrets: rotate", "verifier": "a", "extra_steps": 1}
        for i in range(12)]


class _Base(unittest.TestCase):
    def setUp(self):
        self._workspaces = []
        self.ws = self._fresh()
        invoke_cli(self.ws, ["note", "--goal", "ship it",
                             "--next", "verify it"])
        self._write_rows(ROWS)

    def tearDown(self):
        for ws in self._workspaces:
            shutil.rmtree(ws, ignore_errors=True)

    def _fresh(self):
        ws = tempfile.mkdtemp(prefix="r334_")
        self._workspaces.append(ws)
        return ws

    def _history_path(self):
        return os.path.join(self.ws, ".mindseam", "history.json")

    def _write_rows(self, rows):
        path = self._history_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)

    def _break_history(self, how="corrupt"):
        path = self._history_path()
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
        if how == "corrupt":
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{not json")
        elif how == "non-list-root":
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"a": 1}')
        elif how == "directory":
            os.makedirs(path)
        else:
            raise ValueError(how)

    def _run(self, *args, **kw):
        return run_controller(self.ws, *args, **kw)


class ShipDisclosureTests(_Base):
    def test_ship_warns_on_an_unreadable_history(self):
        self._break_history()
        r = self._run("ship", "-", stdin="draft.")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("could not be read", r.stderr)

    def test_ship_does_not_warn_on_a_healthy_history(self):
        r = self._run("ship", "-", stdin="draft.")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("could not be read", r.stderr)


class HistoryDisclosureTests(_Base):
    def test_count_warns_on_an_unreadable_history(self):
        self._break_history()
        r = self._run("history", "--count")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("could not be read", r.stderr)

    def test_table_warns_on_an_unreadable_history(self):
        self._break_history()
        r = self._run("history")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("could not be read", r.stderr)

    def test_json_face_warns_too(self):
        self._break_history()
        r = self._run("history", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("could not be read", r.stderr)
        json.loads(r.stdout)  # the payload is still valid JSON

    def test_healthy_history_does_not_warn(self):
        r = self._run("history", "--count")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("could not be read", r.stderr)
        self.assertEqual(r.stdout.strip(), "12")


class SkillbookDisclosureTests(_Base):
    def test_skillbook_does_not_claim_a_fresh_start(self):
        self._break_history()
        r = self._run("skillbook")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("could not be read", r.stderr)
        self.assertIn("could not be read", r.stdout)
        self.assertNotIn("No skillbook yet", r.stdout)

    def test_fresh_workspace_keeps_the_original_message(self):
        os.remove(self._history_path())
        r = self._run("skillbook")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("No skillbook yet", r.stdout)

    def test_healthy_skillbook_is_unchanged(self):
        r = self._run("skillbook")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("could not be read", r.stderr)


class DiscoverDisclosureTests(_Base):
    def test_discover_does_not_claim_no_history(self):
        self._break_history()
        r = self._run("discover")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("could not be read", r.stderr)
        self.assertIn("could not be read", r.stdout)
        self.assertNotIn("No history yet", r.stdout)

    def test_fresh_workspace_keeps_the_original_message(self):
        os.remove(self._history_path())
        r = self._run("discover")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("No history yet", r.stdout)

    def test_healthy_discover_is_unchanged(self):
        r = self._run("discover")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("could not be read", r.stderr)


class AuditGateTests(_Base):
    """audit is a statement about the history: a failed read refuses."""

    def test_audit_refuses_on_an_unreadable_history(self):
        for how in ("corrupt", "non-list-root", "directory"):
            with self.subTest(how=how):
                self._break_history(how)
                r = self._run("audit")
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("CANNOT:", r.stderr)

    def test_strict_also_refuses(self):
        self._break_history()
        r = self._run("audit", "--strict")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_json_face_refuses_too(self):
        self._break_history()
        r = self._run("audit", "--json")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")

    def test_the_refusal_survives_a_tag_projection(self):
        # The finding-shaped first cut failed here: --tag delete drops
        # projections, so the gate could be switched off.
        self._break_history()
        r = self._run("audit", "--strict", "--tag", "delete")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT:", r.stderr)

    def test_refusal_precedes_any_finding(self):
        self._break_history()
        r = self._run("audit", "--json")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_healthy_audit_still_gates_on_real_findings(self):
        r = self._run("audit", "--strict")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("could not be read", r.stderr)

    def test_healthy_audit_report_only_is_zero(self):
        r = self._run("audit")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class HelperContractTests(unittest.TestCase):
    def test_read_failed_only_for_empty_plus_reasons(self):
        self.assertTrue(mindseam.history_read_failed([], ["x"]))
        self.assertFalse(mindseam.history_read_failed([{"t": 1}], ["x"]))
        self.assertFalse(mindseam.history_read_failed([], []))
        self.assertFalse(mindseam.history_read_failed([], None))

    def test_read_warning_is_none_when_clean(self):
        self.assertIsNone(mindseam.history_read_warning([]))
        self.assertIsNone(mindseam.history_read_warning(None))

    def test_read_warning_joins_every_reason(self):
        w = mindseam.history_read_warning(["one", "two"])
        self.assertIn("one", w)
        self.assertIn("two", w)
        self.assertTrue(w.startswith("WARNING:"))

    def test_no_caller_subscripts_read_history(self):
        # An AST scan, not a text grep: a COMMENT mentioning the old
        # shape must not fail the guard, and a real ``read_history()[0]``
        # must. Every caller must unpack the triple so it cannot drop
        # the reasons.
        import ast
        src = open(os.path.join(SCRIPTS, "mindseam.py"),
                   encoding="utf-8").read()
        tree = ast.parse(src)
        offenders = []
        for node in ast.walk(tree):
            if type(node).__name__ != "Subscript":
                continue
            value = node.value
            if (type(value).__name__ == "Call"
                    and type(value.func).__name__ == "Name"
                    and value.func.id == "read_history"):
                offenders.append(node.lineno)
        self.assertEqual(offenders, [],
                         "read_history()[...] discards the repair reasons "
                         "at line(s) %s" % offenders)

    def test_the_five_commands_name_the_reasons(self):
        import ast
        src = open(os.path.join(SCRIPTS, "mindseam.py"),
                   encoding="utf-8").read()
        tree = ast.parse(src)
        owners = {}
        for node in ast.walk(tree):
            if type(node).__name__ == "FunctionDef":
                owners[node.name] = ast.dump(node)
        for name in ("mode_ship", "mode_history", "mode_skillbook",
                     "mode_discover", "mode_audit"):
            self.assertIn("hist_repairs", owners.get(name, ""), name)


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

    def test_entry_present_since_r334_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "read-failure-disclosed-everywhere"),
                     None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r334")
        self.assertTrue(entry["default"])

    def test_r334_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 334)


if __name__ == "__main__":
    unittest.main()
