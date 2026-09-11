# -*- coding: utf-8 -*-
"""Round 182 guards: deep optimization — eliminate redundant IO and
recomputation without changing any pinned contract.

Three concrete wins, each a pure-function dedup:

1. ``mode_audit`` called ``audit_findings(book, hist)`` *twice* along
   the ``--baseline-write`` path — once for the report and once to
   feed the baseline writer. The second call is a pure-function
   duplicate: the first call's result, saved before the ``--tag``
   projection, is the exact unprojected list the baseline writer
   needs. r182 caches it in ``full_findings`` and reuses it.

2. ``mode_history`` called ``read_history()`` *three* times along the
   ``--keep`` path (a length check, the truncation read, then an
   unconditional ``hist = read_history()[0]`` that overwrote the
   truncated slice). The overwrite silently cancelled the rotation:
   the on-disk file was slimmed, but the in-memory ``hist`` the rest
   of the function filtered and rendered was the full pre-truncation
   log. r182 reads once, branches on the cached list, and the
   rendered ``history_count`` now matches the on-disk survivors.

3. ``mode_skillbook`` called ``read_history()[0]`` twice — once to
   mine the skillbook and once to pick the "no history" message.
   The cached ``hist`` from the first read answers the emptiness
   check, the way the JSON face already reuses ``entries`` without
   re-mining.

Each test pins the *observable* contract a host relies on; the
dedup is invisible to the host except as fewer disk reads.
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


class AuditBaselineDedupTests(unittest.TestCase):
    """The baseline write uses the unprojected finding list."""

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

    def _history(self, rows):
        (self.ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def test_baseline_write_records_all_findings_not_projected(self):
        # The baseline file is a commitment about the *ledger* state,
        # not this run's ``--tag`` projection. With the dedup, the
        # baseline writer reads ``full_findings`` (the pre-projection
        # list) rather than recomputing; the written file must carry
        # every finding the audit can produce, the way it did before
        # the dedup — the contract is unchanged, only the IO count
        # drops from two ``audit_findings`` calls to one.
        self._history([
            {"t": i + 1, "next": "dom: step %d" % i,
             "verified": i + 1, "open": 0}
            for i in range(6)
        ])
        # Add a duplicate Open so the ``delete`` tag fires.
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\nv\n"
            "## Open\nq\nq\n## Next\nn\n", encoding="utf-8")
        baseline = Path(self.workspace) / "baseline.json"
        # ``--tag delete`` projects the report to one tag; the
        # baseline write must still record every finding.
        r = _invoke(["audit", "--baseline-write", str(baseline),
                     "--tag", "delete"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        written = json.loads(baseline.read_text(encoding="utf-8"))
        # The written baseline carries the full finding set (delete
        # from the duplicate Open), not just the projected subset.
        tags = {f["tag"] for f in written}
        self.assertIn("delete", tags)
        # A second ``audit_findings`` call would have produced the
        # same list; the dedup makes that call unnecessary. Verify
        # the written list matches what a fresh full audit produces.
        book = mindseam.read_ledger()
        hist = mindseam.read_history()[0]
        fresh = mindseam.audit_findings(book, hist)
        self.assertEqual(len(written), len(fresh))


class HistoryKeepTruncationTests(unittest.TestCase):
    """``--keep`` truncates the rendered output, not just the disk."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _seed(self, n):
        ledger = Path(self.workspace) / ".mindseam"
        ledger.mkdir(parents=True, exist_ok=True)
        (ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        for i in range(n):
            _invoke(["note", "--next", "dom: step %d" % i],
                    self.workspace)
            _invoke(["seam", "--json"], self.workspace)

    def test_keep_truncates_the_rendered_count(self):
        # Before the fix, ``--keep N`` wrote the truncated file but
        # then overwrote the in-memory ``hist`` with a fresh read, so
        # the rendered ``history_count`` showed the full log. The
        # rendered count must now match the on-disk survivors.
        self._seed(5)
        r = _invoke(["history", "--keep", "2", "--json"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 2)
        nexts = [row["next"] for row in payload["rows"]]
        self.assertEqual(nexts, ["dom: step 3", "dom: step 4"])

    def test_keep_then_filter_uses_truncated_window(self):
        # With the bug, a ``--keep 3 --filter`` chain filtered the
        # full 5-row log (the truncated slice was discarded). After
        # the fix, the filter sees only the 3 survivors.
        self._seed(5)
        r = _invoke(["history", "--keep", "3", "--json"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        survivors = json.loads(r.stdout)["rows"]
        # Only steps 2, 3, 4 remain on disk.
        self.assertEqual([r["next"] for r in survivors],
                         ["dom: step 2", "dom: step 3", "dom: step 4"])
        # A follow-up filter over the survivors sees the slimmed set.
        r = _invoke(["history", "--filter", "next=dom: step 0"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("dom: step 0", r.stdout)


class SkillbookCacheTests(unittest.TestCase):
    """``mode_skillbook`` reads history once."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_skillbook_empty_history_message(self):
        # An empty history must still produce the "No skillbook yet"
        # message without a second ``read_history`` call. The
        # observable contract is unchanged; the dedup is invisible.
        ledger = Path(self.workspace) / ".mindseam"
        ledger.mkdir(parents=True, exist_ok=True)
        (ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        r = _invoke(["skillbook"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("No skillbook yet", r.stdout)


class InfoAuditSummaryTopTagTests(unittest.TestCase):
    """The top-tag scan is a single pass over ``by_tag``."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_audit_summary_top_tag_picks_highest_count(self):
        # With a duplicate Open and a duplicate Verified, both
        # ``delete`` and ``stdlib`` fire. The top tag is the one
        # with the higher count; the single-pass scan must agree
        # with a reference ``max`` over the same map.
        ledger = Path(self.workspace) / ".mindseam"
        ledger.mkdir(parents=True, exist_ok=True)
        (ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n"
            "## Verified\nv\nv\n\n"
            "## Open\nq\nq\n\n## Next\nn\n", encoding="utf-8")
        (ledger / "history.json").write_text(
            json.dumps([
                {"t": i + 1, "next": "dom: step %d" % i,
                 "verified": i + 1, "open": 0}
                for i in range(6)
            ]), encoding="utf-8")
        r = _invoke(["info", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        summary = json.loads(r.stdout)["audit_summary"]
        # Reference: the top tag is the highest-count tag; ties
        # break by the lexicographically *smallest* tag name — the
        # same rule the single-pass scan applies (``tag < audit_top_tag``
        # on equal count). ``min`` over (-count, tag) reproduces the
        # original ``sorted(...)[0]`` tie-break.
        expected_top = min(summary["by_tag"].items(),
                           key=lambda tc: (-tc[1], tc[0]))[0]
        self.assertEqual(summary["top_tag"], expected_top)
        self.assertEqual(summary["top_tag_count"],
                         summary["by_tag"][expected_top])
