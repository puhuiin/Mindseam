# -*- coding: utf-8 -*-
"""Round 221 guards: the three user-facing docs carry the history
window grammar r220 landed.

r220 pointed ``history --since/--until`` at ``parse_window_value``.
The help text and SKILL.md still only showed bare seconds for
history, while audit's span grammar was documented in all three
docs. r69 pins flag *presence*; this pins the *grammar* the help
and the docs advertise for the window flags, so a reader of
SKILL.md or either README can type ``history --since 30m`` and
have it work.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam

SKILL = (ROOT / "mindseam" / "SKILL.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
README_ZH = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")


class HistoryWindowGrammarDocsTests(unittest.TestCase):

    def test_skill_documents_history_span(self):
        self.assertIn("history --since 30m", SKILL)
        self.assertIn("--until 7d", SKILL)
        self.assertIn("r220", SKILL)

    def test_readme_documents_history_span(self):
        self.assertIn("history --since 30m", README)
        self.assertIn("r220", README)

    def test_chinese_readme_documents_history_span(self):
        self.assertIn("history --since 30m", README_ZH)
        self.assertIn("r220", README_ZH)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-window-grammar-docs", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-window-grammar-docs")
        self.assertEqual(entry["since"], "r221")
        self.assertIn("SKILL.md", entry["summary"])


if __name__ == "__main__":
    unittest.main()
