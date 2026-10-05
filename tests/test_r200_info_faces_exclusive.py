# -*- coding: utf-8 -*-
"""Round 200 guards: info's faces are exclusive; --index gets a JSON face.

The combination probe swept ``info``, the last surface with a branch
order of five short-circuit faces — ``--index``, ``--version``,
``--check``, ``--memory``, ``--list-fields`` — each of which returns
before the next one's branch is reached. A call asking for two faces
got whichever was checked first and silently dropped the rest:
``info --version --check`` printed the version, the fsck-style issues
list never ran; ``info --index --format version`` printed the flat
listing and the path renderer never applied — the same misinformation
shape as r188 (at × window), r197/198 (history renderers) and r199
(stdin × argv edits).

r200 refuses two classes:
  * two or more short-circuit faces together, naming them;
  * any short-circuit face together with ``--format``/``--field``
    (the renderers only read the full payload those faces skip).

The sweep ran over the five faces r200 knew. --explain (r202) and
--warnings-only (r205) joined the set afterwards, and this file's own
hand-typed FACES tuple never grew — the r352 drift the controller
round fixed by rendering the set from INFO_FACE_FLAGS. This file's
sweep now reads the same constant, so it covers all 21 pairs, and
FACE_ARGS supplies --explain's value wherever a combination probe
needs a complete call.

``--json`` is in neither class: every face already carries its own
machine sub-face (the r158 two-faces rule) except ``--index``, whose
``--index --json`` used to print text and leave the host's JSON parser
choking on ``info.…`` lines. r200 gives it the honest shape —
``{"index": [...]}`` — the text face byte-identical to before, and the
r175/r176 window filters still narrow it.

Pinned intact: every single face (text and JSON), the r172
``--field``/``--format`` mutual exclusion, and the index's
sorted-line contract (the JSON list equals the text lines).
"""

import json
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


# r352: read the set from the controller's single source instead of
# the hand copy — the five-face snapshot omitted --explain and
# --warnings-only, the two faces that joined in r202/r205, so the
# pair-sweep below covered 10 of 21 pairs and the explain/warnings
# face had never been swept against its newest siblings by this file.
FACES = tuple(flag for flag, _ in mindseam.INFO_FACE_FLAGS)
# --explain takes a FEATURE-ID value; a bare --explain in a
# combination probe dies as an argparse error, not the refusal under
# test. --warnings-only needs no value but answers from the health
# gate, which every fixture below already satisfies.
FACE_ARGS = {"--explain": ["info-memory"]}


class InfoFaceExclusivityTests(unittest.TestCase):

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

    def _run(self, *args, stdin=None):
        return invoke_cli(self.workspace, list(args), stdin=stdin)

    def test_every_face_pair_is_refused(self):
        for i in range(len(FACES)):
            for j in range(i + 1, len(FACES)):
                a, b = FACES[i], FACES[j]
                r = self._run("info", a, *FACE_ARGS.get(a, ()),
                              b, *FACE_ARGS.get(b, ()))
                self.assertEqual(r.returncode, 2, (a, b))
                self.assertIn("mutually exclusive info faces", r.stderr,
                              (a, b))
                self.assertIn(a, r.stderr, (a, b))
                self.assertIn(b, r.stderr, (a, b))
                self.assertEqual(r.stdout, "", (a, b))

    def test_face_with_renderer_is_refused(self):
        for face in FACES:
            r = self._run("info", face, *FACE_ARGS.get(face, ()),
                          "--format", "version")
            self.assertEqual(r.returncode, 2, face)
            self.assertIn("full payload", r.stderr, face)
            self.assertIn(face, r.stderr, face)
            r = self._run("info", face, *FACE_ARGS.get(face, ()),
                          "--field", "version")
            self.assertEqual(r.returncode, 2, face)
            self.assertIn("--field", r.stderr, face)

    def test_single_faces_still_work(self):
        for face in FACES:
            r = self._run("info", face, *FACE_ARGS.get(face, ()))
            self.assertEqual(r.returncode, 0, "%s -> %s" % (face, r.stderr))
            self.assertNotEqual(r.stdout, "", face)

    def test_face_json_subfaces_still_work(self):
        # The r158 two-faces rule is NOT refused: version/check/memory/
        # list-fields each own a machine sub-face.
        for face in ("--version", "--check", "--memory", "--list-fields"):
            r = self._run("info", face, "--json")
            self.assertEqual(r.returncode, 0, face)
            json.loads(r.stdout)  # must parse

    def test_r172_field_format_pair_still_refused(self):
        # The pre-existing renderer/renderer check is untouched when
        # no face is involved.
        r = self._run("info", "--field", "version", "--format", "version")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--field and --format are mutually exclusive",
                      r.stderr)


class IndexJsonFaceTests(unittest.TestCase):
    """``--index --json`` finally answers in JSON."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _run(self, *args):
        return invoke_cli(self.workspace, list(args))

    def test_json_index_shape_and_sorted_contract(self):
        text = self._run("info", "--index")
        js = self._run("info", "--index", "--json")
        self.assertEqual(js.returncode, 0, js.stderr)
        payload = json.loads(js.stdout)
        self.assertEqual(sorted(payload.keys()), ["index"])
        self.assertEqual(payload["index"], text.stdout.splitlines())
        self.assertEqual(payload["index"], sorted(payload["index"]))

    def test_window_filters_narrow_the_json_face(self):
        r = self._run("info", "--index", "--json", "--index-since", "r199")
        self.assertEqual(r.returncode, 0, r.stderr)
        entries = json.loads(r.stdout)["index"]
        self.assertIn("info.note-from-stdin-exclusive", entries)
        self.assertIn("info.info-index-json-face", entries)
        self.assertNotIn("info.history-filter", entries)

    def test_empty_result_is_empty_list(self):
        # A window that matches nothing yields [], not an error or the
        # text face leaking through. r356 is past the catalog (r355 is
        # the highest entry — each round's own catalog entry lands
        # inside the window the round before it left empty, so this
        # bracket has to move up every round), so the bracket is valid
        # but empty.
        r = self._run("info", "--index", "--json",
                      "--index-since", "r356", "--index-until", "r356")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), {"index": []})


if __name__ == "__main__":
    unittest.main()
