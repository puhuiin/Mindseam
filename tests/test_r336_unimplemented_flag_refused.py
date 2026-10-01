# -*- coding: utf-8 -*-
"""r336 — a registered flag that nothing reads recorded nothing.

Found by an AST sweep: collect every ``add_argument`` dest, then collect
every dest actually READ (``args.X``, ``getattr(args, "X")``). One dest
was registered and never read anywhere — ``note --memory``.

It has never been read in any commit (``git log -S'args.memory'`` is
empty), there is no Memory section in the ledger — ``SECTIONS`` is the
five that ``info --list-fields`` documents — and no test drives it. So

    note --memory "a durable fact to remember"

exited 0 having recorded nothing: the ledger was byte-identical
afterwards. r327 called this the write path's lie — the caller believes
a durable fact is in the ledger and it is not — and r327's own guard
even listed ``--memory`` in the single-use table, so a *repeated*
``--memory`` was refused while a single one was silently discarded.

Live before-fix:

    note --memory "a durable fact"  -> rc 0, ledger unchanged
    note --memory a --memory b      -> rc 2, "was given 2 times"

The fix REFUSES the flag rather than implementing it. Adding a sixth
ledger section is a schema change (``read_ledger`` / ``write_ledger`` /
``validate_book`` / every face / the untrusted echo surface) — that is a
feature, and the honest minimal fix for a flag that does nothing is to
say so instead of inventing one. The refusal is the r188/r205 idiom:
never accept an instruction you do not carry out.

Scope: ``mode_note`` only. The flag stays registered (removing it would
turn ``--memory`` into an argparse error with no explanation), the
r327 repetition refusal still fires first, and every other note flag is
untouched — the same probe confirms each one changes something.
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
        ws = tempfile.mkdtemp(prefix="r336_")
        self._workspaces.append(ws)
        return ws

    def _snapshot(self):
        """Every artefact a note could touch, as bytes."""
        out = {}
        base = os.path.join(self.ws, ".mindseam")
        if os.path.isdir(base):
            for name in sorted(os.listdir(base)):
                path = os.path.join(base, name)
                if os.path.isfile(path):
                    with open(path, "rb") as fh:
                        out[name] = fh.read()
        return out


class MemoryRefusalTests(_Base):
    """--memory must refuse, not silently record nothing."""

    def test_memory_is_refused(self):
        r = run_controller(self.ws, "note", "--memory", "a durable fact")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --memory is not implemented", r.stderr)

    def test_refusal_goes_to_stderr_with_empty_stdout(self):
        r = run_controller(self.ws, "note", "--memory", "a fact")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertTrue(r.stderr.strip())

    def test_nothing_is_written(self):
        before = self._snapshot()
        r = run_controller(self.ws, "note", "--memory", "a durable fact")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self._snapshot(), before,
                         "--memory must not touch the ledger")

    def test_the_refusal_explains_where_to_put_the_fact(self):
        r = run_controller(self.ws, "note", "--memory", "a fact")
        blob = r.stderr
        self.assertIn("no Memory section", blob)
        self.assertIn("--marker", blob)
        self.assertIn("--check", blob)

    def test_repetition_refusal_still_fires_first(self):
        # r327's guard runs before the new refusal, so the message a
        # repeated call gets is still the repetition one.
        r = run_controller(self.ws, "note", "--memory", "a", "--memory", "b")
        self.assertEqual(r.returncode, 2)
        self.assertIn("was given 2 times", r.stderr)

    def test_memory_with_another_edit_still_refuses(self):
        # A mixed call must not apply the other edit and drop --memory.
        before = self._snapshot()
        r = run_controller(self.ws, "note", "--goal", "a new goal",
                           "--memory", "a fact")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--memory is not implemented", r.stderr)
        self.assertEqual(self._snapshot(), before)

    def test_memory_through_stdin_is_refused_too(self):
        # The r199 stdin spec reaches the same mode_note.
        r = run_controller(self.ws, "note", "--from-stdin",
                           stdin='--memory "a durable fact"')
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--memory is not implemented", r.stderr)


class OtherNoteFlagsStillWorkTests(_Base):
    """The refusal is narrow: every other write flag still records."""

    def test_marker_still_records(self):
        r = run_controller(self.ws, "note", "--marker", "OPEN")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        meta = os.path.join(self.ws, ".mindseam", "metacognition.json")
        self.assertTrue(os.path.exists(meta))
        with open(meta, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["marker"], "OPEN")

    def test_goal_and_next_still_record(self):
        r = run_controller(self.ws, "note", "--goal", "new goal")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Goal:     new goal", r.stdout)

    def test_check_still_records(self):
        r = run_controller(self.ws, "note", "--check", "what holds",
                           "--by", "brute force, n <= 6")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        prev = os.getcwd()
        try:
            os.chdir(self.ws)
            verified = mindseam.read_ledger()["Verified"]
        finally:
            os.chdir(prev)
        self.assertTrue(verified)

    def test_memory_is_not_a_ledger_section(self):
        # The reason the flag cannot simply be implemented by writing:
        # the schema has no place for it.
        self.assertEqual(mindseam.SECTIONS,
                         ("Goal", "Core", "Verified", "Open", "Next"))
        self.assertNotIn("Memory", mindseam.SECTIONS)


class RegisteredDestSweepTests(unittest.TestCase):
    """No flag may be registered and never read."""

    def test_every_registered_dest_is_read(self):
        import ast
        src = open(os.path.join(SCRIPTS, "mindseam.py"),
                   encoding="utf-8").read()
        tree = ast.parse(src)
        dests = {}
        for node in ast.walk(tree):
            if type(node).__name__ != "Call":
                continue
            func = node.func
            if not (type(func).__name__ == "Attribute"
                    and func.attr == "add_argument"):
                continue
            flags = [a.value for a in node.args
                     if type(a).__name__ == "Constant"
                     and isinstance(a.value, str)]
            if not flags:
                continue
            dest = None
            for kw in node.keywords:
                if (kw.arg == "dest"
                        and type(kw.value).__name__ == "Constant"):
                    dest = kw.value.value
            if dest is None:
                longs = [x for x in flags if x.startswith("--")]
                if not longs:
                    continue
                dest = longs[0].lstrip("-").replace("-", "_")
            dests[dest] = flags
        reads = set()
        for node in ast.walk(tree):
            if type(node).__name__ == "Attribute":
                v = node.value
                if (type(v).__name__ == "Name"
                        and v.id in ("args", "ns", "spec", "namespace")):
                    reads.add(node.attr)
            if type(node).__name__ == "Call":
                f = node.func
                if (type(f).__name__ == "Name" and f.id == "getattr"
                        and len(node.args) >= 2
                        and type(node.args[0]).__name__ == "Name"
                        and node.args[0].id in ("args", "ns", "spec",
                                                "namespace")
                        and type(node.args[1]).__name__ == "Constant"):
                    reads.add(node.args[1].value)
        unread = sorted(d for d in dests if d not in reads)
        self.assertEqual(unread, [],
                         "registered but never read: %s" % unread)


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

    def test_entry_present_since_r336_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "unimplemented-flag-refused"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r336")
        self.assertTrue(entry["default"])

    def test_r336_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 336)


if __name__ == "__main__":
    unittest.main()
