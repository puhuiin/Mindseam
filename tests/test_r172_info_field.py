# -*- coding: utf-8 -*-
"""Round 172 guards: info --field, the single-key dot-path alias.

r169 added ``--format <path1,path2>`` to ``info``; r170 carried
the same dot-path renderer to every report face. r172 rounds
out the surface with a single-key shorthand borrowed from
``git rev-parse <ref>`` and ``kubectl get <obj>``: ``--field
<key>`` is exactly ``--format <key>``, with no list-indexer
syntax and no comma-separated multi-path. The flag is
mutually exclusive with ``--format`` so the host sees a
clear error when both are passed, the way ``kubectl get
-o json -o yaml`` refuses two output formats.
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


class FieldBase(unittest.TestCase):

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


class FieldBehaviorTests(FieldBase):
    """``--field <key>`` is exactly ``--format <key>``."""

    def test_field_renders_one_key(self):
        self._ledger()
        r = _invoke(["info", "--field", "lock_state.state"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "free")

    def test_field_renders_workspace_id(self):
        # The workspace id block is always present; the
        # 16-hex id is a stable identifier for the host.
        self._ledger()
        r = _invoke(["info", "--field", "workspace_id.id",
                     "--workspace-id"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.strip()), 16)

    def test_field_does_not_emit_json(self):
        # --field is the bare-scalar face; no ``{`` opener.
        self._ledger()
        r = _invoke(["info", "--field", "lock_state.state"],
                    cwd=self.workspace)
        self.assertNotIn("{", r.stdout)

    def test_field_equals_format_on_same_path(self):
        # The contract: --field <key> and --format <key> are
        # exactly the same. The host reads the same scalar.
        self._ledger()
        r_field = _invoke(["info", "--field", "lock_state.state"],
                          cwd=self.workspace)
        r_format = _invoke(["info", "--format", "lock_state.state"],
                           cwd=self.workspace)
        self.assertEqual(r_field.stdout, r_format.stdout)
        self.assertEqual(r_field.returncode, r_format.returncode)

    def test_field_missing_path_is_empty(self):
        # Same contract as --format: a missing path returns
        # an empty string, not exit 2.
        self._ledger()
        r = _invoke(["info", "--field", "no.such.path"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "")


class FieldExclusivityTests(FieldBase):
    """--field and --format are mutually exclusive."""

    def test_field_with_format_refused(self):
        self._ledger()
        r = _invoke(["info", "--field", "lock_state.state",
                     "--format", "workspace_id.id"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("mutually exclusive", r.stderr)
        self.assertIn("--field", r.stderr)
        self.assertIn("--format", r.stderr)

    def test_field_wins_when_format_is_empty(self):
        # An explicit empty --format (``--format=`` with no
        # value) is still treated as "set" by argparse, so
        # the mutual-exclusivity check fires. This pins the
        # contract: a host that wants --field must drop
        # --format entirely, the way a host that wants
        # ``kubectl get -o yaml`` must drop ``-o json``.
        self._ledger()
        r = _invoke(["info", "--field", "lock_state.state",
                     "--format", ""],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("mutually exclusive", r.stderr)


class FieldScopeTests(FieldBase):
    """--field is info-only; other faces reject it."""

    def test_field_on_seam_refused(self):
        # argparse itself refuses --field on seam (no such
        # argument registered), but the r172 contract also
        # checks the dispatch level in case a future round
        # registers --field globally: the r172 pin is "info
        # only" and the r172 help text says so. We assert
        # the argparse-level refusal here.
        self._ledger()
        r = _invoke(["seam", "--field", "x"],
                    cwd=self.workspace)
        self.assertNotEqual(r.returncode, 0)
        # argparse's American spelling.
        self.assertIn("unrecognized", r.stderr.lower())

    def test_field_on_audit_refused(self):
        self._ledger()
        r = _invoke(["audit", "--field", "x"],
                    cwd=self.workspace)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unrecognized", r.stderr.lower())


class FieldCatalogTests(unittest.TestCase):
    """The feature catalog registers the new capability."""

    def test_field_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("info-field", ids)

    def test_field_since_round_is_r172(self):
        for entry in mindseam._FEATURE_CATALOG:
            if entry["id"] == "info-field":
                self.assertEqual(entry["since"], "r172")
                self.assertTrue(entry["default"])
                return
        self.fail("info-field entry missing from catalog")
