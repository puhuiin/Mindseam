# -*- coding: utf-8 -*-
"""Round 172 guards: info --explain, the static capability doc.

A host that reads ``info --features`` gets a list of capability
ids but no prose: the ids are stable keys, not documentation.
``info --explain <feature-id>`` resolves one id to its summary,
the round that introduced it, and whether it is on by default.
Borrowed from ``kubectl explain``, and mirroring the
``audit --explain`` precedent from r171.

Two invariants matter more than the rendering:

* The doc is *static*, so it short-circuits ahead of every
  ledger read and works in an empty workspace, the way
  ``git help`` works outside a repository. It also leaves no
  trace: no ``.mindseam`` directory is created.
* Every id in ``_FEATURE_CATALOG`` is explainable. A capability
  that ships in the catalog but cannot be explained is the same
  class of drift the r69 guard catches for flags.
"""

import json
import os
import shutil
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


class ExplainCatalogTests(unittest.TestCase):
    """The catalog is the single source for the doc."""

    def test_info_explain_is_in_catalog(self):
        entry = [i for i in mindseam._FEATURE_CATALOG
                 if i["id"] == "info-explain"]
        self.assertEqual(len(entry), 1,
                         "info-explain missing from the catalog")
        self.assertEqual(entry[0]["since"], "r172")
        self.assertGreater(len(entry[0]["summary"]), 0)

    def test_catalog_ids_are_unique(self):
        # The lookup is by id, so a duplicate would silently
        # shadow the later entry.
        ids = [item["id"] for item in mindseam._FEATURE_CATALOG]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_entry_carries_the_doc_fields(self):
        for item in mindseam._FEATURE_CATALOG:
            self.assertEqual(
                set(item.keys()),
                {"id", "since", "summary", "default"},
                "feature %r malformed" % item.get("id"))
            self.assertIsInstance(item["default"], bool)

    def test_every_catalog_id_is_explainable(self):
        # The round-trip invariant: nothing ships in the catalog
        # that a host cannot ask about.
        workspace = tempfile.mkdtemp()
        try:
            for item in mindseam._FEATURE_CATALOG:
                r = _invoke(["info", "--explain", item["id"]],
                            cwd=workspace)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("info explain %s" % item["id"], r.stdout)
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


class ExplainBehaviorTests(unittest.TestCase):
    """``--explain FEATURE-ID`` is static and side-effect free."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_explain_works_in_empty_workspace(self):
        r = _invoke(["info", "--explain", "info-explain"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("info explain info-explain", r.stdout)
        self.assertIn("summary:", r.stdout)
        self.assertIn("since:", r.stdout)
        self.assertIn("default:", r.stdout)

    def test_explain_leaves_no_trace(self):
        # Static data means no ledger is created as a side
        # effect, so the command is safe to run anywhere.
        _invoke(["info", "--explain", "info-explain"],
                cwd=self.workspace)
        self.assertFalse(
            (Path(self.workspace) / ".mindseam").exists(),
            "--explain must not create a ledger")

    def test_explain_short_circuits_the_digest(self):
        # It is a lookup, not a report: the normal info header
        # must never be printed alongside the doc.
        r = _invoke(["info", "--explain", "info-memory"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Version:", r.stdout)
        self.assertNotIn("Audit:", r.stdout)

    def test_explain_unknown_id_refused(self):
        r = _invoke(["info", "--explain", "nope"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("not a recognised feature id", r.stderr)
        # The error names the known set so the host can recover.
        self.assertIn("info-explain", r.stderr)
        self.assertIn("audit-explain", r.stderr)

    def test_explain_unknown_id_refused_on_json_face(self):
        # The refuse is not a text-face accident: the JSON face
        # refuses identically so a host cannot miss it.
        r = _invoke(["info", "--explain", "nope", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("not a recognised feature id", r.stderr)

    def test_explain_json_face(self):
        r = _invoke(["info", "--explain", "info-explain", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["id"], "info-explain")
        self.assertEqual(payload["since"], "r172")
        self.assertEqual(payload["default"], True)
        self.assertIn("summary", payload)

    def test_both_faces_agree(self):
        # r158: the two faces carry the same answer, so a host can
        # switch between them without re-learning the contract.
        text = _invoke(["info", "--explain", "info-human"],
                       cwd=self.workspace)
        data = _invoke(["info", "--explain", "info-human", "--json"],
                       cwd=self.workspace)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(data.returncode, 0, data.stderr)
        payload = json.loads(data.stdout)
        self.assertIn(payload["summary"], text.stdout)
        self.assertIn(payload["since"], text.stdout)

    def test_explain_trims_surrounding_whitespace(self):
        # A host that interpolates an id from a file may carry
        # padding; trimming keeps the lookup forgiving.
        r = _invoke(["info", "--explain", "  info-explain  "],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("info explain info-explain", r.stdout)

    def test_explain_renders_default_in_words(self):
        r = _invoke(["info", "--explain", "info-explain"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # The text face says "yes", not the Python literal, the
        # way `systemctl status` prints "active" rather than a
        # boolean.
        self.assertIn("default: yes", r.stdout)
        self.assertNotIn("True", r.stdout)


if __name__ == "__main__":
    unittest.main()
