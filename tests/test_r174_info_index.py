# -*- coding: utf-8 -*-
"""Round 174 guards: info --index, the flat grep-friendly index.

Borrowed from ``pytest --fixtures`` / ``git help config`` /
``cargo --list``: a one-line-per-entry flat text index that a
host can grep without parsing JSON, and that prints
identically on any build of the same controller version.
The r172 ``--field`` shows what the controller can read;
the r174 ``--index`` shows what flags the controller
accepts, at a glance.

The output is sorted so two builds of the same controller
version produce byte-identical index output, the way
``pip list --format=columns`` is stable across runs. The
``info.<feature-id>`` naming scheme borrows the dot-prefix
from a Linux capability (``cap_net_bind_service``); a host
that wants ``format`` reads ``info.info-format``, a host
that wants ``explain`` reads ``info.info-explain``.

The r167 catalog already carries the feature ids; r174
just re-projects them as a flat text index, the way r169
re-projects the JSON payload as a dot-path renderer. Same
data, smaller contract, easier to grep.
"""

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


class IndexContractTests(unittest.TestCase):
    """``info --index`` shape and content."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_index_runs_in_empty_workspace(self):
        # The index is static data; it must work in a fresh
        # empty workspace, the way ``git help config`` works
        # outside a repository.
        r = _invoke(["info", "--index"], cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertGreater(len(r.stdout.strip()), 0)

    def test_index_does_not_create_workspace(self):
        # The index branch short-circuits before the ledger
        # read; it must leave ``.mindseam`` absent.
        _invoke(["info", "--index"], cwd=self.workspace)
        self.assertFalse(
            (Path(self.workspace) / ".mindseam").exists())

    def test_index_one_line_per_entry(self):
        # One feature id per line. A host that runs
        # ``info --index | wc -l`` gets a count that
        # matches the catalog length.
        r = _invoke(["info", "--index"], cwd=self.workspace)
        lines = [l for l in r.stdout.splitlines() if l]
        self.assertEqual(len(lines), len(mindseam._FEATURE_CATALOG))

    def test_index_lines_have_info_prefix(self):
        # Every line is ``info.<feature-id>``, the dot
        # scheme borrowed from a Linux capability name.
        r = _invoke(["info", "--index"], cwd=self.workspace)
        for line in r.stdout.splitlines():
            if not line:
                continue
            self.assertRegex(
                line, r"^info\.[a-z0-9-]+$",
                "line %r breaks the info. prefix convention" % line)

    def test_index_lines_are_sorted(self):
        # The index is sorted, so two builds of the same
        # version produce byte-identical output.
        r = _invoke(["info", "--index"], cwd=self.workspace)
        lines = [l for l in r.stdout.splitlines() if l]
        self.assertEqual(lines, sorted(lines))

    def test_index_matches_catalog(self):
        # Every catalog id shows up exactly once. A missing
        # id means a new capability shipped undocumented;
        # a duplicate id means the catalog was edited
        # twice without a sync, the way the r167 guard
        # catches for the JSON face.
        r = _invoke(["info", "--index"], cwd=self.workspace)
        ids = [l[len("info."):] for l in r.stdout.splitlines()
               if l.startswith("info.")]
        catalog_ids = [e["id"] for e in mindseam._FEATURE_CATALOG]
        self.assertEqual(sorted(ids), sorted(catalog_ids))

    def test_index_is_byte_identical_across_runs(self):
        # Stability: two consecutive invocations on the
        # same controller produce byte-identical output,
        # the way ``pip list`` does. The catalog is
        # static, the sort is stable, no timestamps leak
        # into the output.
        r1 = _invoke(["info", "--index"], cwd=self.workspace)
        r2 = _invoke(["info", "--index"], cwd=self.workspace)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_index_omitted_by_default(self):
        # The default ``info`` face is the sectioned text
        # report; ``--index`` is opt-in. A host that does
        # not pass --index sees the regular report, not
        # the index.
        r = _invoke(["info"], cwd=self.workspace)
        self.assertNotIn("info.info-format", r.stdout)


class IndexCatalogTests(unittest.TestCase):
    """The catalog registers the new capability."""

    def test_index_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("info-index", ids)

    def test_index_since_round_is_r174(self):
        for entry in mindseam._FEATURE_CATALOG:
            if entry["id"] == "info-index":
                self.assertEqual(entry["since"], "r174")
                self.assertTrue(entry["default"])
                return
        self.fail("info-index entry missing from catalog")
