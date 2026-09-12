# -*- coding: utf-8 -*-
"""Round 206 guards: every refusal prints to stderr.

The CANNOT family (audit/info/seam/history refusals since r156)
has always written refusals to stderr with exit 2. But three
older paths never got the memo: note's ``declined()`` helper
printed its NOT RECORDED lines to stdout, and four bare CANNOT
prints (audit intensity-off, ledger-unreadable, the note
cannot-write path, ship's unreadable/undecodable file) omitted
``file=sys.stderr``. The same command ran two failure
conventions — ``note --close 9`` exited 2 with an EMPTY stderr
while ``audit --at 99`` named its problem on stderr — so a host
reading stderr saw nothing and a host reading stdout mixed its
data with failures.

r206 moves every refusal to stderr. Exit codes and refusal text
are unchanged (the r115 NOT RECORDED voice and the two-line
message+fix shape survive byte-for-byte); only the stream moves.
Sixteen stdout pins across nine test files were advanced with
this change — the pinned contracts were about the refusal text,
which never changed.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from _controller_helper import invoke_cli

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _invoke(args, cwd, stdin=None):
    return invoke_cli(cwd, args, stdin=stdin)


class RefusalsOnStderrTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n?01 one\n\n## Next\nn\n", encoding="utf-8")
        rows = [{"t": i + 1, "next": "dom: step %d" % i,
                 "verified": i + 1, "open": 0} for i in range(3)]
        (self.ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _refused(self, *args, stdin=None):
        r = _invoke(list(args), self.workspace, stdin=stdin)
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        return r

    def test_note_declined_lines_land_on_stderr(self):
        r = self._refused("note", "--close", "9")
        self.assertIn("NOT RECORDED: no open question numbered 9",
                      r.stderr)
        self.assertIn("run `resume` to see the full list", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_note_marker_refusal_on_stderr(self):
        r = self._refused("note", "--next", "dom: b", "--marker", "   ")
        self.assertIn("NOT RECORDED", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_settled_by_refusal_on_stderr(self):
        r = self._refused("note", "--settled-by", "x")
        self.assertIn("requires --open", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_ledger_unreadable_on_stderr(self):
        (self.ledger / "WORKSPACE.md").write_bytes(b"\xff\xfe\x00\x80")
        r = self._refused("note", "--goal", "x")
        self.assertIn("ledger was unreadable", r.stderr)
        self.assertIn("repair or remove", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_ship_unreadable_file_on_stderr(self):
        r = self._refused("ship",
                          str(Path(self.workspace) / "no-such-file.md"))
        self.assertIn("CANNOT:", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_ship_undecodable_file_on_stderr(self):
        outgoing = Path(self.workspace) / "outgoing.txt"
        outgoing.write_bytes(b"\x81\x82\x83")
        r = self._refused("ship", str(outgoing))
        self.assertIn("cannot decode safely", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_audit_intensity_off_on_stderr(self):
        r = self._refused("audit", "--intensity", "off")
        self.assertIn("audit intensity is off", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_write_lock_refusal_on_stderr(self):
        (self.ledger / "write.lock").write_text(
            json.dumps({"pid": 999999, "t": 1}), encoding="utf-8")
        r = self._refused("note", "--goal", "x")
        self.assertIn("locked by another writer", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_cannot_family_still_on_stderr(self):
        # The rule r206 extended, not introduced: the newer CANNOT
        # refusals were already stderr — pin one here as the anchor.
        r = self._refused("audit", "--at", "99")
        self.assertIn("out of range", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_success_paths_still_stdout(self):
        # The stream split is the whole contract: data on stdout,
        # refusals on stderr. A passing note must leave stderr
        # empty and the report on stdout.
        r = _invoke(["note", "--goal", "new goal"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip())
        self.assertEqual(r.stderr, "")

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("refusals-on-stderr", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "refusals-on-stderr")
        self.assertEqual(entry["since"], "r206")
        self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
