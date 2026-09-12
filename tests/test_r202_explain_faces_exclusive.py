# -*- coding: utf-8 -*-
"""Round 202 guards: the explain faces and seam's renderer pair are exclusive.

Three faces kept the r188/r197/r199/r200/r201 silent-drop shape:

``audit --explain`` short-circuits before the audit runs, so combined
calls exited 0 while the instruction vanished — probe: ``--explain
delete --baseline-write X`` wrote nothing, ``--intensity banana``
bypassed r185's validation, ``--at 3`` skipped its range check. The
refusal keeps the r171 unknown-tag check as its predecessor and
leaves ``--json`` as explain's machine face.

``info --explain`` is the same branch inside mode_info, and it was
missing from the r200 face set: ``--index --explain`` let the index
face win, ``--format``/``--field`` rendered nothing, and the payload
blocks (--manifest/--mtime/--health/...) were dropped silently.
Face-vs-face and renderer clashes now refuse in the dispatcher
(explain joined the set as the sixth face); the remaining payload
flags refuse inside mode_info.

``seam --quiet --format``: the format branch wins and quiet is
dropped without a word — the r197/r198 renderer-pair doctrine
arriving on seam's two non-JSON renderers, refused before the
stdin read and before any history append. ``--json`` stays the
machine face everything rides, so ``seam --quiet --json`` keeps
printing the payload.
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


class _WorkspaceCase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        rows = [{"t": i + 1, "next": "dom: step %d" % i,
                 "verified": i + 1, "open": 0} for i in range(6)]
        (self.ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)


class AuditExplainExclusiveTests(_WorkspaceCase):

    def _refused(self, *flags):
        r = _invoke(["audit", "--explain", "delete"] + list(flags),
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("runs no audit", r.stderr)
        self.assertEqual(r.stdout, "")
        return r

    def test_strict_refused(self):
        self.assertIn("--strict", self._refused("--strict").stderr)

    def test_intensity_refused_even_valid(self):
        # The combination is invalid as a combination before the
        # value's own validation matters (r201 precedent).
        r = self._refused("--intensity", "lite")
        self.assertIn("--intensity", r.stderr)

    def test_tag_refused(self):
        self.assertIn("--tag", self._refused("--tag", "delete").stderr)

    def test_since_refused(self):
        self.assertIn("--since", self._refused("--since", "3600").stderr)

    def test_until_refused(self):
        self.assertIn("--until", self._refused("--until", "60").stderr)

    def test_at_refused(self):
        self.assertIn("--at", self._refused("--at", "3").stderr)

    def test_baseline_read_refused(self):
        self.assertIn("--baseline",
                      self._refused("--baseline", "bl.json").stderr)

    def test_baseline_write_refused_and_never_writes(self):
        bl = Path(self.workspace) / "bl.json"
        bl.write_text(json.dumps([{"tag": "sentinel"}]),
                      encoding="utf-8")
        self._refused("--baseline-write", str(bl))
        self.assertEqual(
            json.loads(bl.read_text(encoding="utf-8")),
            [{"tag": "sentinel"}])

    def test_format_refused(self):
        self.assertIn("--format",
                      self._refused("--format", "tag").stderr)

    def test_many_flags_all_named(self):
        r = self._refused("--strict", "--at", "2", "--format", "tag")
        for name in ("--strict", "--at", "--format"):
            self.assertIn(name, r.stderr)

    def test_unknown_tag_still_refuses_first(self):
        # r171's contract keeps priority: an invalid --explain value
        # reports its own precise error before the combination clash.
        r = _invoke(["audit", "--explain", "banana", "--strict"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a recognised audit tag", r.stderr)

    def test_json_face_still_composes(self):
        # r171 pinned explain --json; it stays legal.
        r = _invoke(["audit", "--explain", "next-stall", "--json"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["tag"], "next-stall")

    def test_explain_alone_unchanged(self):
        r = _invoke(["audit", "--explain", "delete"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("audit explain delete", r.stdout)


class InfoExplainExclusiveTests(_WorkspaceCase):

    def test_index_explain_pair_refused_in_dispatcher(self):
        # explain joined the r200 face set: face-vs-face refuses in
        # main(), naming both.
        r = _invoke(["info", "--index", "--explain", "info-memory"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("mutually exclusive info faces", r.stderr)
        self.assertIn("--explain", r.stderr)

    def test_format_renderer_refused_in_dispatcher(self):
        r = _invoke(["info", "--explain", "info-memory", "--format",
                     "id"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--format", r.stderr)

    def test_field_renderer_refused_in_dispatcher(self):
        r = _invoke(["info", "--explain", "info-memory", "--field",
                     "id"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--field", r.stderr)

    def test_manifest_refused_in_mode(self):
        r = _invoke(["info", "--explain", "info-memory", "--manifest"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("builds no payload", r.stderr)
        self.assertIn("--manifest", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_health_and_workspace_id_named_together(self):
        r = _invoke(["info", "--explain", "info-memory", "--health",
                     "--workspace-id"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--health", r.stderr)
        self.assertIn("--workspace-id", r.stderr)

    def test_warnings_only_text_human_all_refuse(self):
        for flag in ("--warnings-only", "--text", "--human", "--mtime",
                     "--changed", "--content-hash", "--features",
                     "--aliases"):
            r = _invoke(["info", "--explain", "info-memory", flag],
                        self.workspace)
            self.assertEqual(r.returncode, 2, flag)
            self.assertIn(flag, r.stderr)

    def test_unknown_id_still_refuses_first(self):
        r = _invoke(["info", "--explain", "nope", "--manifest"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a recognised feature id", r.stderr)

    def test_json_face_still_composes(self):
        # r172's machine face stays legal.
        r = _invoke(["info", "--explain", "info-memory", "--json"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["id"], "info-memory")

    def test_explain_alone_unchanged(self):
        r = _invoke(["info", "--explain", "info-memory"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)


class SeamQuietFormatExclusiveTests(_WorkspaceCase):

    def test_quiet_format_pair_refused(self):
        r = _invoke(["seam", "--quiet", "--format",
                     "trend.score.value"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("mutually exclusive renderers", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_refusal_appends_no_history_row(self):
        # The refusal lands before any seam work: a real seam would
        # append a row, so the count staying at 6 proves the branch
        # ran ahead of the append (and the stdin read).
        rows = json.loads(
            (self.ledger / "history.json").read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 6)
        _invoke(["seam", "--quiet", "--format", "trend.score.value"],
                self.workspace)
        after = json.loads(
            (self.ledger / "history.json").read_text(encoding="utf-8"))
        self.assertEqual(len(after), 6)

    def test_quiet_alone_unchanged(self):
        r = _invoke(["seam", "--quiet"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_format_alone_unchanged(self):
        r = _invoke(["seam", "--dry-run", "--format",
                     "trend.score.value"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip().isdigit())

    def test_quiet_rides_json_unchanged(self):
        # The r198 doctrine: --json is the machine face everything
        # rides. Pinning that seam --quiet --json still prints the
        # payload (quiet adds nothing to suppress under JSON).
        r = _invoke(["seam", "--quiet", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("trend", json.loads(r.stdout))

    def test_catalog_entries(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        for name in ("audit-explain-face-exclusive",
                     "info-explain-face-exclusive",
                     "seam-quiet-format-exclusive"):
            self.assertIn(name, ids)
            entry = next(e for e in mindseam._FEATURE_CATALOG
                         if e["id"] == name)
            self.assertEqual(entry["since"], "r202")
            self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
