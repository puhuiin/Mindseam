# -*- coding: utf-8 -*-
"""Round 204 guards: seam's machine face carries a boolean dry_run.

The plan trio — note (r177), seam (r183), resume (r178) — all
preview without writing. resume's JSON face tells a host so as a
machine field: ``"dry_run": bool(dry_run)``, always present. seam
only ever said it in prose: the ``dry-run: history.json was not
updated`` warning that r183 pinned and r203 re-tensed. A host
writing one gate across the two plan faces (``if payload["dry_run"]:
...``) got a clean boolean from resume and a KeyError from seam —
the machine face buried the very fact the face exists to carry.

r204 adds the missing field, following the resume convention
exactly: always present, False on a real run. It is purely
additive — the warnings string rides on unchanged, and the text
face is untouched.
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


def _invoke(args, cwd, stdin=None):
    return invoke_cli(cwd, args, stdin=stdin)


class SeamDryRunMachineMarkerTests(unittest.TestCase):

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
                 "verified": i + 1, "open": 0} for i in range(3)]
        (self.ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _payload(self, *flags):
        r = _invoke(["seam"] + list(flags) + ["--json"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_preview_carries_true(self):
        self.assertIs(self._payload("--dry-run")["dry_run"], True)

    def test_real_run_carries_false_not_absent(self):
        # The resume convention (r178): the field is ALWAYS present.
        # Absent-on-real would push every host back to
        # payload.get("dry_run") and re-open the ambiguity the
        # boolean exists to close.
        payload = self._payload()
        self.assertIn("dry_run", payload)
        self.assertIs(payload["dry_run"], False)

    def test_format_face_renders_the_marker(self):
        # --format rides the same payload: a one-token plan check
        # costs the host no JSON parsing.
        r = _invoke(["seam", "--dry-run", "--format", "dry_run"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "true")

    def test_warnings_string_still_rides(self):
        # Additive only: the r183/r203 prose contract is unchanged.
        joined = " ".join(self._payload("--dry-run")["warnings"])
        self.assertIn("dry-run: history.json was not updated", joined)

    def test_stdin_preview_flags_agree(self):
        # The boolean, the prose marker, and the conditional-tense
        # count all tell the same story in one payload.
        r = _invoke(["seam", "--dry-run", "--from-stdin", "--json"],
                    self.workspace, stdin="a\nb\n")
        payload = json.loads(r.stdout)
        self.assertIs(payload["dry_run"], True)
        joined = " ".join(payload["warnings"])
        self.assertIn("would be recorded", joined)
        self.assertIn("dry-run: history.json was not updated", joined)

    def test_quiet_face_payload_key_parity_untouched(self):
        # The seam quiet/verbose payload key parity pins (r128-era)
        # compared the JSON faces; the new key lands on both by
        # construction — assert cross-run parity of the key set.
        dry = set(self._payload("--dry-run"))
        real = set(self._payload())
        self.assertEqual(dry, real)
        self.assertIn("dry_run", dry)

    def test_resume_convention_holds_side_by_side(self):
        # The whole point of r204: one gate shape across the plan
        # faces. Both payloads answer payload["dry_run"] directly.
        d = self._payload("--dry-run")["dry_run"]
        r = _invoke(["resume", "--dry-run", "--json"], self.workspace)
        self.assertIs(json.loads(r.stdout)["dry_run"], True)
        self.assertIs(d, True)

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("seam-dry-run-machine-marker", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "seam-dry-run-machine-marker")
        self.assertEqual(entry["since"], "r204")
        self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
