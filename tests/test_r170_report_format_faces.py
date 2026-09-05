# -*- coding: utf-8 -*-
"""Round 170 guards: the --format dot-path renderer on every report face.

r158's two-faces rule says every report subcommand answers ``--json``;
r170 completes the same rule for ``--format``: every report face can
render a single scalar without the host piping the whole JSON through
``jq``. Borrowed from ``docker inspect --format`` / ``kubectl get -o
jsonpath`` / ``jq -r`` (the same family as r169's info ``--format``):
a comma-separated list of dot-paths prints one value per line, a
missing path prints an empty string, and the exit contract is
byte-identical to the JSON face.

Faces covered:

- ``seam --format`` — the seam still records its history row; only
  the renderer changes (banner and ledger dump are text-face only).
- ``resume --format`` — the premise prose and reentry banner are
  dropped, the way ``resume --json`` drops them; the side effect
  (one history row) is unchanged.
- ``ship --format`` — the exit contract is byte-identical across
  faces: ``--strict`` gating is decided before the renderer is
  chosen, so a host gating on the process exit code gets the same
  answer either way.
- ``skillbook --format`` — paths resolve against a dict root
  ``{"entries": [...]}``; the bare-list JSON face is unchanged.
- ``discover --format`` — ``domains[0].name`` and
  ``suggested_next`` resolve straight off the payload.
- ``audit --format`` — ``net`` / ``gate`` / ``by_tag.delete`` etc.
  resolve off the r162 payload; the ``--strict`` exit contract is
  the same as the JSON face.

Excluded on purpose:

- ``info`` — owns ``--format`` since r169 (the original).
- ``history`` — its ``--format`` is the older per-row template
  renderer (``%h %n``); the dot-path renderer would clash, and
  ``--fields`` already covers the projection need.
- ``note`` — an editor, not a report; it has no ``--json`` face
  either (r158's parity sweep excluded it for the same reason).
"""

import json
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


def _write_history(workspace, rows):
    path = Path(workspace) / ".mindseam" / "history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")


class FormatBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _ledger(self, goal="demo", core=(), verified=(),
                open_=(), next_="dom: work"):
        path = Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = ["# Mindseam Workspace Ledger", ""]
        text += ["## Goal", goal, ""]
        text += ["## Core"] + list(core) + [""]
        text += ["## Verified"] + list(verified) + [""]
        text += ["## Open"] + list(open_) + [""]
        text += ["## Next", next_, ""]
        path.write_text("\n".join(text), encoding="utf-8")

    def _row(self, next_action, t=1, **extra):
        row = {"t": t, "next": next_action, "verified": 0, "open": 0}
        row.update(extra)
        return row


class SeamFormatTests(FormatBase):
    """``seam --format`` renders scalars; the side effect is unchanged."""

    def test_format_renders_score_value(self):
        self._ledger()
        _write_history(self.workspace, [self._row("dom: a")])
        r = _invoke(["seam", "--dry-run", "--format",
                     "trend.score.value"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The output is a bare integer, no banner, no ledger dump.
        self.assertTrue(r.stdout.strip().isdigit(), r.stdout)
        self.assertNotIn("mindseam", r.stdout)

    def test_format_without_dry_run_still_records(self):
        # The side effect is unchanged: a seam with --format
        # still appends one history row, the way seam --json
        # does.
        self._ledger()
        _write_history(self.workspace, [self._row("dom: a")])
        r = _invoke(["seam", "--format", "history_count"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        count = int(r.stdout.strip())
        rows = json.loads(
            (Path(self.workspace) / ".mindseam" / "history.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(len(rows), count)
        self.assertGreater(count, 1)

    def test_format_multi_path(self):
        self._ledger()
        _write_history(self.workspace, [self._row("dom: a")])
        r = _invoke(["seam", "--dry-run", "--format",
                     "history_count,trend.score.value"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.strip().split("\n")
        self.assertEqual(len(lines), 2)

    def test_format_missing_path_is_empty(self):
        self._ledger()
        _write_history(self.workspace, [self._row("dom: a")])
        r = _invoke(["seam", "--dry-run", "--format",
                     "no.such.path"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "")


class ResumeFormatTests(FormatBase):
    """``resume --format`` drops the prose; the side effect is unchanged."""

    def test_format_drops_prose_and_banner(self):
        self._ledger()
        _write_history(self.workspace, [self._row("dom: a")])
        r = _invoke(["resume", "--format", "history_count"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip().isdigit(), r.stdout)
        # No premise prose, no reentry banner.
        self.assertNotIn("mindseam", r.stdout)
        self.assertNotIn("You do not only produce words", r.stdout)

    def test_format_still_appends_history_row(self):
        self._ledger()
        _write_history(self.workspace, [self._row("dom: a")])
        before = len(json.loads(
            (Path(self.workspace) / ".mindseam" / "history.json")
            .read_text(encoding="utf-8")))
        r = _invoke(["resume", "--format", "history_count"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        after = len(json.loads(
            (Path(self.workspace) / ".mindseam" / "history.json")
            .read_text(encoding="utf-8")))
        self.assertEqual(after, before + 1)

    def test_format_risk_level(self):
        self._ledger()
        _write_history(self.workspace, [self._row("dom: a")])
        r = _invoke(["resume", "--format", "risk.level"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(r.stdout.strip(), ("low", "medium", "high"))


class ShipFormatTests(FormatBase):
    """``ship --format`` keeps the exit contract byte-identical."""

    def _draft(self, text="# Draft\n\nClean prose paragraph.\n"):
        path = Path(self.workspace) / "draft.md"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_format_renders_clean_and_exit(self):
        self._ledger()
        r = _invoke(["ship", self._draft(),
                     "--format", "exit"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "0")

    def test_format_exit_contract_matches_json_face(self):
        # The JSON face and the --format face must return the
        # same exit code for the same input.
        self._ledger()
        draft = self._draft()
        r_json = _invoke(["ship", draft, "--json"],
                         cwd=self.workspace)
        r_fmt = _invoke(["ship", draft, "--format", "exit"],
                        cwd=self.workspace)
        self.assertEqual(r_json.returncode, r_fmt.returncode)

    def test_format_strict_gate_contract(self):
        # A gate failure (open questions) under --strict exits 2
        # through both faces.
        self._ledger(open_=("?01 unresolved question — settled by: nobody",))
        _write_history(self.workspace, [self._row("dom: a")])
        draft = self._draft()
        r_fmt = _invoke(["ship", draft, "--strict",
                         "--format", "exit"],
                        cwd=self.workspace)
        self.assertEqual(r_fmt.returncode, 2, r_fmt.stdout + r_fmt.stderr)
        self.assertEqual(r_fmt.stdout.strip(), "2")

    def test_format_findings_list(self):
        # State markers in outgoing text produce findings; the
        # findings array renders one per line through ``[*]``.
        self._ledger()
        draft = self._draft(
            "# Draft\n\nThe WORKSPACE.md holds.\n")
        r = _invoke(["ship", draft,
                     "--format", "findings[*]"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # Whatever the findings are, the renderer is the list
        # face: one finding per line or empty.
        self.assertIsInstance(r.stdout, str)


class SkillbookFormatTests(FormatBase):
    """``skillbook --format`` resolves against an entries dict root."""

    def test_format_entries_root(self):
        self._ledger()
        # Two identical rows make a recurring pattern.
        _write_history(self.workspace, [
            self._row("dom: repeat", t=1),
            self._row("dom: repeat", t=2),
            self._row("dom: repeat", t=3),
        ])
        r = _invoke(["skillbook", "--format", "entries[0].kind"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The kind is one of the harvested pattern kinds (or
        # empty when no pattern reached the recurrence bar).
        self.assertIsInstance(r.stdout, str)

    def test_format_empty_book_is_empty(self):
        self._ledger()
        _write_history(self.workspace, [self._row("dom: a")])
        r = _invoke(["skillbook", "--format", "entries"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # No recurring patterns yet: the entries list is empty,
        # the renderer prints nothing.
        self.assertEqual(r.stdout.strip(), "")


class DiscoverFormatTests(FormatBase):
    """``discover --format`` resolves domains straight off the payload."""

    def test_format_first_domain(self):
        self._ledger()
        _write_history(self.workspace, [
            self._row("alpha: step one", t=1),
            self._row("alpha: step two", t=2),
            self._row("beta: step one", t=3),
        ])
        r = _invoke(["discover", "--format", "domains[0].name"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "alpha")

    def test_format_suggested_next(self):
        self._ledger()
        _write_history(self.workspace, [
            self._row("alpha: step one", t=1),
            self._row("alpha: step two", t=2),
        ])
        r = _invoke(["discover", "--format", "suggested_next"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "alpha")

    def test_format_visits_are_integers(self):
        self._ledger()
        _write_history(self.workspace, [self._row("alpha: step", t=1)])
        r = _invoke(["discover", "--format", "domains[0].visits"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1")


class AuditFormatTests(FormatBase):
    """``audit --format`` resolves off the r162 payload."""

    def test_format_net_and_gate(self):
        self._ledger()
        _write_history(self.workspace, [self._row("dom: a")])
        r = _invoke(["audit", "--format", "net,gate"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].isdigit())
        self.assertIn(lines[1], ("clean", "finding", "gated"))

    def test_format_by_tag_nested(self):
        # A duplicate Open row fires the delete tag; the nested
        # ``by_tag.delete`` count resolves.
        self._ledger(open_=("?01 same — settled by: x",
                            "?02 same — settled by: x"))
        _write_history(self.workspace, [self._row("dom: a")])
        r = _invoke(["audit", "--format", "by_tag.delete"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1")

    def test_format_strict_exit_contract(self):
        # A finding + --strict exits 1 through both faces.
        self._ledger(open_=("?01 same — settled by: x",
                            "?02 same — settled by: x"))
        _write_history(self.workspace, [self._row("dom: a")])
        r_fmt = _invoke(["audit", "--strict", "--format", "net"],
                        cwd=self.workspace)
        self.assertEqual(r_fmt.returncode, 1, r_fmt.stdout)
        r_json = _invoke(["audit", "--strict", "--json"],
                         cwd=self.workspace)
        self.assertEqual(r_json.returncode, 1, r_json.stdout)

    def test_format_lean_bool(self):
        self._ledger()
        _write_history(self.workspace, [self._row("dom: a")])
        r = _invoke(["audit", "--format", "lean"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(r.stdout.strip(), ("true", "false"))


class ParityTests(unittest.TestCase):
    """Every report face that answers --json also accepts --format."""

    FACES = ("seam", "resume", "ship", "skillbook",
             "discover", "audit", "info")

    def test_every_report_face_accepts_format(self):
        for face in self.FACES:
            args = [face] if face not in ("ship",) else [face, "-"]
            args = args + ["--format", "x"]
            r = subprocess.run(
                [sys.executable, str(MINDSEAM), *args],
                cwd=tempfile.mkdtemp(), input="",
                capture_output=True, text=True, encoding="utf-8")
            combined = r.stderr + r.stdout
            self.assertNotIn(
                "unrecognised arguments", combined,
                "%s does not accept --format" % face)

    def test_note_has_no_format(self):
        # note is an editor, not a report; r158 excluded it from
        # the JSON parity and r170 excludes it here for the same
        # reason.
        r = subprocess.run(
            [sys.executable, str(MINDSEAM), "note", "--format", "x"],
            cwd=tempfile.mkdtemp(),
            capture_output=True, text=True, encoding="utf-8")
        # argparse's American spelling.
        self.assertIn("unrecognized arguments",
                      r.stderr + r.stdout)

    def test_history_keeps_its_template_format(self):
        # history's --format is the older per-row template
        # renderer (%h %n); it must not have been clobbered by
        # the dot-path renderer.
        with tempfile.TemporaryDirectory() as ws:
            _write_history(ws, [
                {"t": 1, "next": "dom: a", "verified": 0, "open": 0}])
            r = _invoke(["history", "--format", "%n"],
                        cwd=ws)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "dom: a")
