# -*- coding: utf-8 -*-
"""r337 — five info faces silently swallowed every payload block.

``mode_info``'s short-circuit faces answer from their own narrow source:
``--version`` prints the version, ``--check`` the issues, ``--memory`` the
size, ``--list-fields`` the schema, ``--index`` the flat index. Each
returns before the full report is rendered, so every payload BLOCK asked
for alongside one was silently dropped.

r200 closed the face/face pairs, r172 closed the renderer pairs
(``--format``/``--field``), and r202/r205 closed ``--explain`` and
``--warnings-only`` against the blocks — but the five faces that predate
those rounds kept swallowing them. Live before-fix:

    info --version --health      -> rc 0, the version, no health block
    info --version --features    -> rc 0, the version, no feature table
    info --check --mtime         -> rc 0, the issues, no file snapshot
    info --memory --content-hash -> rc 0, the size, no hashes
    info --list-fields --aliases -> rc 0, the schema, no aliases
    info --index --features      -> rc 0, the index, no feature table

and the same for ``--manifest``, ``--workspace-id``, ``--audit-baseline``,
``--changed``, ``--human`` and ``--text``. ``--text`` is the sharpest:
its documented contract is "force a plain-text report even if --json is
also set", and with a face it was dropped rather than honoured or
refused.

The fix adds the missing third guard in the dispatcher, before any face
branch runs, so a face never gets the chance to drop a block. Two
deliberate exclusions keep every earlier contract intact:

- ``--explain`` and ``--warnings-only`` are left to their own r202/r205
  refusals inside ``mode_info``, which name the reason more specifically
  ("answers from the static catalog", "prints the warning lines only").
- ``--warnings-only --json`` is exempt entirely: it prints the FULL
  payload (the r161 no-suppression pin), so a block flag alongside it is
  honoured, not dropped.

Scope: the dispatcher guard only. ``--index``'s own modifiers
(``--index-since``/``--index-until``) are not payload blocks and still
compose, and ``--json`` still rides every face as its machine sub-face.
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

FACES = ("--index", "--version", "--check", "--memory", "--list-fields")
BLOCKS = ("--health", "--manifest", "--mtime", "--features", "--aliases",
          "--human", "--workspace-id", "--content-hash", "--changed",
          "--text")
VALUED = {"--audit-baseline": "nope.json"}


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
        ws = tempfile.mkdtemp(prefix="r337_")
        self._workspaces.append(ws)
        return ws

    def _run(self, *args):
        return run_controller(self.ws, *args)


class FaceBlocksRefusedTests(_Base):
    """Every face refuses every payload block."""

    def test_every_face_refuses_every_block(self):
        for face in FACES:
            for block in BLOCKS:
                with self.subTest(face=face, block=block):
                    r = self._run("info", face, block)
                    self.assertEqual(r.returncode, 2,
                                     "%s %s: %s" % (face, block,
                                                    r.stdout + r.stderr))
                    self.assertIn("would be silently dropped", r.stderr)

    def test_valued_block_is_refused_too(self):
        for face in FACES:
            with self.subTest(face=face):
                r = self._run("info", face, "--audit-baseline", "nope.json")
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("--audit-baseline", r.stderr)

    def test_the_refusal_names_the_face_and_the_block(self):
        r = self._run("info", "--version", "--health")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--version", r.stderr)
        self.assertIn("--health", r.stderr)

    def test_the_refusal_names_every_block_given(self):
        r = self._run("info", "--check", "--health", "--mtime",
                      "--features")
        self.assertEqual(r.returncode, 2)
        first = r.stderr.splitlines()[0]
        for name in ("--health", "--mtime", "--features"):
            self.assertIn(name, first)

    def test_order_does_not_matter(self):
        for args in (["info", "--version", "--health"],
                     ["info", "--health", "--version"]):
            with self.subTest(args=args):
                r = self._run(*args)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_text_is_refused_with_a_face(self):
        # --text's contract is "force text even with --json"; with a
        # face it was dropped rather than honoured or refused.
        for face in FACES:
            with self.subTest(face=face):
                r = self._run("info", face, "--text")
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


class EarlierContractsPreservedTests(_Base):
    """The three exclusions keep r161/r202/r205 intact."""

    def test_warnings_only_json_still_keeps_the_full_payload(self):
        # r161 no-suppression pin: --warnings-only --json prints every
        # key, so a block alongside it is honoured.
        r = self._run("info", "--warnings-only", "--json", "--health")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("health", payload)
        self.assertIn("ledger", payload)

    def test_warnings_only_text_still_refuses_with_its_own_message(self):
        # r205's message, not the new one.
        r = self._run("info", "--warnings-only", "--manifest")
        self.assertEqual(r.returncode, 2)
        self.assertIn("prints the warning lines only", r.stderr)

    def test_explain_still_refuses_with_its_own_message(self):
        r = self._run("info", "--explain", "info-version", "--manifest")
        self.assertEqual(r.returncode, 2)
        self.assertIn("builds no payload", r.stderr)

    def test_explain_unknown_id_still_refuses_first(self):
        r = self._run("info", "--explain", "nope", "--manifest")
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a recognised feature id", r.stderr)


class SingleFaceStillWorksTests(_Base):
    """A face alone, and its modifiers, are untouched."""

    def test_each_face_alone_still_answers(self):
        for face in FACES:
            with self.subTest(face=face):
                r = self._run("info", face)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertTrue(r.stdout.strip())

    def test_each_face_json_alone_still_answers(self):
        for face in FACES:
            with self.subTest(face=face):
                r = self._run("info", face, "--json")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                json.loads(r.stdout)

    def test_index_window_modifiers_still_compose(self):
        for extra in (["--index-since", "r200"],
                      ["--index-until", "r300"],
                      ["--index-since", "r200", "--index-until", "r300"]):
            with self.subTest(extra=extra):
                r = self._run("info", "--index", *extra)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_blocks_alone_still_work(self):
        for block in ("--health", "--features", "--mtime", "--changed"):
            with self.subTest(block=block):
                r = self._run("info", block)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertTrue(r.stdout.strip())

    def test_two_blocks_together_still_compose(self):
        # Blocks are not faces: two of them still ride one report.
        r = self._run("info", "--health", "--features")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_face_vs_face_still_refuses(self):
        # r200's rule, re-pinned so the new guard did not displace it.
        r = self._run("info", "--version", "--check")
        self.assertEqual(r.returncode, 2)
        self.assertIn("mutually exclusive info faces", r.stderr)

    def test_renderer_vs_face_still_refuses(self):
        # r172's rule, re-pinned.
        r = self._run("info", "--version", "--format", "version")
        self.assertEqual(r.returncode, 2)
        self.assertIn("would be dropped", r.stderr)


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

    def test_entry_present_since_r337_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "info-face-refuses-payload-blocks"),
                     None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r337")
        self.assertTrue(entry["default"])

    def test_r337_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 337)


if __name__ == "__main__":
    unittest.main()
