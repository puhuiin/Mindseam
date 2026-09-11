# -*- coding: utf-8 -*-
"""Round 188 guards: audit --at and the window flags are exclusive.

The r161 ``--at`` branch slices ``hist[:N]`` and returns; the
``--since``/``--until`` filtering lives in the *else* branch. A call
like ``audit --at 5 --since 3600`` therefore silently dropped the
window — and the ``history_window`` JSON block still carried
``since_seconds: 3600``, reporting a filter that never ran. A host
reading the JSON believed the window was applied.

r188 refuses the combination with exit 2 before any history is read,
naming the offending flag(s), the way ``info --field``/``--format``
refuse to compose (``kubectl get -o json -o yaml`` precedent). The
motivation is the same contract-hardening rule the leaked system
prompts encode: never let a flag be silently ignored, because the
caller will believe it applied.

Alone-paths are untouched: ``--at N`` alone, ``--since`` alone,
``--until`` alone, and ``--since --until`` composed keep their r161 /
r173 behaviour byte-for-byte.
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


class AtWindowExclusivityTests(unittest.TestCase):

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

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_at_with_since_is_refused(self):
        r = _invoke(["audit", "--at", "3", "--since", "3600"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--at 3 composes with neither", r.stderr)
        self.assertIn("--since", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_at_with_until_is_refused(self):
        r = _invoke(["audit", "--at", "3", "--until", "60"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--until", r.stderr)

    def test_at_with_both_names_both(self):
        r = _invoke(["audit", "--at", "3", "--since", "3600",
                     "--until", "60"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--since/--until", r.stderr)

    def test_refusal_happens_before_the_range_check(self):
        # The ambiguity is refused even when --at is also out of
        # range: the combination is invalid as a combination, before
        # any single flag's own validation matters.
        r = _invoke(["audit", "--at", "99", "--since", "3600"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("composes with neither", r.stderr)

    def test_at_alone_unchanged(self):
        r = _invoke(["audit", "--at", "3", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        window = payload["history_window"]
        self.assertEqual(window["at_row"], 3)
        self.assertEqual(window["rows_out"], 3)
        self.assertIsNone(window["since_seconds"])
        self.assertIsNone(window["until_seconds"])

    def test_since_alone_unchanged(self):
        r = _invoke(["audit", "--since", "3600", "--json"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_window"]["since_seconds"], 3600)
        self.assertNotIn("at_row", payload["history_window"])

    def test_since_until_composition_unchanged(self):
        # The r173 bracket (--since with --until, no --at) still
        # composes.
        r = _invoke(["audit", "--since", "3600", "--until", "60"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("audit-at-window-exclusive", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "audit-at-window-exclusive")
        self.assertEqual(entry["since"], "r188")
        self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
