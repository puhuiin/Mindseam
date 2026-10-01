# -*- coding: utf-8 -*-
"""Round 295 guards: inverted time windows refuse.

info --index-since/--index-until bracket a round window and r176
refuses an inverted pair with exit 2. The sibling time windows —
history --since/--until and audit --since/--until — accepted an
inverted pair and returned an empty result at exit 0.

since_cutoff = now - since_seconds and until_cutoff = now -
until_seconds, so the interval is empty exactly when
since_seconds < until_seconds. A swapped pair of flags is a host
bug; the silent-empty is the r272 silent-wrong-at-exit-0 family.

Equal bounds stay valid (a zero-width window).
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam
from _controller_helper import invoke_cli


class WindowInvertedRefusalTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["seam", "--from-stdin"],
                   stdin="a: one\nb: two\n")

    def test_history_inverted_refused(self):
        r = invoke_cli(self.workspace,
                       ["history", "--since", "60", "--until", "3600"])
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertIn("CANNOT", r.stderr)
        self.assertIn("--since", r.stderr)
        self.assertIn("--until", r.stderr)

    def test_history_inverted_span_refused(self):
        r = invoke_cli(self.workspace,
                       ["history", "--since", "1m", "--until", "2h"])
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertIn("CANNOT", r.stderr)

    def test_history_inverted_json_refused(self):
        r = invoke_cli(self.workspace,
                       ["history", "--since", "60", "--until", "3600",
                        "--json"])
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertIn("CANNOT", r.stderr)

    def test_audit_inverted_refused(self):
        r = invoke_cli(self.workspace,
                       ["audit", "--since", "60", "--until", "3600"])
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertIn("CANNOT", r.stderr)
        self.assertIn("--since", r.stderr)

    def test_audit_inverted_json_refused(self):
        r = invoke_cli(self.workspace,
                       ["audit", "--since", "60", "--until", "3600",
                        "--json"])
        self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
        self.assertIn("CANNOT", r.stderr)

    def test_equal_bounds_still_valid(self):
        # A zero-width window is not inverted; the index window keeps
        # since==until (r176) and so does the time window.
        r = invoke_cli(self.workspace,
                       ["history", "--since", "60", "--until", "60",
                        "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_ordered_window_still_valid(self):
        # since_cutoff older than until_cutoff is the valid bracket:
        # --since 3600 --until 60 is [now-3600, now-60].
        r = invoke_cli(self.workspace,
                       ["history", "--since", "3600", "--until", "60",
                        "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_single_flag_untouched(self):
        for args in (["history", "--since", "60"],
                     ["history", "--until", "3600"],
                     ["audit", "--since", "60"],
                     ["audit", "--until", "3600"]):
            r = invoke_cli(self.workspace, args)
            self.assertEqual(r.returncode, 0, (args, r.stderr))

    def test_negative_refusal_unchanged(self):
        # The r217 contract fires first; an inverted pair that is also
        # negative still names the negative.
        r = invoke_cli(self.workspace,
                       ["history", "--since", "-1", "--until", "3600"])
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("non-negative", r.stderr)

    def test_index_inverted_still_refused(self):
        # The r176 sibling keeps its own contract.
        r = invoke_cli(self.workspace,
                       ["info", "--index", "--index-since", "r170",
                        "--index-until", "r160"])
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("after", r.stderr)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("window-inverted-refusal", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "window-inverted-refusal")
        self.assertEqual(entry["since"], "r295")
        self.assertIn("inverted", entry["summary"])


if __name__ == "__main__":
    unittest.main()
