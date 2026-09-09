# -*- coding: utf-8 -*-
"""Round 180 guards: stable finding ids and the letter grade.

Borrowed from ``tokenhabit`` (a stdlib-only sibling that scans
Claude Code logs and reports wasteful habits): every finding
carries a short stable id — ``[H5-04]`` there, ``[D1]`` here —
and the report closes with a letter grade over a published
cut-point scale, so a host can gate on ``Grade: A`` without
parsing counts.

The id is ``<LETTER><N>``: the letter is the tag's stable
initial (D=delete, S=stdlib, Y=yagni, K=shrink, G=goal-stale,
N=next-stall, C=core-drift) and N is the 1-based occurrence
within the tag for this audit run. Ids are allocation
artifacts — they renumber as the ledger heals, exactly like
the ledger's own ``?NN`` / ``✓NN`` prefixes. The r162
(tag, what) fingerprint remains the stable cross-run key;
ids are assigned to the *full* finding set in
``audit_findings`` before ``--tag`` projection and baseline
marking, so a projection never renumbers.

The grade maps the fresh (non-baselined) finding count onto
A-F with published cuts (0/1/2/3/5/8): A = lean, F = ten or
more fresh findings. The grade reflects the projected fresh
set — the same set ``net`` and ``--strict`` gate on.
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


class FindingIdBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _ledger(self, goal="audit demo", core=(), verified=(),
                open_=(), next_="c1 — one"):
        path = Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = ["# Mindseam Workspace Ledger", ""]
        text += ["## Goal", goal, ""]
        text += ["## Core"] + list(core) + [""]
        text += ["## Verified"] + list(verified) + [""]
        text += ["## Open"] + list(open_) + [""]
        text += ["## Next", next_, ""]
        path.write_text("\n".join(text), encoding="utf-8")

    def _row(self, next_action, t=1):
        return {"t": t, "next": next_action, "verified": 0, "open": 0}


class FindingIdTests(FindingIdBase):
    """Each tag's letter and the per-tag numbering."""

    def test_delete_gets_d_prefix(self):
        self._ledger(open_=("?01 same — settled by: x",
                            "?02 same — settled by: x"))
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), [])
        ids = [f["id"] for f in findings if f["tag"] == "delete"]
        self.assertEqual(ids, ["D1"])

    def test_two_deletes_number_sequentially(self):
        self._ledger(
            open_=("?01 same — settled by: x",
                   "?02 same — settled by: x",
                   "?03 other — settled by: y",
                   "?04 other — settled by: y"))
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), [])
        ids = [f["id"] for f in findings if f["tag"] == "delete"]
        self.assertEqual(ids, ["D1", "D2"])

    def test_shrink_uses_k_letter(self):
        # S is taken by stdlib; shrink takes K. The letter map
        # is pinned so a silent re-lettering cannot break host
        # grep patterns.
        self._ledger()
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), [self._row("", t=1)])
        shrink = [f for f in findings if f["tag"] == "shrink"]
        self.assertEqual(shrink[0]["id"], "K1")

    def test_stdlib_uses_s_letter(self):
        self._ledger(verified=("✓01 first — verified by: brute force",
                               "✓02 first — verified by: brute force"))
        findings = mindseam.audit_findings(
            mindseam.read_ledger(), [])
        stdlib = [f for f in findings if f["tag"] == "stdlib"]
        self.assertEqual(stdlib[0]["id"], "S1")

    def test_ids_are_deterministic_across_calls(self):
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same — settled by: x",
                   "?02 same — settled by: x"))
        a = mindseam.audit_findings(mindseam.read_ledger(), [])
        b = mindseam.audit_findings(mindseam.read_ledger(), [])
        self.assertEqual([f["id"] for f in a], [f["id"] for f in b])

    def test_json_face_carries_ids(self):
        self._ledger(open_=("?01 same — settled by: x",
                            "?02 same — settled by: x"))
        r = _invoke(["audit", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertTrue(all("id" in f for f in payload["findings"]))
        self.assertEqual(payload["findings"][0]["id"], "D1")

    def test_text_face_prefixes_the_id(self):
        self._ledger(open_=("?01 same — settled by: x",
                            "?02 same — settled by: x"))
        r = _invoke(["audit"], cwd=self.workspace)
        self.assertIn("[D1] delete", r.stdout)
        self.assertIn("(evidence:", r.stdout)

    def test_tag_projection_keeps_full_set_numbering(self):
        # Ids are assigned to the full finding set; a projection
        # filters but never renumbers, so a host that greps
        # [S1] in a projected report refers to the same finding
        # class as in the full report.
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same — settled by: x",
                   "?02 same — settled by: x"))
        r = _invoke(["audit", "--tag", "stdlib"], cwd=self.workspace)
        self.assertIn("[S1]", r.stdout)


class GradeTests(FindingIdBase):
    """The A-F letter grade over the fresh set."""

    def test_grade_rubric(self):
        # Published cut points: 0=A, 1-2=B... wait, the cuts
        # tuple is (0,A),(1,B),(2,C),(3,D),(5,E),(8,F): count
        # <= threshold maps to the letter. 0->A, 1->B, 2->C,
        # 3-5->D, 6-8->E, 9+->F.
        expected = {
            0: "A", 1: "B", 2: "C", 3: "D", 4: "D", 5: "D",
            6: "E", 7: "E", 8: "E", 9: "F", 50: "F",
        }
        # The cut tuple is (<=0 -> A, <=1 -> B, <=2 -> C, <=3 -> D,
        # <=5 -> D, <=6 -> E, <=8 -> E, else F).
        for count, letter in expected.items():
            self.assertEqual(mindseam.audit_grade(count), letter,
                             "count %d" % count)

    def test_clean_audit_is_grade_a(self):
        self._ledger()
        r = _invoke(["audit", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["grade"], "A")
        self.assertEqual(payload["net"], 0)

    def test_text_face_shows_grade_line(self):
        self._ledger(open_=("?01 same — settled by: x",
                            "?02 same — settled by: x"))
        r = _invoke(["audit"], cwd=self.workspace)
        self.assertIn("Grade: B (1 fresh item)", r.stdout)

    def test_baselined_findings_do_not_lower_grade(self):
        # The grade reflects the fresh set: baselined debt is
        # acknowledged and does not count, the way tokenhabit
        # scores waste rather than raw volume.
        self._ledger(open_=("?01 same — settled by: x",
                            "?02 same — settled by: x"))
        bl = os.path.join(self.workspace, "bl.json")
        _invoke(["audit", "--baseline-write", bl], cwd=self.workspace)
        r = _invoke(["audit", "--baseline", bl, "--json"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["grade"], "A")
        self.assertEqual(payload["net"], 0)
        self.assertEqual(payload["baselined"], 1)

    def test_grade_reflects_tag_projection(self):
        # The grade is computed from the projected fresh set,
        # the same set net and --strict gate on.
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three",
                  "c4 — four", "c5 — five"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same — settled by: x",
                   "?02 same — settled by: x"))
        r = _invoke(["audit", "--tag", "delete", "--json"],
                    cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["net"], 1)
        self.assertEqual(payload["grade"], "B")

    def test_grade_agrees_with_net(self):
        self._ledger(
            core=("c1 — one", "c2 — two", "c3 — three"),
            verified=("✓01 first — verified by: brute force",
                      "✓02 first — verified by: brute force"),
            open_=("?01 same — settled by: x",
                   "?02 same — settled by: x"))
        r = _invoke(["audit", "--json"], cwd=self.workspace)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["grade"],
                         mindseam.audit_grade(payload["net"]))


class IdGradeCatalogTests(unittest.TestCase):

    def test_finding_ids_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("audit-finding-ids", ids)

    def test_grade_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("audit-grade", ids)

    def test_since_r180(self):
        entries = {e["id"]: e for e in mindseam._FEATURE_CATALOG}
        self.assertEqual(entries["audit-finding-ids"]["since"], "r180")
        self.assertEqual(entries["audit-grade"]["since"], "r180")
