# -*- coding: utf-8 -*-
"""Round 175 guards: info --index-since filters the index by round.

Borrowed from ``tldr --list`` / ``man -k`` / ``git log
--since``: an index is most useful when a host can filter
it by recency. r174 gave a flat ``info.<feature-id>`` per
line; r175 lets a host pass ``--index-since r172`` to
limit the list to features introduced in r172 or later,
the way ``pip list --uptodate`` filters by freshness.

The filter is inclusive on the round tag (``r172`` keeps
everything from r172 onward), the way ``git log
--since=2024-01-01`` keeps the day's commits. An invalid
round tag refuses with exit 2 on stderr, the way the
r172 mutual-exclusivity check refuses ``--field`` plus
``--format``.
"""

import json
import os
import re
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


class IndexSinceContractTests(unittest.TestCase):
    """``--index-since`` is inclusive on the round tag."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_index_since_runs_in_empty_workspace(self):
        # Same contract as ``--index`` itself: works in a
        # fresh empty workspace, the way ``git log
        # --since`` works before ``git init``.
        r = _invoke(["info", "--index", "--index-since", "r172"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertGreater(len(r.stdout.strip()), 0)

    def test_index_since_does_not_create_workspace(self):
        _invoke(["info", "--index", "--index-since", "r172"],
                 cwd=self.workspace)
        self.assertFalse(
            (Path(self.workspace) / ".mindseam").exists())

    def test_index_since_includes_features_at_round(self):
        # r172 keeps the r172 features (inclusive on the
        # round tag).
        r = _invoke(["info", "--index", "--index-since", "r172"],
                    cwd=self.workspace)
        ids = [l[len("info."):] for l in r.stdout.splitlines()
               if l.startswith("info.")]
        self.assertIn("info-field", ids)

    def test_index_since_excludes_features_before_round(self):
        # r162 keeps r162 and later, excludes everything
        # before r162 (including r156 audit, r157 history,
        # r158 report-json-faces, r159 audit-facets /
        # tag-projection, r160 audit-evidence-link, r161
        # audit-window-at).
        r = _invoke(["info", "--index", "--index-since", "r162"],
                    cwd=self.workspace)
        ids = [l[len("info."):] for l in r.stdout.splitlines()
               if l.startswith("info.")]
        # Anything before r162 must be excluded.
        self.assertNotIn("info-warnings-only", ids)  # r156
        self.assertNotIn("info-version", ids)        # r156
        self.assertNotIn("history-filter", ids)      # r157
        self.assertNotIn("history-human", ids)       # r157
        self.assertNotIn("report-json-faces", ids)   # r158
        self.assertNotIn("audit-facets", ids)        # r159
        self.assertNotIn("audit-tag-projection", ids) # r159
        self.assertNotIn("audit-evidence-link", ids)  # r160
        self.assertNotIn("audit-window-at", ids)     # r161
        # r162 itself is included (inclusive on the
        # round tag).
        self.assertIn("info-field", ids)            # r172  # r172 >= r162
        # r162 audit-baseline is included.
        self.assertIn("audit-baseline", ids)

    def test_index_since_filters_against_catalog(self):
        # The filtered output is a subset of the full
        # index, the way ``--since`` filters a log.
        full = _invoke(["info", "--index"],
                       cwd=self.workspace).stdout.splitlines()
        recent = _invoke(["info", "--index", "--index-since", "r170"],
                          cwd=self.workspace).stdout.splitlines()
        # r170 keeps the features introduced in r170 or
        # later (r170 report-format-faces, r171 audit-explain,
        # r172 info-field, r173 skill-example-runner, r174
        # note-from-stdin + info-index, r175 info-index-since,
        # r176 info-index-until, r177 note-dry-run, r178
        # resume-dry-run, r179 stale-write-lock-recovery, r180
        # audit-finding-ids + audit-grade, r181
        # health-velocity-trend, r187 skillbook-staleness, r188
        # audit-at-window-exclusive). The count is stable
        # because the catalog is static; it moves only when a
        # new round lands, and the move is a deliberate pin
        # update, the way the r167 catalog count moved when
        # r169 landed.
        self.assertEqual(len(recent), 16)
        for line in recent:
            self.assertIn(line, full)

    def test_index_since_lines_are_sorted(self):
        # Stability: the filtered index is sorted, the
        # way the full index is sorted.
        r = _invoke(["info", "--index", "--index-since", "r170"],
                    cwd=self.workspace)
        lines = [l for l in r.stdout.splitlines() if l]
        self.assertEqual(lines, sorted(lines))

    def test_index_since_invalid_round_refused(self):
        # An invalid round tag refuses with exit 2 on stderr,
        # the way r172's --field mutual-exclusivity check
        # refuses. The error names the expected format so
        # the host can recover.
        r = _invoke(["info", "--index", "--index-since", "bad"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("round tag", r.stderr)
        self.assertIn("r156", r.stderr)

    def test_index_since_non_round_string_refused(self):
        # Numbers without the ``r`` prefix are also refused.
        r = _invoke(["info", "--index", "--index-since", "172"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("round tag", r.stderr)

    def test_index_since_round_zero_works(self):
        # ``r0`` is a valid (but absurd) round tag. The
        # filter keeps everything, the way ``--since=epoch``
        # keeps every log entry.
        r = _invoke(["info", "--index", "--index-since", "r0"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        full_count = len(
            [l for l in _invoke(["info", "--index"],
                                  cwd=self.workspace)
                .stdout.splitlines() if l])
        recent_count = len(
            [l for l in r.stdout.splitlines() if l])
        self.assertEqual(full_count, recent_count)


class IndexSinceCatalogTests(unittest.TestCase):
    """The catalog registers the new capability."""

    def test_index_since_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("info-index-since", ids)

    def test_index_since_since_round_is_r175(self):
        for entry in mindseam._FEATURE_CATALOG:
            if entry["id"] == "info-index-since":
                self.assertEqual(entry["since"], "r175")
                self.assertTrue(entry["default"])
                return
        self.fail("info-index-since entry missing from catalog")
