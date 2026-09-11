# -*- coding: utf-8 -*-
"""Round 176 guards: info --index-until, the window's upper bound.

r175 gave the index a lower bound (``--index-since r172``
keeps everything from r172 onward). r176 completes the
bracket with ``--index-until r174`` — features introduced
in r174 or earlier — the way ``git log --since=... --until=...``
brackets a date window and ``journalctl --since --until``
brackets a time window.

The two flags compose: ``--index-since r172 --index-until
r174`` returns exactly the features introduced in the
closed interval [r172, r174]. An inverted window (since
after until) refuses with exit 2, the way ``sort -k2 -k1``
with contradictory keys is a caller error, not a silent
empty result.
"""

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


class IndexUntilContractTests(unittest.TestCase):
    """``--index-until`` is inclusive on the round tag."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_index_until_runs_in_empty_workspace(self):
        # Same static-data contract as --index / --index-since.
        r = _invoke(["info", "--index", "--index-until", "r160"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertGreater(len(r.stdout.strip()), 0)

    def test_index_until_does_not_create_workspace(self):
        _invoke(["info", "--index", "--index-until", "r160"],
                 cwd=self.workspace)
        self.assertFalse(
            (Path(self.workspace) / ".mindseam").exists())

    def test_index_until_excludes_features_after_round(self):
        # r160 keeps everything up to and including r160.
        r = _invoke(["info", "--index", "--index-until", "r160"],
                    cwd=self.workspace)
        ids = [l[len("info."):] for l in r.stdout.splitlines()
               if l.startswith("info.")]
        # r160's own features are kept (inclusive).
        self.assertIn("audit-evidence-link", ids)   # r160
        # r161+ features are excluded.
        self.assertNotIn("audit-window-at", ids)    # r161
        self.assertNotIn("info-field", ids)         # r172
        self.assertNotIn("info-index", ids)         # r174

    def test_index_until_includes_oldest_rounds(self):
        # The r156 surface tags are the oldest entries; the
        # ceiling keeps them.
        r = _invoke(["info", "--index", "--index-until", "r160"],
                    cwd=self.workspace)
        ids = [l[len("info."):] for l in r.stdout.splitlines()
               if l.startswith("info.")]
        self.assertIn("info-warnings-only", ids)    # r156
        self.assertIn("history-filter", ids)        # r157

    def test_window_brackets_a_round_range(self):
        # since + until compose into a closed interval.
        r = _invoke(
            ["info", "--index",
             "--index-since", "r172", "--index-until", "r174"],
            cwd=self.workspace)
        ids = [l[len("info."):] for l in r.stdout.splitlines()
               if l.startswith("info.")]
        # The closed interval [r172, r174].
        self.assertIn("info-field", ids)            # r172
        self.assertIn("skill-example-runner", ids)  # r173
        self.assertIn("info-index", ids)            # r174
        self.assertIn("note-from-stdin", ids)       # r174
        # Outside the window.
        self.assertNotIn("report-format-faces", ids)  # r170
        self.assertNotIn("info-index-since", ids)     # r175

    def test_inverted_window_refused(self):
        # A window with since after until is a caller error,
        # not a silent empty result.
        r = _invoke(
            ["info", "--index",
             "--index-since", "r174", "--index-until", "r172"],
            cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("is after", r.stderr)
        self.assertIn("--index-since", r.stderr)
        self.assertIn("--index-until", r.stderr)

    def test_invalid_until_round_refused(self):
        r = _invoke(["info", "--index", "--index-until", "bad"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("round tag", r.stderr)
        self.assertIn("--index-until", r.stderr)

    def test_window_is_subset_of_full_index(self):
        # The bracketed window is a subset of the full index,
        # the way ``--since --until`` filters a log.
        full = _invoke(["info", "--index"],
                       cwd=self.workspace).stdout.splitlines()
        window = _invoke(
            ["info", "--index",
             "--index-since", "r168", "--index-until", "r170"],
            cwd=self.workspace).stdout.splitlines()
        self.assertGreater(len(window), 0)
        for line in window:
            self.assertIn(line, full)

    def test_window_lines_are_sorted(self):
        r = _invoke(
            ["info", "--index",
             "--index-since", "r168", "--index-until", "r170"],
            cwd=self.workspace)
        lines = [l for l in r.stdout.splitlines() if l]
        self.assertEqual(lines, sorted(lines))


class IndexUntilCatalogTests(unittest.TestCase):
    """The catalog registers the new capability."""

    def test_index_until_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("info-index-until", ids)

    def test_index_until_since_round_is_r176(self):
        for entry in mindseam._FEATURE_CATALOG:
            if entry["id"] == "info-index-until":
                self.assertEqual(entry["since"], "r176")
                self.assertTrue(entry["default"])
                return
        self.fail("info-index-until entry missing from catalog")
