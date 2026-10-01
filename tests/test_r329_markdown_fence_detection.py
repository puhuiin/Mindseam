# -*- coding: utf-8 -*-
"""r329 — a mis-detected code fence hid a leaked register marker.

``markdown_fenced_lines`` decides which lines of an outgoing document are
*structural* (quoted data) and which are *prose*. ``ship``'s outbound
register scan reads only the NON-structural lines — a quoted code block
is data the author chose to show (r244) — so a line wrongly classified
as a fence removes whatever follows it from the scan entirely.

Two openings were accepted that CommonMark does not call fences:

1. A BACKTICK fence whose info string contains a backtick. CommonMark
   says the info string of a backtick fence may not contain any backtick,
   so ```` ```python``` ```` — a paragraph — was read as an opener, and
   every line until the next closer was classified as quoted data.
2. A TAB-indented fence. CommonMark allows up to three SPACES of
   indentation; a tab counts as four columns, so `\t``` ` is an indented
   code block. Because an indented code block ends at the first
   non-blank, non-indented line, the prose AFTER it stayed prose — but
   the old `\\s{0,3}` accepted the tab and fenced everything after it.

Live before-fix, on `ship -` with the register marker ``PHEW`` planted
one line under each::

    plain prose                      -> fenced []    finding reported
    ``` + the marker + ```           -> fenced [0,1,2] clean (correct)
    ```python``` + the marker + ```  -> fenced [0,1,2] clean  <-- hidden
    \t``` + the marker + ```         -> fenced [0,1,2] clean  <-- hidden

The third and fourth are the defect: the marker rode out of the
human-facing boundary reported clean, which is the same class r244
called worse than the inbound hole because ship is the surface a human
reads. After the fix both report the finding.

The fix is two rules, both straight from CommonMark: a backtick fence's
info string may not contain a backtick (tilde fences have no such
restriction), and fence indentation is up to three SPACES rather than
any whitespace. The closing fence keeps allowing trailing spaces or
tabs, which CommonMark ignores.

Note how the round found this: the function had never been named in any
test (one of sixteen uncovered by name), so a coverage-shaped sweep —
every function in the module against the concatenated test source — was
the probe, and the mis-classification was then driven end-to-end through
`ship` to confirm the harm rather than stopping at the helper.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _controller_helper import invoke_cli, run_controller  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "mindseam", "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import mindseam  # noqa: E402

MARK = "PHEW"


def ship_stdout(ws, text):
    return run_controller(ws, "ship", "-", stdin=text)


class FencedLinesTests(unittest.TestCase):
    """The fence detector itself."""

    def test_backtick_info_with_a_backtick_is_not_an_opener(self):
        lines = ["```python```", "prose", "```", "more"]
        fenced = mindseam.markdown_fenced_lines(lines)
        self.assertNotIn(0, fenced, fenced)
        self.assertNotIn(1, fenced, fenced)
        # the trailing bare fence still opens
        self.assertIn(2, fenced)
        self.assertIn(3, fenced)

    def test_tilde_info_with_a_backtick_still_opens(self):
        # Tilde fences have no restriction on the info string.
        lines = ["~~~python```", "code", "~~~", "prose"]
        self.assertEqual(sorted(mindseam.markdown_fenced_lines(lines)),
                         [0, 1, 2])

    def test_tab_indented_fence_is_not_an_opener(self):
        lines = ["\t```", "prose", "```", "more"]
        fenced = mindseam.markdown_fenced_lines(lines)
        self.assertNotIn(0, fenced, fenced)
        self.assertNotIn(1, fenced, fenced)
        self.assertIn(2, fenced)

    def test_plain_info_string_still_opens(self):
        lines = ["```python", "code", "```", "prose"]
        self.assertEqual(sorted(mindseam.markdown_fenced_lines(lines)),
                         [0, 1, 2])

    def test_four_space_indent_is_not_a_fence(self):
        lines = ["    ```", "code", "```", "more"]
        self.assertEqual(sorted(mindseam.markdown_fenced_lines(lines)),
                         [2, 3])

    def test_three_space_indent_is_a_fence(self):
        lines = ["   ```", "code", "```", "prose"]
        self.assertEqual(sorted(mindseam.markdown_fenced_lines(lines)),
                         [0, 1, 2])

    def test_closing_fence_allows_trailing_tab_and_space(self):
        for tail in ("\t", "  ", " \t "):
            lines = ["```", "code", "```" + tail, "prose"]
            self.assertEqual(sorted(mindseam.markdown_fenced_lines(lines)),
                             [0, 1, 2], tail)

    def test_unclosed_fence_still_swallows_the_tail(self):
        lines = ["intro", "```", "code", "more"]
        self.assertEqual(sorted(mindseam.markdown_fenced_lines(lines)),
                         [1, 2, 3])

    def test_larger_closing_fence_closes(self):
        lines = ["```", "code", "`````", "prose"]
        self.assertEqual(sorted(mindseam.markdown_fenced_lines(lines)),
                         [0, 1, 2])

    def test_inner_fence_line_is_content(self):
        lines = ["```", "a ``` b", "```", "prose"]
        self.assertEqual(sorted(mindseam.markdown_fenced_lines(lines)),
                         [0, 1, 2])


class StructuralLinesTests(unittest.TestCase):
    """The structural classification that ship scans against."""

    def test_mis_detected_lines_are_no_longer_structural(self):
        lines = ["```python```", "the register says %s" % MARK, "```"]
        structural = mindseam.markdown_structural_lines(lines)
        self.assertNotIn(1, structural, structural)

    def test_real_fence_is_still_structural(self):
        lines = ["```", "the register says %s" % MARK, "```"]
        structural = mindseam.markdown_structural_lines(lines)
        self.assertEqual(sorted(structural), [0, 1, 2])

    def test_headings_and_tables_unchanged(self):
        lines = ["## Heading", "| case | result |", "|---|---|",
                 "| empty | ok |"]
        structural = mindseam.markdown_structural_lines(lines)
        for index in range(4):
            self.assertIn(index, structural)


class ShipBoundaryTests(unittest.TestCase):
    """The end-to-end harm: a leaked marker must not ride out clean."""

    def setUp(self):
        self._workspaces = []
        self.ws = self._fresh()
        invoke_cli(self.ws, ["note", "--goal", "ship it",
                             "--next", "verify it"])

    def tearDown(self):
        for ws in self._workspaces:
            shutil.rmtree(ws, ignore_errors=True)

    def _fresh(self):
        ws = tempfile.mkdtemp(prefix="r329_")
        self._workspaces.append(ws)
        return ws

    def test_backtick_info_fence_no_longer_hides_the_marker(self):
        doc = "```python```\nthe register says %s right here\n```\n" % MARK
        r = ship_stdout(self.ws, doc)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("state markers in outgoing text", r.stdout)

    def test_tab_indented_fence_no_longer_hides_the_marker(self):
        doc = "\t```\nthe register says %s right here\n```\n" % MARK
        r = ship_stdout(self.ws, doc)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("state markers in outgoing text", r.stdout)

    def test_real_fence_still_reads_as_quoted_data(self):
        doc = "```\nthe register says %s right here\n```\n" % MARK
        r = ship_stdout(self.ws, doc)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Found:", r.stdout)
        self.assertIn("clean", r.stdout)

    def test_plain_prose_still_fires(self):
        r = ship_stdout(self.ws, "the register says %s right here\n" % MARK)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("state markers in outgoing text", r.stdout)


class CatalogPinTests(unittest.TestCase):

    def _since_ints(self):
        out = []
        for e in mindseam._FEATURE_CATALOG:
            since = e.get("since")
            if isinstance(since, str) and since.startswith("r"):
                try:
                    out.append(int(since.lstrip("r")))
                except ValueError:
                    pass
        return out

    def test_entry_present_since_r329_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "markdown-fence-detection"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r329")
        self.assertTrue(entry["default"])

    def test_r329_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 329)


if __name__ == "__main__":
    unittest.main()
