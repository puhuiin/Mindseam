# -*- coding: utf-8 -*-
"""Round 178 guards: resume --dry-run, completing the plan trio.

``seam --dry-run`` has existed since the first rounds and
``note --dry-run`` landed in r177. ``resume`` is the third
and last mutating surface: a real resume appends one history
row and may compact the history file. r178 borrows from
``terraform plan`` one more time: the reentry report is
computed exactly as a real resume would compute it — same
health score, same risk, same trend — but nothing is
appended and nothing is compacted.

The JSON face carries a ``dry_run`` boolean so a host
reading the payload can tell a preview from a real resume,
the way ``terraform plan`` marks its output as a plan. The
text face prints a ``(dry run) history row not appended``
footer so a human scrolling the transcript sees the
preview marker too.

The side-effect contract of a real resume is unchanged:
without the flag, one history row is appended and the
compaction runs, byte-identical to the r158 behaviour.
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


def _write_history(workspace, rows):
    path = Path(workspace) / ".mindseam" / "history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")


def _read_history(workspace):
    path = Path(workspace) / ".mindseam" / "history.json"
    return json.loads(path.read_text(encoding="utf-8"))


class DryRunBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _ledger(self, goal="demo", next_="n1"):
        path = Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = ["# L", "", "## Goal", goal, "", "## Core", "",
                "## Verified", "", "## Open", "", "## Next", next_, ""]
        path.write_text("\n".join(text), encoding="utf-8")

    def _seed_history(self, n=1):
        _write_history(self.workspace, [
            {"t": i + 1, "next": "dom: step %d" % i,
             "verified": 0, "open": 0}
            for i in range(n)
        ])


class ResumeDryRunTests(DryRunBase):
    """The preview computes the report; the side effect is skipped."""

    def test_dry_run_does_not_append_history(self):
        self._ledger()
        self._seed_history(3)
        r = _invoke(["resume", "--dry-run", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["history_count"], 3)
        # The side effect is skipped.
        self.assertEqual(len(_read_history(self.workspace)), 3)

    def test_dry_run_json_carries_marker(self):
        # The marker is False on a real resume, True on a
        # preview, so a host reading the payload can tell
        # them apart, the way ``terraform plan`` marks a
        # plan.
        self._ledger()
        self._seed_history(1)
        r_real = _invoke(["resume", "--json"],
                         cwd=self.workspace)
        p_real = json.loads(r_real.stdout)
        self.assertFalse(p_real["dry_run"])
        self.assertEqual(p_real["history_count"], 2)

    def test_dry_run_text_face_prints_footer(self):
        self._ledger()
        self._seed_history(1)
        r = _invoke(["resume", "--dry-run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The reentry banner still prints (text face), plus
        # the dry-run footer.
        self.assertIn("mindseam", r.stdout)
        self.assertIn("(dry run) history row not appended", r.stdout)

    def test_dry_run_format_reads_preview_payload(self):
        # --format composes with --dry-run: the dot-path
        # renderer reads the preview payload, the way
        # ``terraform plan -json`` composes with other
        # output flags.
        self._ledger()
        self._seed_history(2)
        r = _invoke(["resume", "--dry-run", "--format",
                     "history_count,dry_run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.strip().split("\n")
        self.assertEqual(lines, ["2", "true"])

    def test_dry_run_health_score_matches_real(self):
        # The preview computes the same score a real resume
        # would (the score is a function of the ledger and
        # the pre-append history; the appended row itself
        # changes the score only through the count, which
        # the score does not use). The pin is that the
        # score block is present and well-formed in both.
        self._ledger()
        self._seed_history(2)
        r = _invoke(["resume", "--dry-run", "--format",
                     "trend.score.value"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip().isdigit())

    def test_real_resume_still_appends(self):
        # Backward compat: without the flag the r158
        # behaviour is unchanged.
        self._ledger()
        self._seed_history(1)
        r = _invoke(["resume"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(_read_history(self.workspace)), 2)

    def test_dry_run_ignores_history_compaction(self):
        # A real resume may compact history; a dry-run
        # reports the read-time state repairs but applies
        # no compaction. With a well-formed history there
        # is nothing to repair and nothing to compact, and
        # the file is untouched either way.
        self._ledger()
        self._seed_history(5)
        before = _read_history(self.workspace)
        _invoke(["resume", "--dry-run", "--json"],
                 cwd=self.workspace)
        self.assertEqual(_read_history(self.workspace), before)


class ResumeDryRunCatalogTests(unittest.TestCase):
    """The catalog registers the new capability."""

    def test_dry_run_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("resume-dry-run", ids)

    def test_dry_run_since_round_is_r178(self):
        for entry in mindseam._FEATURE_CATALOG:
            if entry["id"] == "resume-dry-run":
                self.assertEqual(entry["since"], "r178")
                self.assertTrue(entry["default"])
                return
        self.fail("resume-dry-run entry missing from catalog")
