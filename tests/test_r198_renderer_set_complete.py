# -*- coding: utf-8 -*-
"""Round 198 guards: the renderer exclusivity set is complete.

r197 refused pairs among ``{--csv, --domains, --format, --quiet}`` —
but the combination probe that found them kept sweeping, and the same
silent-ignore family turned out to cover two more renderers the
refusal set missed: ``--span`` (a summary block) and ``--count``
(a one-number aggregate). The branch order made
``history --csv --span`` print CSV (span dropped) while
``history --quiet --span`` printed the span block (quiet dropped) and
``history --count --quiet`` printed one-word lines (count dropped) —
the winner depends on branch order, which is exactly the ambiguity a
host cannot reason about.

r198 extends the r197 refusal to all six renderers:
``{--count, --csv, --domains, --format, --quiet, --span}``. Any pair
is refused with exit 2 naming the flags, before the destructive
``--keep`` rotation. Compositions survive: ``--span --json`` and the
machine face in general (``--json`` is not a renderer — the r170
payload carries everything), ``--fields`` column selection,
``--human`` timestamp rendering, ``--row-id`` precedence, and every
renderer alone.

A neighbour candidate was investigated and deliberately left alone:
``seam --quiet --dry-run`` prints nothing at all, including the
dry-run marker — but that is a pinned, commented design decision
(``test_quiet_drops_banner_ledger_telemetry``: "quiet at its
quietest"), with the marker riding the JSON warnings for scripting
hosts. Not a gap; not touched.
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


class SixRendererExclusivityTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
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

    def test_span_and_count_pairs_are_refused(self):
        # The r197 set missed these: span and count participate in the
        # same winner-by-branch-order ambiguity.
        pairs = [
            ["--csv", "--span"],
            ["--quiet", "--span"],
            ["--format", "%n", "--span"],
            ["--count", "--span"],
            ["--count", "--quiet"],
            ["--count", "--csv"],
            ["--count", "--format", "%n"],
            ["--domains", "--span"],
            ["--count", "--domains"],
        ]
        for combo in pairs:
            r = _invoke(["history", *combo], self.workspace)
            self.assertEqual(r.returncode, 2, combo)
            self.assertIn("mutually exclusive renderers", r.stderr, combo)
            self.assertEqual(r.stdout, "", combo)

    def test_refusal_names_span_and_count(self):
        r = _invoke(["history", "--count", "--span"], self.workspace)
        self.assertIn("--count", r.stderr)
        self.assertIn("--span", r.stderr)

    def test_every_renderer_alone_still_works(self):
        ok = [
            ["--count"],
            ["--csv"],
            ["--domains"],
            ["--format", "%t %n"],
            ["--quiet"],
            ["--span"],
        ]
        for combo in ok:
            r = _invoke(["history", *combo], self.workspace)
            self.assertEqual(r.returncode, 0, "%s -> %s" % (combo, r.stderr))

    def test_span_and_count_ride_json(self):
        # --json is the machine face, not a renderer: span and count
        # compose with it (span rides via its own json face, count's
        # number is already the payload's history_count).
        r = _invoke(["history", "--span", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn("span", payload)
        r = _invoke(["history", "--count", "--json"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_count"], 3)

    def test_filters_still_compose_with_renderers(self):
        # Filters are not renderers: --grep/--since narrow the set any
        # renderer then presents.
        r = _invoke(["history", "--grep", "step 1", "--count"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1")
        r = _invoke(["history", "--grep", "step 1", "--csv"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 2)  # header + row

    def test_quiet_dry_run_stays_pinned_empty(self):
        # The deliberate design r198 investigated and left alone:
        # quiet suppresses the dry-run marker ("quiet at its
        # quietest", pinned by test_quiet_drops_banner_ledger_telemetry),
        # and the JSON warnings carry the marker for scripting hosts.
        r = _invoke(["seam", "--quiet", "--dry-run"], self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        # Facts still print under quiet; the marker must not.
        self.assertNotIn("dry-run: history.json was not updated",
                         r.stdout)
        r = _invoke(["seam", "--quiet", "--dry-run", "--json"],
                    self.workspace)
        self.assertIn("dry-run: history.json was not updated", r.stdout)


if __name__ == "__main__":
    unittest.main()
