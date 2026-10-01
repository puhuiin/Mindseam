# -*- coding: utf-8 -*-
"""Round 305 guards: the ship char-run finding names what it matches.

REPETITION_CHAR_RUN is ([.…\\-'])\\1{19,} — four notation characters —
but the finding read "a character run of 20 or more", implying any
character. 25 x's scanned clean and 25 hyphens scanned clean
(markdown structural), while 25 dots fired.
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


class RepetitionMessageAccuracyTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        invoke_cli(self.workspace, ["note", "--goal", "g", "--next", "a: one"])

    def _ship(self, body):
        out = __import__("os").path.join(self.workspace, "out.txt")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(body)
        return invoke_cli(self.workspace, ["ship", out])

    def test_message_names_notation(self):
        r = self._ship("." * 25 + "\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("20 or more repeated notation", r.stdout)
        self.assertIn("dots", r.stdout)
        self.assertNotIn("a character run of 20 or more", r.stdout)

    def test_letters_do_not_fire(self):
        r = self._ship("x" * 25 + "\n")
        self.assertNotIn("repetition loop", r.stdout)

    def test_hyphen_rule_is_structural(self):
        # A pure hyphen line is a markdown rule — skipped, not flagged.
        r = self._ship("-" * 25 + "\n")
        self.assertNotIn("repetition loop", r.stdout)

    def test_inline_hyphen_run_still_fires(self):
        r = self._ship("text: " + "-" * 25 + "\n")
        self.assertIn("20 or more repeated notation", r.stdout)

    def test_dots_still_fire(self):
        r = self._ship("." * 20 + "\n")
        self.assertIn("20 or more repeated notation", r.stdout)

    def test_nineteen_still_clean(self):
        r = self._ship("." * 19 + "\n")
        self.assertNotIn("repetition loop", r.stdout)

    def test_line_repetition_message_unchanged(self):
        r = self._ship("same\nsame\nsame\n")
        self.assertIn("a line repeats three times or more", r.stdout)

    def test_pattern_unchanged(self):
        self.assertTrue(mindseam.REPETITION_CHAR_RUN.search("." * 20))
        self.assertTrue(mindseam.REPETITION_CHAR_RUN.search("'" * 20))
        self.assertIsNone(mindseam.REPETITION_CHAR_RUN.search("x" * 20))
        self.assertIsNone(mindseam.REPETITION_CHAR_RUN.search("." * 19))

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("repetition-message-accuracy", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "repetition-message-accuracy")
        self.assertEqual(entry["since"], "r305")
        self.assertIn("notation", entry["summary"])


if __name__ == "__main__":
    unittest.main()
