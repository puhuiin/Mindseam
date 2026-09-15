# -*- coding: utf-8 -*-
"""Round 220 guards: history --since/--until share audit's window grammar.

The help text has always said "like docker logs --since 30m", but
argparse was ``type=int`` so a span died in the parser with a usage
error. ``audit --since 30m`` worked (r173). r220 points history at
the same ``parse_window_value``: seconds, span, or ISO-8601 date.

Unreadable values refuse with the CANNOT family (exit 2), the same
as audit. Bare seconds keep working so existing hosts are unaffected.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from _controller_helper import invoke_cli

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


class HistoryWindowGrammarTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        (self.ledger / "WORKSPACE.md").write_text(
            "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nn\n", encoding="utf-8")
        self.history = self.ledger / "history.json"
        import time as _time
        now = int(_time.time())
        rows = [
            # Fresh row (now)
            {"t": now, "next": "a: fresh", "verified": 1, "open": 0,
             "marker": "DONE", "confidence": "strong",
             "verifier": "pytest", "risk": "low",
             "error": "", "outcome": "ok", "extra_steps": 0},
            # Old row (3 days ago)
            {"t": now - 3 * 86400, "next": "a: old", "verified": 0,
             "open": 0, "marker": "DONE", "confidence": "strong",
             "verifier": "pytest", "risk": "low",
             "error": "", "outcome": "ok", "extra_steps": 0},
        ]
        self.history.write_text(json.dumps(rows), encoding="utf-8")

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_span_since_accepted(self):
        r = invoke_cli(self.workspace, ["history", "--since", "1h", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1")

    def test_span_until_accepted(self):
        r = invoke_cli(self.workspace, ["history", "--until", "1h", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1")

    def test_bare_seconds_still_work(self):
        r = invoke_cli(self.workspace, ["history", "--since", "3600", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1")

    def test_span_and_bare_compose(self):
        r = invoke_cli(self.workspace,
                       ["history", "--since", "1d", "--until", "1h", "--count"])
        self.assertEqual(r.returncode, 0, r.stderr)
        # Fresh row is within 1h; old row is outside 1d upper bound...
        # --until 1h drops rows newer than 1h ago, so only the old row
        # survives until; --since 1d keeps only last day, so old (3d)
        # is dropped. Result: 0 rows in the bracket.
        self.assertEqual(r.stdout.strip(), "0")

    def test_unreadable_value_refused(self):
        r = invoke_cli(self.workspace, ["history", "--since", "banana",
                                        "--count"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--since", r.stderr)
        self.assertIn("accepted", r.stderr)

    def test_negative_still_refused(self):
        r = invoke_cli(self.workspace, ["history", "--since", "-10", "--count"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--since", r.stderr)

    def test_span_json_carries_seconds(self):
        r = invoke_cli(self.workspace, ["history", "--since", "2h", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["since"], 7200)
        self.assertEqual(payload["history_count"], 1)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-window-grammar", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-window-grammar")
        self.assertEqual(entry["since"], "r220")
        self.assertIn("parse_window_value", entry["summary"])
        self.assertIn("30m", entry["summary"])


if __name__ == "__main__":
    unittest.main()
