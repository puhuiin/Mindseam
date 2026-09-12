# -*- coding: utf-8 -*-
"""Round 208 guards: history's truncation selectors are exclusive.

``--head N`` keeps the first N rows, ``--tail N`` the last N, and
``--limit N`` (``-n``) aliases ``--tail`` — they share one
variable. The if/elif silently made ``--head 2 --tail 3`` print
the head rows and exit 0, and ``--limit 3 --tail 2`` discard the
explicit --tail (the alias wins the shared variable). The old
comment called this "the last filter winning" — but these are
command-line flags, not a shell pipeline, and the baseline pin's
own docstring said a host that needs both ends should split into
two invocations. The pin locked the silent behaviour while its
intent described the refusal r208 implements.

r208 refuses any pair of the three selectors with exit 2, naming
them, before any rotation or render. The window flags
(--since/--until) are filters over time, not selectors, and keep
composing with each selector.
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


class TruncationSelectorsExclusiveTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        rows = [{"t": i, "next": "dom: s%d" % i,
                 "verified": i + 1, "open": 0} for i in range(10)]
        (self.ledger / "history.json").write_text(
            json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _rows(self):
        return json.loads(
            (self.ledger / "history.json").read_text(encoding="utf-8"))

    def test_head_tail_refused(self):
        r = _invoke(["history", "--head", "2", "--tail", "3"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("mutually exclusive truncation selectors",
                      r.stderr)
        self.assertIn("--head", r.stderr)
        self.assertIn("--tail", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_limit_tail_alias_pair_refused(self):
        # --limit aliases --tail: passing both is one selector asked
        # twice, and the alias used to win the shared variable
        # silently.
        r = _invoke(["history", "--limit", "3", "--tail", "2"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--limit", r.stderr)
        self.assertIn("--tail", r.stderr)

    def test_limit_head_pair_refused(self):
        r = _invoke(["history", "--limit", "3", "--head", "2"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--head", r.stderr)

    def test_all_three_refused(self):
        r = _invoke(["history", "--head", "1", "--tail", "2",
                     "--limit", "3"], self.workspace)
        self.assertEqual(r.returncode, 2)
        for name in ("--head", "--tail", "--limit"):
            self.assertIn(name, r.stderr)

    def test_refusal_before_render_and_rotation(self):
        # The refusal sits with the other history refusals, before
        # the --keep rotation: the ledger file is untouched.
        r = _invoke(["history", "--head", "2", "--tail", "3",
                     "--keep", "1"], self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(len(self._rows()), 10)

    def test_alone_paths_unchanged(self):
        for args, expect in (
            (["--head", "2"], ["dom: s0", "dom: s1"]),
            (["--tail", "2"], ["dom: s8", "dom: s9"]),
            (["--limit", "3"], ["dom: s7", "dom: s8", "dom: s9"]),
            (["-n", "2"], ["dom: s8", "dom: s9"]),
        ):
            r = _invoke(["history", *args, "--json"], self.workspace)
            self.assertEqual(r.returncode, 0, (args, r.stderr))
            self.assertEqual([x["next"] for x in
                              json.loads(r.stdout)["rows"]], expect)

    def test_window_flags_still_compose(self):
        # Filters are not selectors: --since keeps composing with a
        # truncation selector (r197's documented compositions).
        r = _invoke(["history", "--tail", "2", "--since", "3600",
                     "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_feature_in_catalog(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-truncation-selectors-exclusive", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-truncation-selectors-exclusive")
        self.assertEqual(entry["since"], "r208")
        self.assertTrue(entry["default"])


if __name__ == "__main__":
    unittest.main()
