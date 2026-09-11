# -*- coding: utf-8 -*-
"""Round 197 guards: history's four renderers are mutually exclusive.

``mode_history`` grew four renderers over its lifetime — ``--csv``
(r15x), ``--domains``, ``--format`` (r16x), ``--quiet`` — and the
branch order made the first one win while the rest were silently
dropped: ``history --csv --format '%t|%n'`` emitted stock CSV while
the host believed its template was applied, and ``--quiet --csv``
handed back header-bearing rows to a caller parsing one-word lines.
The same silent-ignore shape r188 refused on ``audit --at`` plus the
window flags, and the same two-output-formats ambiguity info's
``--field``/``--format`` have refused since r172.

r197 refuses any combination of two or more of
``{--csv, --domains, --format, --quiet}`` with exit 2, naming the
offending flags — checked at the very top of ``mode_history``, before
the destructive ``--keep`` rotation, so a refused call never writes.

Real compositions are pinned intact: ``--fields`` selects columns for
``--csv`` and the table, ``--human`` renders timestamps under any
renderer, ``--format`` rides ``--json`` (the r170 two-faces rule),
``--row-id`` keeps its documented before-every-render-flag
precedence, and ``--count`` is an aggregator, not a renderer.
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
    # r191's in-process harness: same returncode/stdout/stderr shape
    # as a spawn, without growing the suite's spawning set.
    return invoke_cli(cwd, args)


class RendererExclusivityTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        for i in range(4):
            _invoke(["note", "--next", "dom: step %d" % i], self.workspace)
            _invoke(["seam", "--json"], self.workspace)

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_every_renderer_pair_is_refused(self):
        pairs = [
            ["--csv", "--format", "%t|%n"],
            ["--csv", "--quiet"],
            ["--csv", "--domains"],
            ["--format", "%n", "--quiet"],
            ["--format", "%n", "--domains"],
            ["--quiet", "--domains"],
        ]
        for combo in pairs:
            r = _invoke(["history", *combo], self.workspace)
            self.assertEqual(r.returncode, 2, combo)
            self.assertIn("mutually exclusive renderers", r.stderr, combo)
            self.assertEqual(r.stdout, "", combo)

    def test_refusal_names_every_offending_flag(self):
        r = _invoke(["history", "--csv", "--quiet"], self.workspace)
        self.assertIn("--csv", r.stderr)
        self.assertIn("--quiet", r.stderr)

    def test_refusal_precedes_the_keep_rotation(self):
        # A refused call must not rotate: the destructive --keep write
        # sits after the renderer check, so the on-disk history is
        # byte-identical before and after the refusal.
        history = self.ledger / "history.json"
        before = history.read_bytes()
        r = _invoke(["history", "--keep", "1", "--csv", "--quiet"],
                    self.workspace)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(history.read_bytes(), before)

    def test_real_compositions_survive(self):
        ok = [
            ["--csv", "--fields", "t,next"],
            ["--format", "%n", "--json"],
            ["--quiet", "--fields", "next"],
            ["--csv", "--human"],
            ["--csv"],
            ["--quiet"],
            ["--format", "%t %n"],
            ["--domains"],
            ["--row-id", "1", "--quiet"],
            ["--count"],
        ]
        for combo in ok:
            r = _invoke(["history", *combo], self.workspace)
            self.assertEqual(r.returncode, 0, "%s -> %s" % (combo, r.stderr))

    def test_csv_fields_composition_selects_columns(self):
        # --fields is a column selector, not a renderer: it must keep
        # composing with --csv exactly as before.
        r = _invoke(["history", "--csv", "--fields", "next"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(lines[0], "next")
        for line in lines[1:]:
            self.assertNotIn(",", line)

    def test_format_rides_json(self):
        # The r170 two-faces rule on the template renderer: the JSON
        # face keeps the full payload (rows) and adds the rendered
        # lines plus the template — the shape the baseline
        # round-trip test's docstring always described.
        r = _invoke(["history", "--format", "%n", "--json"],
                    self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["format"], "%n")
        self.assertEqual(payload["lines"],
                         ["dom: step %d" % i for i in range(4)])
        self.assertEqual(len(payload["rows"]), 4)
        self.assertEqual([row["next"] for row in payload["rows"]],
                         payload["lines"])


if __name__ == "__main__":
    unittest.main()
