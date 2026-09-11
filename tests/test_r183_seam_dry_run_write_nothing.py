# -*- coding: utf-8 -*-
"""Round 183 guards: seam --dry-run writes nothing.

The dry-run contract is "write nothing", the way ``terraform plan``
writes nothing and the r177 ``note --dry-run`` defers its meta write.
The seam history append was already gated on ``not dry_run``; the
meta and skillbook side effects were not — ``seam --dry-run --json``
rewrote ``metacognition.json`` (even when the content was
byte-identical) and touched ``skillbook.md`` on every preview.

r183 gates them the same way: the in-memory ``meta`` /
``extract_skillbook(hist)`` results still feed the report, they just
do not land on disk. These tests pin the observable contract a host
relies on: a preview leaves ``.mindseam/`` byte-for-byte untouched.

The report side is unchanged — a dry-run still carries the
telemetry / score / risk fields that come from the in-memory meta
and health score, the way it did before.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from _controller_helper import invoke_cli

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _invoke(args, cwd):
    return invoke_cli(cwd, args)


class SeamDryRunWriteNothingTests(unittest.TestCase):
    """seam --dry-run leaves .mindseam/ byte-for-byte untouched."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        self.ledger_path = self.ledger

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _seam(self, extra=()):
        r = _invoke(["seam", "--json", *extra], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def _tree_snapshot(self):
        snap = {}
        for p in sorted(self.ledger.rglob("*")):
            if p.is_file():
                snap[str(p.relative_to(self.ledger))] = p.read_bytes()
        return snap

    def test_dry_run_on_clean_ledger_creates_no_artefacts(self):
        # A ledger with a goal/next but no real seam yet: a regular
        # seam would create history.json, metacognition.json and
        # skillbook.md; the dry-run must create none of them.
        _invoke(["note", "--next", "dom: step 0"], self.workspace)
        r = _invoke(["seam", "--dry-run", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        names = {p.name for p in self.ledger.iterdir()}
        self.assertEqual(names, {"WORKSPACE.md"})

    def test_dry_run_does_not_rewrite_meta_even_when_content_would_change(self):
        # Seed a real seam so metacognition.json exists.
        _invoke(["note", "--next", "dom: step 0"], self.workspace)
        self._seam()
        meta = self.ledger / "metacognition.json"
        self.assertTrue(meta.exists())
        # A shaky confidence would append to the meta trend if the
        # dry-run wrote; snapshot AFTER the note (the note's own meta
        # write is its expected side effect) so the before/after
        # comparison isolates what the seam dry-run does.
        _invoke(["note", "--confidence", "shaky"], self.workspace)
        before = meta.read_bytes()
        r = _invoke(["seam", "--dry-run", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(meta.read_bytes(), before)

    def test_dry_run_does_not_touch_skillbook(self):
        _invoke(["note", "--next", "dom: step 0"], self.workspace)
        self._seam()
        skillbook = self.ledger / "skillbook.md"
        self.assertTrue(skillbook.exists())
        mtime_before = skillbook.stat().st_mtime_ns
        r = _invoke(["seam", "--dry-run", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(skillbook.stat().st_mtime_ns, mtime_before)

    def test_dry_run_leaves_whole_ledger_untouched(self):
        # The strictest pin: the full artefact tree is identical
        # before and after a preview, history included.
        _invoke(["note", "--next", "dom: step 0"], self.workspace)
        self._seam()
        _invoke(["note", "--confidence", "shaky"], self.workspace)
        before = self._tree_snapshot()
        r = _invoke(["seam", "--dry-run", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self._tree_snapshot(), before)
        self.assertIn("dry-run: history.json was not updated", r.stdout)

    def test_real_seam_still_writes_meta_and_skillbook(self):
        # The gate must not leak into the real seam: without the
        # flag, both artefacts are written as before.
        _invoke(["note", "--next", "dom: step 0"], self.workspace)
        self._seam()
        self.assertTrue((self.ledger / "metacognition.json").exists())
        self.assertTrue((self.ledger / "skillbook.md").exists())

    def test_dry_run_report_still_carries_health_score(self):
        # The gate defers the *write*, not the computation: the
        # in-memory meta and health score still feed the report, so
        # a CI preview can gate on the same signals a real seam
        # would report.
        _invoke(["note", "--next", "dom: step 0"], self.workspace)
        self._seam()
        for _ in range(2):
            _invoke(["note", "--next", "dom: step 0"], self.workspace)
            self._seam()
        r = _invoke(["seam", "--dry-run", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("score", payload.get("trend", {}))
        self.assertIn("value", payload["trend"]["score"])


class ResumeDryRunUnaffectedTests(unittest.TestCase):
    """resume --dry-run keeps its own write-nothing contract."""

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

    def test_resume_dry_run_leaves_ledger_untouched(self):
        _invoke(["note", "--next", "dom: step 0"], self.workspace)
        r = _invoke(["seam", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        before = {p.name: p.read_bytes() for p in self.ledger.iterdir() if p.is_file()}
        r = _invoke(["resume", "--dry-run", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["dry_run"])
        after = {p.name: p.read_bytes() for p in self.ledger.iterdir() if p.is_file()}
        self.assertEqual(after, before)