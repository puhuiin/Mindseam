# -*- coding: utf-8 -*-
"""Round 171 guards: audit --explain, the static tag doc.

A host (or human) that meets an audit finding can ask
``audit --explain <tag>`` for the trigger, the fix, and the
evidence shape, without grepping the source. Borrowed from
``git help <cmd>`` / ``tldr`` / ``kubectl explain``: static
self-documentation that works in an empty workspace, the way
``git help`` works outside a repository.

The doc dict is hand-curated like the r167 feature catalog.
Its keys must track ``AUDIT_TAGS`` exactly — a new tag cannot
ship undocumented, the way a new flag cannot ship
undocumented since the r69 drift guard.
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


def _invoke(args, cwd, env=None):
    return invoke_cli(cwd, args, env=env,
                       drop_env=("MINDSEAM_INTENSITY",))


class ExplainCatalogTests(unittest.TestCase):
    """The static doc tracks the tag tuple exactly."""

    def test_explain_keys_match_audit_tags(self):
        self.assertEqual(
            set(mindseam.AUDIT_TAG_EXPLAIN.keys()),
            set(mindseam.AUDIT_TAGS))

    def test_every_entry_has_three_fields(self):
        for tag, doc in mindseam.AUDIT_TAG_EXPLAIN.items():
            self.assertEqual(
                set(doc.keys()),
                {"trigger", "fix", "evidence"},
                "tag %s doc malformed" % tag)
            for key, value in doc.items():
                self.assertIsInstance(value, str)
                self.assertGreater(len(value), 0,
                                   "tag %s field %s empty" % (tag, key))


class ExplainBehaviorTests(unittest.TestCase):
    """``--explain TAG`` works in an empty workspace."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_explain_works_in_empty_workspace(self):
        # No .mindseam, no ledger — the doc is static data.
        r = _invoke(["audit", "--explain", "delete"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("audit explain delete", r.stdout)
        self.assertIn("trigger:", r.stdout)
        self.assertIn("fix:", r.stdout)
        self.assertIn("evidence:", r.stdout)

    def test_explain_every_tag(self):
        for tag in mindseam.AUDIT_TAGS:
            r = _invoke(["audit", "--explain", tag],
                        cwd=self.workspace)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("audit explain %s" % tag, r.stdout)
            self.assertIn(doc_check(tag), r.stdout)

    def test_explain_unknown_tag_refused(self):
        r = _invoke(["audit", "--explain", "nope"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("not a recognised audit tag", r.stderr)
        # The error names the known set so the host can recover.
        self.assertIn("delete", r.stderr)
        self.assertIn("core-drift", r.stderr)

    def test_explain_json_face(self):
        r = _invoke(["audit", "--explain", "next-stall",
                     "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["tag"], "next-stall")
        self.assertIn("trigger", payload)
        self.assertIn("fix", payload)
        self.assertIn("evidence", payload)
        # The JSON face matches the static catalog exactly.
        self.assertEqual(payload["trigger"],
                         mindseam.AUDIT_TAG_EXPLAIN["next-stall"]["trigger"])

    def test_explain_does_not_run_the_audit(self):
        # The explain branch short-circuits before the ledger
        # read, so a wasteful ledger still just prints the doc.
        led = Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
        led.parent.mkdir(parents=True, exist_ok=True)
        led.write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n?01 a — settled by: x\n?02 a — settled by: x\n\n"
            "## Next\nn\n", encoding="utf-8")
        r = _invoke(["audit", "--explain", "delete"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("audit explain delete", r.stdout)
        # No findings section in the output.
        self.assertNotIn("Net:", r.stdout)

    def test_explain_never_writes(self):
        # Report-only: the explain branch must not create
        # .mindseam or any artefact.
        _invoke(["audit", "--explain", "yagni"],
                cwd=self.workspace)
        self.assertFalse(
            (Path(self.workspace) / ".mindseam").exists())


def doc_check(tag):
    """A stable substring of each tag's trigger doc, for the sweep."""
    return {
        "delete": "duplicates another Open entry",
        "stdlib": "recorded twice",
        "yagni": "beyond the two live slots",
        "shrink": "blank next action",
        "goal-stale": "re-anchored",
        "next-stall": "3 or more of the last 5",
        "core-drift": "Next and Core disagree",
    }[tag]


if __name__ == "__main__":
    unittest.main()
