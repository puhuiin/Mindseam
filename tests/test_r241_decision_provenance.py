# -*- coding: utf-8 -*-
"""Round 241 guards: decision payloads carry their versioned inputs.

The Jev/TypeSafe survey (2026-09-19) surfaced one transferable rule
that needs no network dependency: its calibration guidance — "pin a
versioned model ID when thresholds depend on model behavior, and log
the version returned in each response, not only the alias sent in the
request". Mindseam publishes cut points (the audit grade scale, the
health letters) that a host reads as verdicts, and until now the
payload never said which rev produced them: a host that recorded
``grade: C`` could not tell whether the scale moved or the ledger did.

r241 makes the decision inputs inspectable:

- ``model_provenance()`` returns id / rev / grade_scale /
  health_bands / named thresholds, read at call time so a test host
  can pin the rev it asserts against.
- ``HEALTH_BANDS`` lifts the health letter ladder out of ``grade()``
  into a published constant, the way ``AUDIT_GRADE_CUTS`` already was
  (the same shape r180 gave the audit letter).
- ``audit --json``/``--format``, ``seam --json``/``--format`` and
  ``resume --json``/``--format`` all carry a ``model`` block.

No behaviour changed: ``grade()`` returns the same letters for every
score (pinned band by band, including the 39/40 and 59/60 boundaries),
and the block is additive.
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


class ProvenanceShapeTests(unittest.TestCase):

    def test_provenance_is_json_serializable(self):
        prov = mindseam.model_provenance()
        # A payload block that cannot round-trip is a broken machine
        # face; assert the whole dict, not just the top keys.
        self.assertEqual(json.loads(json.dumps(prov)), prov)

    def test_provenance_names_id_and_rev(self):
        prov = mindseam.model_provenance()
        self.assertEqual(prov["id"], mindseam.PROVENANCE_ID)
        self.assertEqual(prov["rev"], mindseam.__version__)

    def test_grade_scale_matches_the_audit_cuts(self):
        # The published scale must be the one audit_grade actually
        # uses, or the block lies about its own policy. Each cut is
        # an inclusive CEILING: a count equal to the threshold gets
        # that letter, and one more gets the next one down.
        prov = mindseam.model_provenance()
        self.assertEqual([tuple(pair) for pair in prov["grade_scale"]],
                         list(mindseam.AUDIT_GRADE_CUTS))
        for threshold, letter in mindseam.AUDIT_GRADE_CUTS:
            self.assertEqual(mindseam.audit_grade(threshold), letter)
        self.assertEqual(mindseam.audit_grade(9), "F")

    def test_health_bands_match_grade(self):
        prov = mindseam.model_provenance()
        for threshold, letter in prov["health_bands"]:
            self.assertEqual(mindseam.grade(threshold), letter)
            self.assertEqual(mindseam.grade(threshold + 1), letter)

    def test_thresholds_are_the_named_constants(self):
        prov = mindseam.model_provenance()
        self.assertEqual(prov["thresholds"]["skillbook_min_recurrence"],
                         mindseam.SKILLBOOK_MIN_RECURRENCE)
        self.assertEqual(prov["thresholds"]["stall_run"],
                         mindseam.STALL_RUN)
        self.assertEqual(prov["thresholds"]["resume_gap"],
                         mindseam.RESUME_GAP)

    def test_provenance_reads_at_call_time(self):
        # Not frozen at import: a host (or test) that pins a different
        # rev sees the difference, which is the whole point of logging
        # the version rather than the alias.
        saved = mindseam.__version__
        try:
            mindseam.__version__ = "0.0.0-test"
            self.assertEqual(mindseam.model_provenance()["rev"],
                             "0.0.0-test")
        finally:
            mindseam.__version__ = saved
        self.assertEqual(mindseam.model_provenance()["rev"], saved)


class GradeBehaviourUnchangedTests(unittest.TestCase):

    def test_every_band_edge_is_byte_identical(self):
        # The if-ladder this replaced is pinned here so the constant
        # can never drift the letters.
        expected = {
            100: "A", 90: "A", 89: "B", 75: "B", 74: "C", 60: "C",
            59: "D", 40: "D", 39: "F", 0: "F",
        }
        for score, letter in expected.items():
            self.assertEqual(mindseam.grade(score), letter, score)


class PayloadProvenanceTests(unittest.TestCase):

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

    def _json(self, *args):
        r = invoke_cli(self.workspace, list(args) + ["--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_audit_payload_carries_model(self):
        payload = self._json("audit")
        self.assertIn("model", payload)
        self.assertEqual(payload["model"]["id"], mindseam.PROVENANCE_ID)
        self.assertIn("grade_scale", payload["model"])

    def test_seam_payload_carries_model(self):
        payload = self._json("seam", "--dry-run")
        self.assertIn("model", payload)
        self.assertEqual(payload["model"]["rev"], mindseam.__version__)

    def test_resume_payload_carries_model(self):
        payload = self._json("resume", "--dry-run")
        self.assertIn("model", payload)
        self.assertIn("health_bands", payload["model"])

    def test_format_face_renders_provenance(self):
        for command in (["audit"], ["seam", "--dry-run"],
                        ["resume", "--dry-run"]):
            r = invoke_cli(self.workspace,
                           command + ["--format", "model.id"])
            self.assertEqual(r.returncode, 0, (command, r.stderr))
            self.assertEqual(r.stdout.strip(), mindseam.PROVENANCE_ID)

    def test_provenance_matches_the_live_scale(self):
        # The payload's scale must equal the one in force, or a host
        # calibrating against it is calibrating against a ghost.
        payload = self._json("audit")
        self.assertEqual([tuple(p) for p in payload["model"]["grade_scale"]],
                         list(mindseam.AUDIT_GRADE_CUTS))


if __name__ == "__main__":
    unittest.main()
