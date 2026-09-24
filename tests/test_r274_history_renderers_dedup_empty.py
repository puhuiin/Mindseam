# -*- coding: utf-8 -*-
"""Round 274 guards: the renderer exclusivity set covers dedup and empty.

r197 refused four renderers, r198 extended the set to six (``--span`` and
``--count``) and its docstring called the set complete. But two more
print-and-return renderers were never added: ``--dedup`` /
``--dedup-by-msg`` (the ``sort -u`` / ``uniq`` collapse, terminal at
mindseam.py:7852 with its own ``--json`` face) and ``--empty`` (the
``find -empty`` post-filter, terminal at 7902 with its own ``--json``
face). The runtime branch order is
``--csv < --domains < --span < --dedup < --empty < --json < --quiet <
--count < --format``, so whichever branch printed first won and the later
flag was silently dropped at exit 0 — the identical winner-by-branch-order
ambiguity r188/r197/r198/r207 refuse.

r274 extends the set to eight slots. ``--empty`` gets its own slot; the
dedup pair shares ONE slot (line 7866: "both are honoured if both are
passed"), named for whichever was given so the refusal message stays
accurate. ``--json`` stays out of the set (it rides each renderer via that
branch's own json face, the r170 two-faces rule), ``--dedup
--dedup-by-msg`` still composes to exit 0, and every one of the six prior
renderers still refuses each other and still works alone.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam
from _controller_helper import invoke_cli


def _invoke(args, cwd):
    return invoke_cli(cwd, args)


class DedupEmptyExclusivityTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r274_")
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        for i in range(3):
            _invoke(["note", "--next", "dom: step %d" % i], self.workspace)
            _invoke(["seam", "--json"], self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_dedup_pairs_with_prior_renderers_are_refused(self):
        # --dedup is a terminal renderer: it must refuse every one of the
        # six prior renderers, the way they refuse each other.
        pairs = [
            ["--dedup", "--quiet"],
            ["--dedup", "--count"],
            ["--dedup", "--csv"],
            ["--dedup", "--domains"],
            ["--dedup", "--span"],
            ["--dedup", "--format", "%n"],
        ]
        for combo in pairs:
            r = _invoke(["history", *combo], self.workspace)
            self.assertEqual(r.returncode, 2, combo)
            self.assertIn("mutually exclusive renderers", r.stderr, combo)
            self.assertEqual(r.stdout, "", combo)

    def test_empty_pairs_with_prior_renderers_are_refused(self):
        pairs = [
            ["--empty", "--quiet"],
            ["--empty", "--count"],
            ["--empty", "--csv"],
            ["--empty", "--domains"],
            ["--empty", "--span"],
            ["--empty", "--format", "%n"],
        ]
        for combo in pairs:
            r = _invoke(["history", *combo], self.workspace)
            self.assertEqual(r.returncode, 2, combo)
            self.assertIn("mutually exclusive renderers", r.stderr, combo)
            self.assertEqual(r.stdout, "", combo)

    def test_dedup_and_empty_refuse_each_other(self):
        r = _invoke(["history", "--dedup", "--empty"], self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("mutually exclusive renderers", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_dedup_by_msg_pairs_are_refused(self):
        r = _invoke(["history", "--dedup-by-msg", "--quiet"], self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("mutually exclusive renderers", r.stderr)

    def test_refusal_names_the_dedup_flag(self):
        # The slot is named for whichever dedup flag was given so the
        # message is accurate, not a blank or a wrong flag.
        r = _invoke(["history", "--span", "--dedup"], self.workspace)
        self.assertIn("--dedup", r.stderr)
        self.assertIn("--span", r.stderr)
        r = _invoke(["history", "--dedup-by-msg", "--quiet"], self.workspace)
        self.assertIn("--dedup-by-msg", r.stderr)

    def test_refusal_names_empty(self):
        r = _invoke(["history", "--empty", "--count"], self.workspace)
        self.assertIn("--empty", r.stderr)
        self.assertIn("--count", r.stderr)

    def test_dedup_and_dedup_by_msg_still_compose(self):
        # By design (line 7866): both keys are honoured in one pass, so
        # the pair must NOT self-refuse.
        r = _invoke(["history", "--dedup", "--dedup-by-msg"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_dedup_and_dedup_by_msg_compose_under_json(self):
        r = _invoke(["history", "--dedup", "--dedup-by-msg", "--json"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("unique_count", payload)

    def test_dedup_alone_works(self):
        r = _invoke(["history", "--dedup"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_empty_alone_works(self):
        r = _invoke(["history", "--empty"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_dedup_by_msg_alone_works(self):
        r = _invoke(["history", "--dedup-by-msg"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_dedup_rides_json(self):
        # --json is the machine face, not a renderer: dedup composes with
        # it via the dedup branch's own json face.
        r = _invoke(["history", "--dedup", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("unique_count", payload)
        self.assertEqual(payload["by"], "next")

    def test_empty_rides_json(self):
        r = _invoke(["history", "--empty", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("rows", payload)
        self.assertIn("history_count", payload)

    def test_prior_six_still_refuse_each_other(self):
        # Regression: adding two slots must not weaken the r197/r198 set.
        pairs = [
            ["--csv", "--span"],
            ["--quiet", "--count"],
            ["--domains", "--format", "%n"],
        ]
        for combo in pairs:
            r = _invoke(["history", *combo], self.workspace)
            self.assertEqual(r.returncode, 2, combo)
            self.assertIn("mutually exclusive renderers", r.stderr, combo)

    def test_every_renderer_alone_still_works(self):
        # All eight, each alone, exit 0.
        ok = [
            ["--count"],
            ["--csv"],
            ["--domains"],
            ["--dedup"],
            ["--dedup-by-msg"],
            ["--empty"],
            ["--format", "%t %n"],
            ["--quiet"],
            ["--span"],
        ]
        for combo in ok:
            r = _invoke(["history", *combo], self.workspace)
            self.assertEqual(r.returncode, 0, "%s -> %s" % (combo, r.stderr))

    def test_filters_still_compose_with_dedup(self):
        # Filters are not renderers: --grep narrows the set dedup collapses.
        r = _invoke(["history", "--grep", "step 1", "--dedup"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)


class DedupEmptyCatalogTests(unittest.TestCase):

    def _since_ints(self):
        return [int(e["since"].lstrip("r"))
                for e in mindseam._FEATURE_CATALOG]

    def test_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-renderers-dedup-empty", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-renderers-dedup-empty")
        self.assertEqual(entry["since"], "r274")
        self.assertIn("--dedup", entry["summary"])
        self.assertIn("--empty", entry["summary"])

    def test_r274_is_the_highest_round(self):
        # The newest round owns the exact ``max == NNN`` head; it retires
        # to a ``>=`` floor once its successor lands.
        self.assertEqual(max(self._since_ints()), 274)

    def test_catalog_grew_to_125(self):
        self.assertEqual(len(mindseam._FEATURE_CATALOG), 125)

    def test_recent_window_is_95(self):
        recent = [i for i in self._since_ints() if i >= 170]
        self.assertEqual(len(recent), 95)


if __name__ == "__main__":
    unittest.main()
