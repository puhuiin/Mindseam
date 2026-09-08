# -*- coding: utf-8 -*-
"""Round 177 guards: note --dry-run, the terraform plan mode.

``seam --dry-run`` has existed since the first rounds: a seam
can be previewed without appending to history.json. ``note``
never had the same flag, so a host that wants to validate a
note call — a CI script that checks whether a proposed edit
would be accepted — had to run the note for real and clean
up after a refusal. r177 borrows from ``terraform plan`` /
``git add --dry-run``: the edits are computed exactly as a
real note would compute them (same validation, same refusal
contract), but the ledger and the meta file are not written.

The plan is section-level: a section that did not change is
not listed, the way ``terraform plan`` lists only drifted
resources. The refusal contract is byte-identical — the
same NOT RECORDED lines print with or without the flag, and
refusals exit 2 either way. A no-change note under dry-run
reports "No changes would be applied." instead of echoing
the unchanged ledger, the way ``terraform plan`` reports
"No changes."
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _invoke(args, cwd, env=None):
    run_env = os.environ.copy()
    run_env.pop("MINDSEAM_INTENSITY", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, str(MINDSEAM), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        env=run_env,
    )


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

    def _ledger_text(self):
        return (Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
                ).read_text(encoding="utf-8")


class DryRunPlanTests(DryRunBase):
    """The plan is the product; nothing is written."""

    def test_dry_run_prints_section_plan(self):
        self._ledger()
        r = _invoke(["note", "--next", "n2", "--dry-run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("note (dry run)", r.stdout)
        self.assertIn("~ Next", r.stdout)
        self.assertIn("No changes written", r.stdout)

    def test_dry_run_does_not_write(self):
        self._ledger()
        _invoke(["note", "--next", "n2", "--dry-run"],
                 cwd=self.workspace)
        text = self._ledger_text()
        self.assertIn("n1", text)
        self.assertNotIn("n2", text)

    def test_dry_run_lists_only_changed_sections(self):
        # Goal and Next both change; Core / Verified / Open
        # do not, and must not appear in the plan, the way
        # ``terraform plan`` lists only drifted resources.
        self._ledger()
        r = _invoke(["note", "--goal", "g2", "--next", "n2",
                     "--dry-run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("~ Goal", r.stdout)
        self.assertIn("~ Next", r.stdout)
        self.assertNotIn("~ Core", r.stdout)
        self.assertNotIn("~ Verified", r.stdout)
        self.assertNotIn("~ Open", r.stdout)

    def test_dry_run_check_adds_verified_section(self):
        # A --check edit lands in Verified; the plan names
        # the section that would grow.
        self._ledger()
        r = _invoke(["note", "--check", "what now holds",
                     "--by", "brute force, including empty and maximum",
                     "--dry-run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("~ Verified", r.stdout)
        self.assertNotIn("~ Verified", self._ledger_text())

    def test_dry_run_open_adds_open_section(self):
        self._ledger()
        r = _invoke(["note", "--open", "the question",
                     "--settled-by", "cheapest test",
                     "--dry-run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("~ Open", r.stdout)
        self.assertNotIn("?01", self._ledger_text())

    def test_dry_run_close_removes_open_section(self):
        # Close requires a check in the same call; the plan
        # shows both the Verified addition and the Open
        # removal.
        self._ledger()
        base = ["# L", "", "## Goal", "demo", "", "## Core", "",
                "## Verified", "", "## Open",
                "?01 the question — settled by: cheapest test",
                "", "## Next", "n1", ""]
        (Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
         ).write_text("\n".join(base), encoding="utf-8")
        r = _invoke(["note", "--close", "1",
                     "--check", "settled",
                     "--by", "brute force, including empty and maximum",
                     "--dry-run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("~ Open", r.stdout)
        # The open question is still on disk.
        self.assertIn("?01", self._ledger_text())

    def test_dry_run_no_change_reports_no_changes(self):
        # A note with no edit flags changes nothing; the plan
        # says so instead of echoing the ledger, the way
        # ``terraform plan`` reports "No changes." (``--next
        # same`` is an idempotent edit -- the r156 semantics
        # treat any --next value as a write, so it is not the
        # no-change case.)
        self._ledger()
        r = _invoke(["note", "--dry-run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("No changes would be applied", r.stdout)
        self.assertNotIn("~ Next", r.stdout)


class DryRunRefusalTests(DryRunBase):
    """The refusal contract is byte-identical with the flag."""

    def test_refusal_exits_two_with_dry_run(self):
        self._ledger()
        r = _invoke(["note", "--next", "n2", "--by", "orphan",
                     "--dry-run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--by requires --check", r.stdout)

    def test_refusal_does_not_write_partial_edits(self):
        # A real note with a refused edit still writes the
        # accepted ones ("everything else in this call was
        # recorded"). A dry-run writes nothing, even when
        # some edits were accepted.
        self._ledger()
        _invoke(["note", "--next", "n2", "--by", "orphan",
                 "--dry-run"],
                 cwd=self.workspace)
        text = self._ledger_text()
        self.assertIn("n1", text)
        self.assertNotIn("n2", text)

    def test_fresh_creation_refusal_does_not_create_ledger(self):
        # Opening the ledger requires both Goal and Next; a
        # dry-run of an incomplete creation must not create
        # the .mindseam directory either.
        r = _invoke(["note", "--goal", "g", "--dry-run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertFalse(
            (Path(self.workspace) / ".mindseam" / "WORKSPACE.md").exists())

    def test_refusal_without_dry_run_still_writes(self):
        # Backward compat: without --dry-run the behaviour
        # is unchanged — accepted edits are recorded even
        # when other edits are refused.
        self._ledger()
        r = _invoke(["note", "--next", "n2", "--by", "orphan"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("n2", self._ledger_text())


class DryRunMetaTests(DryRunBase):
    """meta writes are also deferred under dry-run."""

    def test_dry_run_marker_does_not_write_meta(self):
        # A --marker edit lands in metacognition.json; the
        # dry-run must not write it.
        self._ledger()
        r = _invoke(["note", "--next", "n2", "--marker", "OPEN",
                     "--dry-run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("~ meta", r.stdout)
        self.assertFalse(
            (Path(self.workspace) / ".mindseam" / "metacognition.json").exists())

    def test_dry_run_confidence_reports_meta(self):
        self._ledger()
        r = _invoke(["note", "--next", "n2",
                     "--confidence", "thin", "--dry-run"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("~ meta", r.stdout)


class DryRunCatalogTests(unittest.TestCase):
    """The catalog registers the new capability."""

    def test_dry_run_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("note-dry-run", ids)

    def test_dry_run_since_round_is_r177(self):
        for entry in mindseam._FEATURE_CATALOG:
            if entry["id"] == "note-dry-run":
                self.assertEqual(entry["since"], "r177")
                self.assertTrue(entry["default"])
                return
        self.fail("note-dry-run entry missing from catalog")
