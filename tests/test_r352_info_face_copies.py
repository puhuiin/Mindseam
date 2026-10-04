# -*- coding: utf-8 -*-
"""r352 -- the short-circuit-face set was hand-typed in three copies,
and all three had drifted the way r349's tag-list copy did.

The live set is seven flags: {--index, --version, --check, --memory,
--list-fields, --explain, --warnings-only}. Five predated r200; --explain
joined in r202 and --warnings-only in r205. Every copy written before
those two arrivals stayed at its snapshot:

  * ``info --index``'s argparse help promised exclusivity against four
    of the six other faces -- naming neither of the two newest;
  * SKILL.md and both READMEs copied that four-face list;
  * the r200 test's own FACES tuple kept the original five, so the
    round's pair-sweep covered 10 of the 21 pairs.

Live before the fix: ``info --index --warnings-only`` and
``info --index --explain info-memory`` refused with exit 2 while the
help a host reads -- the only place to discover the contract before
guessing -- described a CLI that accepts them.

The control case again proves this is a defect, not a style choice:
the dispatcher iterates one tuple and refuses every pair, so the
runtime was always right; only the copies understated it. The fix
renders the copies from the set (INFO_FACE_FLAGS) so the copy that
could go stale no longer exists, and this file guards both directions:
the help and each doc line must name exactly the faces the constant
names -- none missing, none orphaned -- and the live guard must refuse
every pair the constant forms, naming both, in constant order.
"""

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam
from _controller_helper import invoke_cli

FACES = tuple(flag for flag, _ in mindseam.INFO_FACE_FLAGS)
FACE_ARGS = {"--explain": ["info-memory"]}
OTHERS = mindseam.info_other_faces("--index")


class FaceSetShapeTests(unittest.TestCase):
    """The single source has the shape the copies were written to mirror."""

    def test_seven_unique_faces(self):
        self.assertEqual(len(FACES), 7)
        self.assertEqual(len(set(FACES)), 7)
        dests = [dest for _, dest in mindseam.INFO_FACE_FLAGS]
        self.assertEqual(len(set(dests)), 7)
        for flag, _ in mindseam.INFO_FACE_FLAGS:
            self.assertTrue(flag.startswith("--"), flag)

    def test_other_faces_render_six_without_the_excluded(self):
        names = OTHERS.split("/")
        self.assertEqual(names, [f for f in FACES if f != "--index"])
        self.assertNotIn("--index", names)
        # Excluding an unknown name keeps every face -- the helper
        # filters, it does not index, so a typo renders all seven.
        self.assertEqual(mindseam.info_other_faces("--bogus").split("/"),
                         list(FACES))


class HelpCopyTests(unittest.TestCase):
    """--index's argparse help must name exactly the other faces."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _flat_help(self):
        # argparse word-wraps help at terminal width and splits
        # hyphenated tokens mid-word (--list-\nfields), so compare
        # whitespace-free text.
        r = invoke_cli(self.workspace, ["info", "--help"])
        self.assertEqual(r.returncode, 0, r.stderr)
        return re.sub(r"\s+", "", r.stdout)

    def test_help_names_all_six_others(self):
        flat = self._flat_help()
        needle = "(%s)" % OTHERS
        self.assertIn(needle, flat)

    def test_help_has_no_stale_orphan_copy(self):
        # The stale snapshot: the four-face parenthetical that drifted.
        # A re-typed short list (orphaned faces silently dropped) can
        # never match the derived needle above, and the closed
        # parenthetical "(--version/--check/--memory/--list-fields)"
        # must no longer appear anywhere in the help.
        flat = self._flat_help()
        self.assertNotIn("(--version/--check/--memory/--list-fields)",
                         flat)


class DocsCopyTests(unittest.TestCase):
    """Each doc's --index line must name the same set the code has."""

    def _read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def _index_lines(self, text):
        return [ln for ln in text.splitlines() if "info --index" in ln
                and "index-since" not in ln and "index-until" not in ln]

    def test_skill_md_index_line(self):
        lines = self._index_lines(self._read("mindseam/SKILL.md"))
        self.assertTrue(lines, "no --index line in SKILL.md")
        needle = "(%s)" % OTHERS
        self.assertTrue(any(needle in ln for ln in lines),
                        "SKILL.md --index line does not name all six others")

    def test_readme_index_line(self):
        lines = self._index_lines(self._read("README.md"))
        self.assertTrue(lines)
        # README wraps each flag in backticks (house markdown style);
        # build the expectation from the constant rather than typing it.
        needle = "(" + "/".join("`%s`" % f for f in OTHERS.split("/")) + ")"
        self.assertTrue(any(needle in ln for ln in lines),
                        "README.md --index line does not name all six others")

    def test_readme_zh_index_line(self):
        # The zh doc wraps each flag in backticks inside full-width
        # parens; build the same derived expectation from the constant.
        lines = self._index_lines(self._read("README.zh-CN.md"))
        self.assertTrue(lines)
        needle = chr(0xFF08) + "/".join("`%s`" % f
                                        for f in OTHERS.split("/")) + chr(0xFF09)
        self.assertTrue(any(needle in ln for ln in lines),
                        "README.zh-CN.md --index line does not name all six")


class LiveSweepTests(unittest.TestCase):
    """The dispatcher iterates this very constant: every pair refuses."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        ledger = Path(self.workspace) / ".mindseam"
        ledger.mkdir(parents=True, exist_ok=True)
        (ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _run(self, *args):
        return invoke_cli(self.workspace, list(args))

    def test_all_twenty_one_pairs_refuse_in_constant_order(self):
        pairs = 0
        for i in range(len(FACES)):
            for j in range(i + 1, len(FACES)):
                a, b = FACES[i], FACES[j]
                r = self._run("info", a, *FACE_ARGS.get(a, ()),
                              b, *FACE_ARGS.get(b, ()))
                self.assertEqual(r.returncode, 2, (a, b))
                self.assertEqual(
                    r.stderr,
                    "CANNOT: %s, %s are mutually exclusive info faces; "
                    "pick one.\n" % (a, b), (a, b))
                self.assertEqual(r.stdout, "", (a, b))
                pairs += 1
        self.assertEqual(pairs, 21)

    def test_neighbouring_guards_survive_the_render(self):
        # r172 renderer clash, r337 face x block, r342 window without
        # --index, r205/r161 --warnings-only --json: all still answer
        # exactly as pinned; only the copies changed this round.
        r = self._run("info", "--index", "--format", "version")
        self.assertEqual(r.returncode, 2)
        self.assertIn("full payload", r.stderr)
        r = self._run("info", "--version", "--health")
        self.assertEqual(r.returncode, 2)
        r = self._run("info", "--index-since", "r170")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--index", r.stderr)
        r = self._run("info", "--warnings-only", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        json.loads(r.stdout)


class CatalogPinTests(unittest.TestCase):
    """The catalog registers the round and keeps its shape."""

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("face-set-copies-rendered", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "face-set-copies-rendered")
        self.assertEqual(entry["since"], "r352")
        self.assertIn("INFO_FACE_FLAGS", entry["summary"])
        self.assertIn("r349", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 202 before r352; one entry lands. Floor, not exact.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 203)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertEqual(len(mindseam.INFO_FACE_FLAGS), 7)
        self.assertEqual(len(mindseam.AUDIT_TAG_EXPLAIN),
                         len(mindseam.AUDIT_TAGS))


if __name__ == "__main__":
    unittest.main()
