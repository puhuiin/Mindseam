# -*- coding: utf-8 -*-
"""Round 205 guards: info --warnings-only is a face, and its text face
refuses the payload blocks.

r200 made the info short-circuit faces mutually exclusive and
r202 added --explain — but the sweep enumerated the dispatcher's
branch list, and ``--warnings-only`` lived one layer deeper: its
branch sits inside mode_info, after the payload is built, and on
the text face prints ONLY the warning lines. ``info --check
--warnings-only`` therefore printed the warnings (check never
ran), and ``info --warnings-only --manifest`` computed the
manifest into the payload and printed none of it — both exit 0,
both silent drops of the r200 family.

r205 joins --warnings-only to the dispatcher's face set (seventh
face: face pairs and face-x-renderer clashes refuse there, free
with the r200 machinery) and refuses the payload blocks on the
text face through the r202 shared flag table. The JSON face is
deliberately untouched: ``--warnings-only --json`` prints the
FULL payload — the r161 no-suppression pin — so the blocks are
honoured there and the composition stays legal.
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


def _invoke(args, cwd):
    return invoke_cli(cwd, args)


class WarningsOnlyFaceExclusivityTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        (self.ledger / "history.json").write_text("[]", encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_face_pairs_refuse_in_dispatcher(self):
        for args in (["info", "--warnings-only", "--check"],
                     ["info", "--warnings-only", "--version"],
                     ["info", "--warnings-only", "--memory"],
                     ["info", "--warnings-only", "--list-fields"],
                     ["info", "--warnings-only", "--index"],
                     ["info", "--warnings-only", "--explain",
                      "info-memory"]):
            r = _invoke(args, self.workspace)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn("mutually exclusive info faces", r.stderr)
            self.assertIn("--warnings-only", r.stderr)

    def test_format_renderer_refuses_in_dispatcher(self):
        r = _invoke(["info", "--warnings-only", "--format",
                     "warnings[0]"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--format", r.stderr)

    def test_field_renderer_refuses_in_dispatcher(self):
        r = _invoke(["info", "--warnings-only", "--field",
                     "warnings[0]"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--field", r.stderr)

    def test_text_face_blocks_refuse_in_mode(self):
        for flag, extra in (("--manifest", None), ("--mtime", None),
                            ("--health", None), ("--workspace-id", None),
                            ("--content-hash", None), ("--changed", None),
                            ("--features", None), ("--aliases", None),
                            ("--human", None),
                            ("--audit-baseline", "bl.json")):
            args = ["info", "--warnings-only", flag]
            if extra:
                args.append(extra)
            r = _invoke(args, self.workspace)
            self.assertEqual(r.returncode, 2, flag)
            self.assertIn("prints the warning lines only", r.stderr)
            self.assertIn(flag, r.stderr)
            self.assertEqual(r.stdout, "")

    def test_text_blocks_named_together(self):
        r = _invoke(["info", "--warnings-only", "--manifest",
                     "--health"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--manifest", r.stderr)
        self.assertIn("--health", r.stderr)

    def test_json_face_stays_composable_full_payload(self):
        # The r161 no-suppression pin: --warnings-only --json prints
        # the FULL payload, so the blocks are honoured, not dropped.
        r = _invoke(["info", "--warnings-only", "--json",
                     "--manifest"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("audit_manifest", payload)
        self.assertIn("warnings", payload)

    def test_alone_paths_unchanged(self):
        r = _invoke(["info", "--warnings-only"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Warning:", r.stdout)
        r = _invoke(["info", "--warnings-only", "--json"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("warnings", json.loads(r.stdout))

    def test_explain_still_refuses_with_blocks(self):
        # The r202 contract rides the shared table unchanged.
        r = _invoke(["info", "--explain", "info-memory",
                     "--manifest"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("builds no payload", r.stderr)

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("info-warnings-only-face-exclusive", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "info-warnings-only-face-exclusive")
        self.assertEqual(entry["since"], "r205")
        self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
