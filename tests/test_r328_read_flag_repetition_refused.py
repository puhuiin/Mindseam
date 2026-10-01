# -*- coding: utf-8 -*-
"""r328 — the read-path flags stop last-winning, and one hook covers all.

r325/r326/r327 closed the last-wins family three times over: history's
text filters, then history's selectors and audit's window, then note's
ledger fields and seam's message. Each round named the rest as the
carriers. This round finishes the family and consolidates its
mechanism.

Remaining live before-fix, every one at exit 0 with only the LAST value
applied::

    seam --format A --format B          -> renders B
    resume --format A --format B        -> renders B
    ship --format A --format B          -> renders B
    info --format A --format B          -> renders B
    skillbook --format A --format B     -> renders B
    discover --format A --format B      -> renders B
    audit --format A --format B         -> renders B
    info --field A --field B            -> shows B
    info --index-since A --index-since B -> window from B
    info --index-until A --index-until B -> window to B
    info --audit-baseline A --B         -> baseline B
    audit --intensity lite --intensity full   -> full
    audit --tag delete --tag shrink     -> shrink
    audit --at 1 --at 2                 -> audits seam 2
    audit --baseline A --B              -> baseline B
    audit --baseline-write A --B        -> writes B
    audit --explain delete --explain shrink -> explains shrink

None of these RECORDS anything wrongly (that was r327's write path,
which is why it went first), but each one answers a different question
than the caller asked, and there is no signal that it did.

The fix extends r326's shared table to the read-path commands and moves
the refusal to ONE hook in ``main()``, immediately after the parse and
before the ledger is read. That placement is what makes the family
impossible to leave half-finished: a new subcommand inherits the guard
by adding a table entry, not by remembering a per-command call.

The three per-command hooks r325/r326/r327 added are removed as dead
code — the universal hook already unwrapped their dests — EXCEPT
``mode_note``'s, which is the one guard the universal hook cannot
cover: the r199 ``--from-stdin`` spec is parsed by a SECOND
``parse_args`` inside ``read_note_stdin_spec``, and ``mode_note``
receives that merged namespace. A repeated flag smuggled in through
stdin is caught only there.
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


class _Base(unittest.TestCase):
    def setUp(self):
        self._workspaces = []
        self.ws = self._fresh()
        invoke_cli(self.ws, ["note", "--goal", "ship it",
                             "--next", "verify it"])

    def tearDown(self):
        for ws in self._workspaces:
            shutil.rmtree(ws, ignore_errors=True)

    def _fresh(self):
        ws = tempfile.mkdtemp(prefix="r328_")
        self._workspaces.append(ws)
        return ws


READ_CASES = (
    (["seam", "--dry-run", "--format", "history_count",
      "--format", "ledger.goal"], "seam", "--format"),
    (["resume", "--format", "history_count", "--format", "ledger.goal"],
     "resume", "--format"),
    (["ship", "-", "--format", "gate", "--format", "exit"], "ship",
     "--format"),
    (["info", "--format", "version", "--format", "ledger.goal"], "info",
     "--format"),
    (["skillbook", "--format", "[0].kind", "--format", "[0].text"],
     "skillbook", "--format"),
    (["discover", "--format", "suggested_next", "--format", "domains"],
     "discover", "--format"),
    (["audit", "--format", "lean", "--format", "gate"], "audit",
     "--format"),
    (["info", "--json", "--field", "version", "--field", "ledger"],
     "info", "--field"),
    (["info", "--index", "--index-since", "r200", "--index-since", "r100"],
     "info", "--index-since"),
    (["info", "--index", "--index-until", "r200", "--index-until", "r300"],
     "info", "--index-until"),
    (["info", "--audit-baseline", "x.json", "--audit-baseline", "y.json"],
     "info", "--audit-baseline"),
    (["audit", "--intensity", "lite", "--intensity", "full"], "audit",
     "--intensity"),
    (["audit", "--tag", "delete", "--tag", "shrink"], "audit", "--tag"),
    (["audit", "--explain", "delete", "--explain", "shrink"], "audit",
     "--explain"),
    (["audit", "--baseline", "a.json", "--baseline", "b.json"], "audit",
     "--baseline"),
    (["audit", "--baseline-write", "a.json", "--baseline-write", "b.json"],
     "audit", "--baseline-write"),
)


class ReadPathRefusalTests(_Base):
    """Every read-path flag refuses a repetition."""

    def test_every_read_flag_refuses(self):
        for args, cmd, flag in READ_CASES:
            with self.subTest(flag=flag, cmd=cmd):
                stdin = "draft." if args[0] == "ship" else None
                r = run_controller(self.ws, *args, stdin=stdin)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("CANNOT: %s was given 2 times" % flag,
                              r.stderr)

    def test_refusal_names_both_values(self):
        r = run_controller(self.ws, "info", "--field", "version",
                           "--field", "ledger")
        self.assertEqual(r.returncode, 2)
        first = r.stderr.splitlines()[0]
        self.assertIn("'version'", first)
        self.assertIn("'ledger'", first)

    def test_refusal_guidance_names_the_harm(self):
        r = run_controller(self.ws, "audit", "--tag", "delete",
                           "--tag", "shrink")
        self.assertEqual(r.returncode, 2)
        self.assertIn("the findings you see are not the ones you asked for",
                      r.stderr)

    def test_at_two_repeats_is_refused_not_range_checked(self):
        # --at 1 --at 2 used to reach the range check (which refused for
        # an unrelated reason on an empty history); the repetition guard
        # fires first.
        r = run_controller(self.ws, "audit", "--at", "1", "--at", "2")
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT: --at was given 2 times", r.stderr)


class SingleReadCallUnchangedTests(_Base):
    """One value keeps every existing read contract byte-identical."""

    def test_format_faces_still_render(self):
        # An empty skillbook renders nothing and a clean ledger renders a
        # single-character gate value, so this pins rc==0 and the absence
        # of the repetition refusal rather than non-empty output.
        cases = (
            (["seam", "--dry-run", "--format", "history_count"], None),
            (["resume", "--format", "history_count"], None),
            (["info", "--format", "ledger.goal"], None),
            (["skillbook", "--format", "[0].kind"], None),
            (["discover", "--format", "suggested_next"], None),
            (["ship", "-", "--format", "gate"], "draft."),
            (["audit", "--format", "gate"], None),
        )
        for args, stdin in cases:
            with self.subTest(cmd=args[0]):
                r = run_controller(self.ws, *args, stdin=stdin)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertNotIn("was given 2 times", r.stderr)
                self.assertNotIn("Traceback", r.stderr)

    def test_format_faces_render_real_values(self):
        # A ledger with content, so the faces have something to render.
        self._write_rows()
        r = run_controller(self.ws, "seam", "--dry-run", "--format",
                           "history_count")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "3")

    def _write_rows(self):
        rows = [{"t": 1000 + i * 100, "next": "build: step %d" % i,
                 "msg": "m%d" % i, "verified": i, "open": i, "risk": "",
                 "marker": "", "confidence": "strong", "outcome": "ok",
                 "error": "", "verifier": "alice"} for i in range(3)]
        path = os.path.join(self.ws, ".mindseam", "history.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)

    def test_multi_path_format_still_renders_all_paths(self):
        # One --format takes a comma-separated list of paths; that is the
        # documented repeat mechanism and must keep working.
        r = run_controller(self.ws, "seam", "--dry-run", "--format",
                           "history_count,ledger.goal")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 2)

    def test_info_field_and_index_window_still_work(self):
        r = run_controller(self.ws, "info", "--json", "--field", "version")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run_controller(self.ws, "info", "--index", "--json",
                           "--index-since", "r200", "--index-until", "r300")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        entries = json.loads(r.stdout)["index"]
        self.assertTrue(entries)

    def test_audit_flags_still_work_singly(self):
        for args in (["audit", "--intensity", "lite"],
                     ["audit", "--tag", "delete"],
                     ["audit", "--explain", "delete"]):
            with self.subTest(args=args):
                r = run_controller(self.ws, *args)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_audit_at_needs_a_history(self):
        # --at indexes rows, so on a ledger with no history it refuses for
        # the range reason — not the repetition reason.
        r = run_controller(self.ws, "audit", "--at", "1")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("out of range", r.stderr)
        self.assertNotIn("was given 2 times", r.stderr)

    def test_existing_composition_refusals_not_shadowed(self):
        # r202/r205/r222: the explain and quiet/json faces refuse to
        # compose. The repetition guard must not replace them.
        r = run_controller(self.ws, "info", "--field", "version",
                           "--index")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--field", r.stderr)
        r = run_controller(self.ws, "seam", "--quiet", "--json")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("mutually exclusive", r.stderr)


class UniversalHookTests(_Base):
    """The one hook in main() covers every command's argv path."""

    def test_hook_sits_before_the_ledger_read(self):
        # A repeated flag is refused even in a workspace whose ledger
        # cannot be read, because the guard runs before read_ledger().
        path = os.path.join(self.ws, ".mindseam", "WORKSPACE.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not a ledger")
        r = run_controller(self.ws, "info", "--field", "a", "--field", "b")
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT: --field was given 2 times", r.stderr)

    def test_hook_covers_a_command_with_no_table_entry(self):
        # A command absent from the table simply has no single-use flags
        # to guard, and the hook must not crash on it.
        r = run_controller(self.ws, "resume")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_hook_unwraps_before_dispatch(self):
        # mode_seam reads format_path as a string; a list there raises.
        r = run_controller(self.ws, "seam", "--dry-run", "--format",
                           "history_count")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_history_refusal_still_precedes_keep(self):
        before = open(os.path.join(self.ws, ".mindseam", "history.json"),
                      encoding="utf-8").read() \
            if os.path.exists(os.path.join(self.ws, ".mindseam",
                                           "history.json")) else None
        r = run_controller(self.ws, "history", "--keep", "100", "--keep",
                           "0")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --keep was given 2 times", r.stderr)
        after = open(os.path.join(self.ws, ".mindseam", "history.json"),
                     encoding="utf-8").read() \
            if os.path.exists(os.path.join(self.ws, ".mindseam",
                                           "history.json")) else None
        self.assertEqual(before, after)

    def test_note_refusal_still_precedes_a_write(self):
        before = open(os.path.join(self.ws, ".mindseam", "WORKSPACE.md"),
                      encoding="utf-8").read()
        r = run_controller(self.ws, "note", "--goal", "a", "--goal", "b")
        self.assertEqual(r.returncode, 2)
        after = open(os.path.join(self.ws, ".mindseam", "WORKSPACE.md"),
                     encoding="utf-8").read()
        self.assertEqual(before, after)


class StdinPathTests(_Base):
    """The r199 stdin spec is parsed by a second parse_args the universal
    hook never sees, so mode_note keeps its own call."""

    def test_repeated_flag_through_stdin_is_refused(self):
        r = run_controller(self.ws, "note", "--from-stdin",
                           stdin='--goal "one" --goal "two" --next "n"')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --goal was given 2 times", r.stderr)

    def test_repeated_open_through_stdin_is_refused(self):
        r = run_controller(self.ws, "note", "--from-stdin",
                           stdin='--open "Q1?" --open "Q2?"')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --open was given 2 times", r.stderr)

    def test_single_flags_through_stdin_still_work(self):
        r = run_controller(self.ws, "note", "--from-stdin", "--dry-run",
                           stdin='--goal "from stdin" --next "piped"')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("dry run", r.stdout)


class TableTests(unittest.TestCase):
    """The table now spans the whole tool."""

    def test_every_command_is_covered(self):
        self.assertEqual(set(mindseam._SINGLE_USE_FLAGS),
                         {"note", "seam", "history", "audit", "info",
                          "resume", "ship", "skillbook", "discover"})

    def test_read_path_commands_cover_their_format(self):
        for cmd in ("info", "resume", "ship", "skillbook", "discover",
                    "seam", "audit"):
            dests = {dest for _, dest, _
                     in mindseam._SINGLE_USE_FLAGS[cmd]}
            self.assertIn("format_path", dests, cmd)

    def test_info_covers_its_own_flags(self):
        dests = {dest for _, dest, _
                 in mindseam._SINGLE_USE_FLAGS["info"]}
        self.assertEqual(dests, {"format_path", "field_path", "explain",
                                 "index_since", "index_until",
                                 "audit_baseline"})

    def test_history_and_note_tables_are_unchanged(self):
        # The earlier rounds' entries must not drift when a later one
        # extends the same table.
        self.assertEqual(len(mindseam._SINGLE_USE_FLAGS["history"]), 11)
        self.assertEqual(len(mindseam._SINGLE_USE_FLAGS["note"]), 16)

    def test_filter_is_deliberately_absent_everywhere(self):
        for cmd, specs in mindseam._SINGLE_USE_FLAGS.items():
            dests = {dest for _, dest, _ in specs}
            self.assertNotIn("filter", dests, cmd)

    def test_no_flag_appears_twice_in_one_command(self):
        for cmd, specs in mindseam._SINGLE_USE_FLAGS.items():
            flags = [flag for flag, _, _ in specs]
            self.assertEqual(len(flags), len(set(flags)), cmd)


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

    def test_entry_present_since_r328_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "read-flag-repetition-refused"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r328")
        self.assertTrue(entry["default"])

    def test_r328_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 328)


if __name__ == "__main__":
    unittest.main()
