# -*- coding: utf-8 -*-
"""r348 — the last payload block with no text face at all.

`info` carries six payload blocks: `--health`, `--mtime`,
`--content-hash`, `--changed`, `--manifest`, and `--workspace-id`. Five of
them print their own section on the text face. ``--manifest`` did not.

r242 found exactly this shape for ``--health`` and wrote the diagnosis
down: "the health block had no text face at all, so ``info --health``
printed the ordinary report and never the answer that was asked for —
the same silent-drop shape as r202/r205, one layer lower because here
the flag was simply never rendered." It gave health a section. ``--mtime``
(r163) and ``--content-hash`` / ``--changed`` (r166) each had one from the
start.

``--manifest`` never got one, and r337 made it look handled. r337 added
``--manifest`` to the face/block exclusivity guard, so
``info --version --manifest`` is correctly refused — but ``info
--manifest`` ALONE answered rc 0 with the plain report and no manifest
section. Live before-fix, on a normal workspace:

    info --manifest         -> 12 lines, the last of them the ordinary
                              "Audit: 3 items removable" summary
    info --json --manifest  -> the full audit_manifest block, all nine
                              tags with counts

A host that asked for the manifest got no signal it had not been
rendered. That is the r202/r205/r337 family — a silently dropped
request at exit 0 — on the one block that round's own guard gave the
appearance of covering.

THE FIX adds the missing section, in the shape its siblings use: one
summary line, then one line per artefact. Here the "artefacts" are the
tags, and they are ALL listed — including the tags that did not fire —
because that is the block's stated purpose (r163): a missing tag means
the detector did not run, not that it found nothing. The columns follow
``pip list``'s two-column shape so a host can grep or awk on the result.

Order matters and is tested: the manifest section rides after
``--content-hash`` and before ``--changed``, so a combined call prints the
sections in a stable order whatever order the flags arrived in.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import mindseam
from _controller_helper import invoke_cli

BLOCKS = ("--health", "--mtime", "--content-hash", "--changed",
          "--manifest", "--workspace-id")


def _workspace(verified=(), open_=(), core=("c1 — work",)):
    ws = tempfile.mkdtemp()
    d = os.path.join(ws, ".mindseam")
    os.makedirs(d)
    with open(os.path.join(d, "WORKSPACE.md"), "w", encoding="utf-8") as f:
        out = ["# L", "", "## Goal", "g", "", "## Core"]
        out += ["- " + c for c in core]
        out += ["", "## Verified"] + ["- " + v for v in verified]
        out += ["", "## Open"] + ["- " + o for o in open_]
        out += ["", "## Next", "n"]
        f.write("\n".join(out) + "\n")
    with open(os.path.join(d, "history.json"), "w", encoding="utf-8") as f:
        json.dump([{"t": 1700000000 + i, "next": "dom: a",
                    "msg": "m%d" % i, "verified": 0, "open": 0}
                   for i in range(12)], f)
    return ws


class ManifestTextFaceTests(unittest.TestCase):
    """The defect: the section now exists."""

    def test_the_section_prints(self):
        r = invoke_cli(_workspace(), ["info", "--manifest"])
        self.assertIn("Audit manifest:", r.stdout)

    def test_the_summary_line_names_the_counts(self):
        r = invoke_cli(_workspace(), ["info", "--manifest"])
        line = [l for l in r.stdout.splitlines()
                if l.startswith("Audit manifest:")]
        self.assertTrue(line)
        payload = json.loads(invoke_cli(
            _workspace(), ["info", "--json", "--manifest"]).stdout)
        block = payload["audit_manifest"]
        # The text line and the JSON counts must agree, the r254/r259
        # one-value-every-projector discipline.
        self.assertIn("%d tags" % block["tags_total"], line[0])
        self.assertIn("%d fired" % block["tags_fired"], line[0])
        self.assertIn("%d clean" % block["tags_clean"], line[0])

    def test_every_tag_is_listed(self):
        r = invoke_cli(_workspace(), ["info", "--manifest"])
        for tag in mindseam.AUDIT_TAGS:
            self.assertIn(tag, r.stdout, tag)

    def test_the_counts_match_the_json_block(self):
        ws = _workspace()
        text = invoke_cli(ws, ["info", "--manifest"]).stdout
        block = json.loads(invoke_cli(ws, ["info", "--json",
                                           "--manifest"]).stdout)[
            "audit_manifest"]
        for tag, count in block["by_tag"].items():
            self.assertIn("  %-22s  %d" % (tag, count), text,
                          "%s count mismatch" % tag)

    def test_a_tag_that_did_not_fire_is_listed_too(self):
        # r163's stated purpose: a missing tag means the detector did not
        # run, not that it found nothing.
        ws = _workspace()
        block = json.loads(invoke_cli(ws, ["info", "--json",
                                           "--manifest"]).stdout)[
            "audit_manifest"]
        clean = [t for t, c in block["by_tag"].items() if c == 0]
        self.assertTrue(clean, "this workspace fires every tag")
        text = invoke_cli(ws, ["info", "--manifest"]).stdout
        for tag in clean:
            pattern = "  %-22s  0" % tag
            self.assertIn(pattern, text, "%s missing or miscounted" % tag)


class EveryBlockHasATextFaceTests(unittest.TestCase):
    """The invariant the fix restores: no payload block is silent."""

    def test_every_block_prints_something_of_its_own(self):
        # The plain report is the control. Each block must add content
        # beyond it.
        plain = invoke_cli(_workspace(), ["info"]).stdout
        for block in BLOCKS:
            argv = ["info"]
            if block == "--workspace-id":
                continue     # a scalar id, not a section
            r = invoke_cli(_workspace(), argv + [block])
            self.assertTrue(r.stdout.startswith(plain[:60]),
                            "%s changed the base report" % block)
            extra = [l for l in r.stdout.splitlines()
                     if l not in plain.splitlines()]
            self.assertTrue(extra, "%s adds no text-face content" % block)

    def test_workspace_id_is_a_scalar_not_a_section(self):
        # r160: the workspace_id block is one id, and it renders as part
        # of the JSON payload. It has never claimed a text section and
        # this round does not add one.
        r = invoke_cli(_workspace(), ["info", "--workspace-id"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Workspace:", r.stdout)


class InteractionTests(unittest.TestCase):
    """The new section composes with the guards and siblings."""

    def test_r337_still_refuses_a_face_plus_manifest(self):
        # The guard r337 added is unchanged and still fires.
        for face in ("--version", "--check", "--index", "--memory",
                     "--list-fields", "--warnings-only"):
            r = invoke_cli(_workspace(), ["info", face, "--manifest"])
            self.assertEqual(r.returncode, 2, face)
            self.assertIn("--manifest", r.stderr)

    def test_two_blocks_still_compose(self):
        r = invoke_cli(_workspace(), ["info", "--health", "--manifest"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Health:", r.stdout)
        self.assertIn("Audit manifest:", r.stdout)

    def test_sections_print_in_a_stable_order(self):
        # Whatever order the flags arrived in.
        a = invoke_cli(_workspace(), ["info", "--manifest",
                                      "--content-hash"]).stdout
        b = invoke_cli(_workspace(), ["info", "--content-hash",
                                      "--manifest"]).stdout
        self.assertEqual(a, b)
        self.assertLess(a.index("Content hash:"),
                        a.index("Audit manifest:"))

    def test_manifest_before_changed(self):
        r = invoke_cli(_workspace(), ["info", "--manifest",
                                      "--changed"]).stdout
        self.assertLess(r.index("Audit manifest:"),
                        r.index("Changed since last call:"))

    def test_the_json_face_is_unchanged(self):
        # A rendering fix must not touch the machine face.
        a = json.loads(invoke_cli(_workspace(), ["info", "--json",
                                                 "--manifest"]).stdout)
        self.assertEqual(sorted(a["audit_manifest"].keys()),
                         ["by_tag", "tags_clean", "tags_fired",
                          "tags_total"])

    def test_manifest_alone_still_answers(self):
        r = invoke_cli(_workspace(), ["info", "--manifest"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_the_render_is_not_in_the_json_only_path(self):
        # The regression that would make this round moot: the section
        # must be outside the `if json_flag` branch.
        r = invoke_cli(_workspace(), ["info", "--manifest"])
        self.assertNotIn("Audit manifest: {", r.stdout.replace("\n", " "))


class SourceShapeTests(unittest.TestCase):
    """The fix's own construction."""

    def test_the_source_names_the_round(self):
        src = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(
            encoding="utf-8")
        i = src.find("# r348: the last payload block with no text face")
        self.assertGreater(i, 0, "the r348 comment is missing")
        head = src[i:i + 2400]
        self.assertIn("no text face at all", head)
        self.assertIn("r242", head)
        self.assertIn("--manifest", head)

    def test_the_section_is_guarded_on_manifest(self):
        src = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(
            encoding="utf-8")
        self.assertIn('if manifest and "audit_manifest" in payload:', src)

    def test_every_other_block_has_its_own_guard(self):
        # The five siblings, so a future block cannot be added without a
        # face without this test noticing.
        src = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(
            encoding="utf-8")
        for guard in ('if health and "health" in payload:',
                      'if mtime and "workspace_files" in payload:',
                      'if content_hash and "content_hash" in payload:',
                      'if changed and "changed" in payload:',
                      'if manifest and "audit_manifest" in payload:'):
            self.assertIn(guard, src, guard)


class CatalogPinTests(unittest.TestCase):
    """The catalog registers the round and keeps its shape."""

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("manifest-text-face", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "manifest-text-face")
        self.assertEqual(entry["since"], "r348")
        self.assertIn("--manifest", entry["summary"])
        self.assertIn("r242", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 198 before r348; one entry lands.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 199)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertTrue(callable(mindseam.mode_info))


if __name__ == "__main__":
    unittest.main()
