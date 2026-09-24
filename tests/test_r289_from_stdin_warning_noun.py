"""r289 — the seam --json from-stdin warning agrees noun with the count.

``mode_seam``'s ``--json`` warnings face rendered the from-stdin
next-action count as a hardcoded plural
"from-stdin: %d next actions %s" while its text sibling
"From stdin: %d next action%s recorded." already pluralizes on the
count. So exactly one piped next action made the two faces project the
SAME quantity ``len(extra_nexts)`` two ways: JSON
"from-stdin: 1 next actions recorded", text
"From stdin: 1 next action recorded." Under ``--dry-run`` the JSON
warning read "1 next actions would be recorded".

Live before-fix (fresh workspace, exactly one non-blank line on stdin):
  seam --from-stdin --json  -> warnings ["from-stdin: 1 next actions recorded"]
  seam --from-stdin --dry-run --json -> "... 1 next actions would be recorded"
  seam --from-stdin (text)  -> "From stdin: 1 next action recorded."

This is the singular/plural family of r281-r288, on the JSON warnings
surface. The machine face and the human face project one value so they
must agree by construction (r254/r259 enumerate-every-projector). The
JSON warning now pluralizes the noun on the same count
("" if len(extra_nexts) == 1 else "s"), keeping the r203 dry-run tense
branch ("would be recorded"/"recorded"). Only exactly 1 becomes
"1 next action"; 0 and >=2 stay "next actions".
"""

import json
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam  # noqa: E402

from _controller_helper import invoke_cli  # noqa: E402


def _since_ints():
    return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]


def _stdin_warning(warnings):
    for w in warnings:
        if w.startswith("from-stdin:"):
            return w
    return None


class _Base(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r289_")
        invoke_cli(self.workspace, ["note", "--goal", "ship the parser",
                                    "--next", "write the lexer"])
        invoke_cli(self.workspace,
                   ["note", "--core", "Parser — the one true grammar"])

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _json_warnings(self, *args, stdin=None):
        r = invoke_cli(self.workspace, list(args), stdin=stdin)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout).get("warnings", [])


class FromStdinWarningSingularTests(_Base):
    """Exactly one piped next action -> singular noun on the JSON face."""

    def test_one_line_json_warning_is_singular(self):
        warnings = self._json_warnings("seam", "--from-stdin", "--json",
                                       stdin="write the parser\n")
        self.assertEqual(_stdin_warning(warnings),
                         "from-stdin: 1 next action recorded")

    def test_one_line_json_warning_has_no_lazy_plural(self):
        warnings = self._json_warnings("seam", "--from-stdin", "--json",
                                       stdin="write the parser\n")
        w = _stdin_warning(warnings)
        self.assertNotIn("1 next actions", w)

    def test_trailing_blank_lines_still_count_as_one(self):
        # splitlines()+strip() drops blank lines, so one non-blank line
        # among blanks is still count 1 -> singular.
        warnings = self._json_warnings("seam", "--from-stdin", "--json",
                                       stdin="\n  \nwrite the parser\n\n")
        self.assertEqual(_stdin_warning(warnings),
                         "from-stdin: 1 next action recorded")


class DryRunTenseTests(_Base):
    """The r203 dry-run tense branch survives, with the agreeing noun."""

    def test_one_line_dry_run_is_singular_and_conditional(self):
        warnings = self._json_warnings("seam", "--from-stdin", "--dry-run",
                                       "--json", stdin="write the parser\n")
        self.assertIn("from-stdin: 1 next action would be recorded", warnings)

    def test_dry_run_marker_still_present(self):
        # r203: the from-stdin count and the dry-run marker coexist.
        warnings = self._json_warnings("seam", "--from-stdin", "--dry-run",
                                       "--json", stdin="write the parser\n")
        self.assertIn("dry-run: history.json was not updated", warnings)

    def test_two_lines_dry_run_stay_plural(self):
        warnings = self._json_warnings("seam", "--from-stdin", "--dry-run",
                                       "--json", stdin="a\nb\n")
        self.assertIn("from-stdin: 2 next actions would be recorded", warnings)


class PluralUnchangedTests(_Base):
    """0 and >=2 keep the plural noun byte-for-byte."""

    def test_two_lines_stay_plural(self):
        warnings = self._json_warnings("seam", "--from-stdin", "--json",
                                       stdin="a\nb\n")
        self.assertEqual(_stdin_warning(warnings),
                         "from-stdin: 2 next actions recorded")

    def test_three_lines_stay_plural(self):
        warnings = self._json_warnings("seam", "--from-stdin", "--json",
                                       stdin="a\nb\nc\n")
        self.assertEqual(_stdin_warning(warnings),
                         "from-stdin: 3 next actions recorded")

    def test_zero_nonblank_stays_plural(self):
        # from_stdin is set but every line is blank -> count 0, still
        # "next actions" (only exactly 1 is singular).
        warnings = self._json_warnings("seam", "--from-stdin", "--json",
                                       stdin="\n   \n")
        self.assertEqual(_stdin_warning(warnings),
                         "from-stdin: 0 next actions recorded")


class FacesAgreeTests(_Base):
    """The JSON warning noun matches the text sibling noun for one line."""

    def _text_stdin_line(self, *args, stdin=None):
        r = invoke_cli(self.workspace, list(args), stdin=stdin)
        self.assertEqual(r.returncode, 0, r.stderr)
        for line in r.stdout.splitlines():
            if line.startswith("From stdin:"):
                return line
        return None

    def test_json_and_text_agree_on_singular_noun(self):
        text = self._text_stdin_line("seam", "--from-stdin",
                                     stdin="write the parser\n")
        self.assertEqual(text, "From stdin: 1 next action recorded.")
        json_warnings = self._json_warnings("seam", "--from-stdin", "--json",
                                            stdin="write the parser\n")
        json_w = _stdin_warning(json_warnings)
        # Both faces render the count with the singular noun "next action".
        self.assertIn("1 next action ", text + " ")
        self.assertIn("1 next action ", json_w + " ")

    def test_json_and_text_agree_on_plural_noun(self):
        text = self._text_stdin_line("seam", "--from-stdin", stdin="a\nb\n")
        self.assertEqual(text, "From stdin: 2 next actions recorded.")
        json_warnings = self._json_warnings("seam", "--from-stdin", "--json",
                                            stdin="a\nb\n")
        self.assertIn("2 next actions", _stdin_warning(json_warnings))


class CatalogTests(unittest.TestCase):
    def test_entry_present_since_r289_default_true(self):
        entry = next(
            (e for e in mindseam._FEATURE_CATALOG
             if e["id"] == "from-stdin-warning-agrees-noun"),
            None,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r289")
        self.assertTrue(entry["default"])

    def test_r289_is_the_highest_round(self):
        self.assertGreaterEqual(max(_since_ints()), 289)

    def test_catalog_grew_to_140(self):
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 140)

    def test_recent_window_is_110(self):
        recent = [n for n in _since_ints() if n >= 170]
        self.assertGreaterEqual(len(recent), 110)


if __name__ == "__main__":
    unittest.main()
