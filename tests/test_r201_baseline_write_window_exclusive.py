# -*- coding: utf-8 -*-
"""Round 201 guards: audit --baseline-write and the window flags are exclusive.

A baseline is a commitment to the whole ledger state — r182 already
refuses to let the ``--tag`` projection reshape what gets written.
The time window (``--since``/``--until``) and the historical slice
(``--at``) narrow the *history* the facet detectors see, which
changes the findings themselves: a shrink finding names the rows its
slice contains, so the sliced fingerprint never matches the full
audit's. The damage is invisible at write time — the file is written,
counted as recorded — and a chained ``--baseline-write X --baseline X``
run even reports ``gate: clean`` while the next full audit still
exits 1 (probe: net 0 in the chain, rc 1 after).

r201 refuses the combination with exit 2 before any ledger read or
write, naming the offending flag(s) — the r188 family (``--at`` with
the window), extended to the write side. Composition that does not
touch the write path is untouched: baseline *reads* still compose
with the window (a viewing narrowing), the tag projection still
composes with the write (r182's doctrine), and an unwindowed
``--baseline-write`` behaves exactly as before.
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


class BaselineWriteWindowExclusivityTests(unittest.TestCase):

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
        self.baseline = Path(self.workspace) / "bl.json"

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_write_with_since_is_refused(self):
        r = _invoke(["audit", "--baseline-write", str(self.baseline),
                     "--since", "3600"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--baseline-write composes with none of",
                      r.stderr)
        self.assertIn("--since", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_write_with_until_is_refused(self):
        r = _invoke(["audit", "--baseline-write", str(self.baseline),
                     "--until", "60"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--until", r.stderr)

    def test_write_with_at_is_refused(self):
        r = _invoke(["audit", "--baseline-write", str(self.baseline),
                     "--at", "2"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--at", r.stderr)

    def test_write_with_all_three_names_all_three(self):
        r = _invoke(["audit", "--baseline-write", str(self.baseline),
                     "--at", "2", "--since", "3600", "--until", "60"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--at", r.stderr)
        self.assertIn("--since", r.stderr)
        self.assertIn("--until", r.stderr)

    def test_refusal_writes_no_file(self):
        _invoke(["audit", "--baseline-write", str(self.baseline),
                 "--at", "2"], self.workspace)
        self.assertFalse(self.baseline.exists())

    def test_refusal_leaves_existing_baseline_untouched(self):
        # Pre-seed with sentinel content: had the code proceeded to
        # the write, the file would have been replaced. Byte-identity
        # proves the refusal lands before the write path.
        self.baseline.write_text(json.dumps([{"tag": "sentinel"}]),
                                 encoding="utf-8")
        r = _invoke(["audit", "--baseline-write", str(self.baseline),
                     "--since", "3600"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(
            json.loads(self.baseline.read_text(encoding="utf-8")),
            [{"tag": "sentinel"}])

    def test_refusal_beats_out_of_range_check(self):
        # The combination is invalid as a combination before any
        # single flag's own validation matters: --at 99 is also out
        # of range here, yet the r201 message names the clash.
        r = _invoke(["audit", "--baseline-write", str(self.baseline),
                     "--at", "99"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("composes with none of", r.stderr)
        self.assertNotIn("out of range", r.stderr)

    def test_at_window_clash_still_refuses_first(self):
        # r188's own refusal (the window flags against --at) keeps
        # priority when all three collide, before the write's clash.
        r = _invoke(["audit", "--baseline-write", str(self.baseline),
                     "--at", "3", "--since", "3600"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--at 3 composes with neither", r.stderr)

    def test_json_face_refuses_before_any_payload(self):
        r = _invoke(["audit", "--baseline-write", str(self.baseline),
                     "--since", "3600", "--json"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_unwindowed_write_still_works(self):
        r = _invoke(["audit", "--baseline-write", str(self.baseline),
                     "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.baseline.exists())
        json.loads(self.baseline.read_text(encoding="utf-8"))

    def test_baseline_read_still_composes_with_window(self):
        # The read side is a viewing narrowing, not a commitment:
        # --since with --baseline stays legal.
        _invoke(["audit", "--baseline-write", str(self.baseline)],
                self.workspace)
        r = _invoke(["audit", "--since", "3600", "--baseline",
                     str(self.baseline), "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_write_still_composes_with_tag_projection(self):
        # r182's doctrine: the --tag projection is ignored by the
        # write and stays composable with it.
        r = _invoke(["audit", "--tag", "shrink", "--baseline-write",
                     str(self.baseline)], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.baseline.exists())

    def test_chained_windowed_run_no_longer_lies_clean(self):
        # The probe scenario: a chained write+gate run used to
        # report gate=clean while the next full run exited 1. The
        # chain is now refused outright.
        r = _invoke(["audit", "--since", "3000", "--baseline-write",
                     str(self.baseline), "--baseline", str(self.baseline)],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("clean", r.stdout)

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("audit-baseline-write-window-exclusive", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "audit-baseline-write-window-exclusive")
        self.assertEqual(entry["since"], "r201")
        self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
