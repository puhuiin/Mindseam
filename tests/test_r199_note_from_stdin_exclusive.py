# -*- coding: utf-8 -*-
"""Round 199 guards: note --from-stdin is exclusive with argv edit flags,
and the r174 surface gains its first direct coverage.

``note --from-stdin`` (r174) re-parses a stdin payload through the note
subparser *instead of* the argv spec — the dispatch replaces the argv
namespace wholesale. A call like ``note --goal "new" --from-stdin``
therefore ran to exit 0 with the argv ``--goal`` silently dropped and
the old goal still on the ledger: the caller believes both edits
applied, the ledger disagrees. Same shape as r188 (``audit --at`` ×
window flags) and r198 (renderer pairs): branch-exclusive code paths
plus silent drops.

r199 refuses the combination before stdin is even read, naming every
argv flag that would vanish; ``--dry-run`` composes (it is a mode, not
an edit). The round also lands the base coverage the flag never had —
a valid stdin spec applies its edits, an empty or unparseable spec is
refused, and ``--settled-by`` without ``--open`` keeps its own
refusal.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam
from _controller_helper import invoke_cli


class FromStdinExclusivityTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _goal(self):
        return mindseam.read_ledger().get("Goal")

    def test_argv_flag_alongside_stdin_is_refused(self):
        r = invoke_cli(self.workspace,
                       ["note", "--goal", "ARGV GOAL", "--from-stdin"],
                       stdin='--next "dom: b"\n')
        self.assertEqual(r.returncode, 2)
        self.assertIn("would be silently dropped", r.stderr)
        self.assertIn("--goal", r.stderr)
        self.assertEqual(self._goal(), ["g"],
                         "the ledger must be untouched by the refusal")

    def test_refusal_names_every_dropped_flag(self):
        r = invoke_cli(self.workspace,
                       ["note", "--goal", "x", "--marker", "DONE",
                        "--from-stdin"],
                       stdin='--next "dom: b"\n')
        self.assertEqual(r.returncode, 2)
        self.assertIn("--goal", r.stderr)
        self.assertIn("--marker", r.stderr)

    def test_dry_run_composes_with_stdin(self):
        # --dry-run is a mode, not an edit: it composes with the stdin
        # spec, and the preview writes nothing. The ledger is opened
        # with a real note first so the read-time repair of the stub
        # header is not mistaken for a dry-run write.
        r = invoke_cli(self.workspace,
                       ["note", "--goal", "open", "--next", "dom: open"])
        self.assertEqual(r.returncode, 0, r.stderr)
        before = (self.ledger / "WORKSPACE.md").read_bytes()
        r = invoke_cli(self.workspace,
                       ["note", "--dry-run", "--from-stdin"],
                       stdin='--goal "preview only"\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.ledger / "WORKSPACE.md").read_bytes(),
                         before)

    def test_valid_stdin_spec_applies(self):
        r = invoke_cli(self.workspace,
                       ["note", "--from-stdin"],
                       stdin='--goal "stdin goal" --next "dom: c"\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        book = mindseam.read_ledger()
        self.assertEqual(book.get("Goal"), ["stdin goal"])
        self.assertEqual(book.get("Next"), ["dom: c"])

    def test_empty_stdin_is_refused(self):
        r = invoke_cli(self.workspace, ["note", "--from-stdin"],
                       stdin="   \n")
        self.assertEqual(r.returncode, 2)
        self.assertIn("read no flags from stdin", r.stderr)

    def test_unparseable_stdin_is_refused(self):
        r = invoke_cli(self.workspace, ["note", "--from-stdin"],
                       stdin="--bogus x\n")
        self.assertEqual(r.returncode, 2)
        self.assertIn("failed to parse", r.stderr)

    def test_settled_by_alone_keeps_its_refusal(self):
        # The probe finding: --settled-by requires --open, and the
        # refusal fires before any write.
        r = invoke_cli(self.workspace,
                       ["note", "--settled-by", "test suite"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("requires --open", r.stderr)
        self.assertEqual(self._goal(), ["g"])

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("note-from-stdin-exclusive", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "note-from-stdin-exclusive")
        self.assertEqual(entry["since"], "r199")
        self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
