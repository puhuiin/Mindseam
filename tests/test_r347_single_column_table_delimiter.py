# -*- coding: utf-8 -*-
"""r347 — a one-column table was never a table.

``TABLE_DELIMITER`` is the r244 structural classifier's table row: a line
of dashes under a header row means "what follows is data the author chose
to quote", so `ship` skips it rather than reporting the author's own
quoted text as a leaked register marker. The pattern was

    ^\\s*\\|?\\s*:?-{3,}:?\\s*(?:\\|\\s*:?-{3,}:?\\s*)+\\|?\\s*$

and the trailing cell group is ``+`` — **at least two** delimiter cells. A
one-column table's delimiter row could never match, and a one-column
table is an ordinary GFM construct. Live before-fix, through ``ship``
over a draft whose only content was a table quoting data:

    | a | b |         | note |      | note |
    | --- | --- |     | --- |       | :-: |
    | step | DATA ..| | DATA DATA..| | DATA DATA..|
      -> clean           -> "state     -> "state
                            markers"     markers"

The two-column form is the one the pattern was written for, and it is
excluded as quoted data; the single-column form fell through to the prose
scan, which reported the author's own quoted table as a leaked marker.

FOUND BY the r158 two-faces matrix coming up empty. That matrix
(every renderer x ``--json``, every command) held everywhere, so the next
enumeration was the markdown classifier's own grammar — fifteen delimiter
rows through the pattern — which showed exactly one family changed when
the ``+`` became ``*``.

THE FIX is ``+`` -> ``*``: one delimiter cell is a table, not two. Two
forms are deliberately left narrower than GFM allows, and pinned that
way, because r244's doctrine is that quoted data is skipped only when the
author really quoted it — widening further would grow the exclusion
surface and hide a planted marker inside it:

    ``| - |``   a single dash per cell. GFM allows it, but a one-dash
                cell is also ordinary row text, so it stays prose.
    ``| :-: |`` an alignment colon. GFM allows it, and the same argument
                applies one level out.

A bare ``---`` line now matches as a single-cell delimiter, which changes
nothing: a line of hyphens is already a thematic break and is structural
either way — pinned so that reasoning stays visible rather than being
inferred from a passing suite.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import mindseam
from _controller_helper import invoke_cli


def _ship(lines):
    ws = tempfile.mkdtemp()
    path = os.path.join(ws, "draft.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return invoke_cli(ws, ["ship", path])


class SingleColumnTableTests(unittest.TestCase):
    """The defect: a one-column table's delimiter row now matches."""

    def test_a_piped_single_cell_matches(self):
        self.assertTrue(mindseam.TABLE_DELIMITER.match("| --- |"))

    def test_a_bare_single_cell_matches(self):
        self.assertTrue(mindseam.TABLE_DELIMITER.match("---"))

    def test_the_body_below_it_is_structural(self):
        lines = ["| note |", "| --- |", "| DATA DATA seen here |"]
        self.assertEqual(sorted(mindseam.markdown_structural_lines(lines)),
                         [0, 1, 2])

    def test_a_single_column_table_is_quoted_data(self):
        # The live surface: `ship` skips a table, because the author
        # chose to quote it (r244).
        r = _ship(["| note |", "| --- |", "| DATA DATA seen here |"])
        self.assertNotIn("state markers in outgoing text", r.stdout)

    def test_a_pipeless_delimiter_is_a_setext_heading_not_a_table(self):
        # The no-pipe form is the interesting boundary: `note` followed by
        # `---` is a setext H2, so the classifier's setext branch takes it
        # before the table branch ever sees it. The header pair is
        # structural and the paragraph after it is prose — which is the
        # right answer, because a heading's body is not quoted table data.
        lines = ["note", "---", "DATA DATA seen here"]
        self.assertEqual(sorted(mindseam.markdown_structural_lines(lines)),
                         [0, 1])
        r = _ship(lines)
        self.assertIn("state markers in outgoing text", r.stdout)

    def test_a_pipeless_two_column_table_is_still_a_table(self):
        # The same form with two cells is unambiguous: no setext rule
        # can claim a line containing a pipe, so it is a table and the
        # body is data.
        lines = ["a | b", "--- | ---", "x | DATA DATA"]
        self.assertEqual(sorted(mindseam.markdown_structural_lines(lines)),
                         [0, 1, 2])
        r = _ship(lines)
        self.assertNotIn("state markers in outgoing text", r.stdout)


class MultiColumnUnchangedTests(unittest.TestCase):
    """r244's contract, which the fix must not disturb."""

    def test_two_columns_still_match(self):
        self.assertTrue(mindseam.TABLE_DELIMITER.match("| --- | --- |"))

    def test_three_columns_still_match(self):
        self.assertTrue(mindseam.TABLE_DELIMITER.match("| --- | --- | --- |"))

    def test_no_outer_pipes_still_match(self):
        self.assertTrue(mindseam.TABLE_DELIMITER.match("--- | ---"))

    def test_a_two_column_table_is_still_quoted_data(self):
        lines = ["| a | b |", "| --- | --- |", "| step | DATA DATA |"]
        self.assertEqual(sorted(mindseam.markdown_structural_lines(lines)),
                         [0, 1, 2])
        r = _ship(lines)
        self.assertNotIn("state markers in outgoing text", r.stdout)

    def test_aligned_two_columns_still_match(self):
        # r244 pins the alignment form for the multi-column case, which
        # the ``*`` change leaves exactly as it was.
        self.assertFalse(mindseam.TABLE_DELIMITER.match("| :-: | --: |"))
        lines = ["| a | b |", "| :-: | --: |", "| 1 | 2 |"]
        self.assertEqual(sorted(mindseam.markdown_structural_lines(lines)),
                         [])


class DeliberatelyNarrowTests(unittest.TestCase):
    """The two forms left narrower than GFM, pinned so the exclusion
    surface cannot creep."""

    def test_a_single_dash_cell_stays_prose(self):
        self.assertFalse(mindseam.TABLE_DELIMITER.match("| - |"))
        lines = ["| a | b |", "| - | - |", "| 1 | 2 |"]
        self.assertEqual(sorted(mindseam.markdown_structural_lines(lines)),
                         [])

    def test_an_alignment_colon_cell_stays_prose(self):
        self.assertFalse(mindseam.TABLE_DELIMITER.match("| :-: |"))
        lines = ["| note |", "| :-: |", "| DATA DATA seen here |"]
        self.assertEqual(sorted(mindseam.markdown_structural_lines(lines)),
                         [])

    def test_a_bare_hyphen_line_is_a_thematic_break_either_way(self):
        # The ``*`` change makes a lone ``---`` match as a single-cell
        # delimiter, and it was already a thematic break. Pinned so the
        # reasoning stays visible rather than being inferred from a
        # passing suite.
        self.assertTrue(mindseam.TABLE_DELIMITER.match("---"))
        self.assertTrue(mindseam.THEMATIC_BREAK.match("---"))
        self.assertEqual(
            sorted(mindseam.markdown_structural_lines(["---"])), [0])

    def test_prose_is_not_a_table(self):
        for line in ("text", "| text | text |", "- not a run", "| : |",
                     "| -- | text |"):
            self.assertFalse(mindseam.TABLE_DELIMITER.match(line), line)


class ClassifierElsewhereTests(unittest.TestCase):
    """The rest of the r329 classifier is untouched."""

    def test_other_constructs_are_unchanged(self):
        for label, lines, want in (
                ("heading", ["# Title", "body"], [0]),
                ("list", ["- a", "- b"], []),
                ("setext h1", ["Title", "====="], [0, 1]),
                ("setext h2", ["Title", "-----"], [0, 1]),
                ("thematic dash", ["---"], [0]),
                ("thematic star", ["***"], [0]),
                ("fence", ["```", "code", "```"], [0, 1, 2]),
                ("fence tilde", ["~~~", "code", "~~~"], [0, 1, 2]),
                ("plain prose", ["just words"], [])):
            got = sorted(mindseam.markdown_structural_lines(lines))
            self.assertEqual(got, want, label)

    def test_a_fence_still_wins(self):
        # A table inside a fence is data, and the fence classification is
        # unchanged by the delimiter widening.
        lines = ["```", "| a | b |", "| --- | --- |", "| 1 | 2 |", "```"]
        self.assertEqual(sorted(mindseam.markdown_structural_lines(lines)),
                         [0, 1, 2, 3, 4])

    def test_prose_after_a_single_column_table_is_still_scanned(self):
        # The exclusion is the table, not everything after it.
        r = _ship(["| note |", "| --- |", "| data |", "",
                   "DATA DATA in prose"])
        self.assertIn("state markers in outgoing text", r.stdout)


class LiveShipSurfaceTests(unittest.TestCase):
    """The whole point: quoted data is not a leaked marker."""

    def test_every_column_count_quoting_data_is_clean(self):
        for lines in (
                ["| a | b |", "| --- | --- |", "| x | DATA DATA |"],
                ["| a | b | c |", "| --- | --- | --- |", "| x | y | DATA DATA |"],
                ["| note |", "| --- |", "| DATA DATA |"]):
            r = _ship(lines)
            self.assertNotIn("state markers in outgoing text", r.stdout,
                             str(lines))

    def test_a_marker_in_prose_still_fires(self):
        r = _ship(["DATA DATA in prose"])
        self.assertIn("state markers in outgoing text", r.stdout)

    def test_a_marker_in_a_fence_still_does_not_fire(self):
        r = _ship(["```", "DATA DATA", "```"])
        self.assertNotIn("state markers in outgoing text", r.stdout)


class PatternShapeTests(unittest.TestCase):
    """The pattern's own construction."""

    def test_the_cell_group_is_star_not_plus(self):
        self.assertIn(r"(?:\|\s*:?-{3,}:?\s*)*", mindseam.TABLE_DELIMITER.pattern)

    def test_the_dash_count_is_still_three_or_more(self):
        self.assertIn("-{3,}", mindseam.TABLE_DELIMITER.pattern)

    def test_the_source_names_the_round(self):
        src = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(
            encoding="utf-8")
        i = src.find("TABLE_DELIMITER = re.compile(")
        self.assertGreater(i, 0)
        head = src[max(0, i - 1900):i]
        self.assertIn("r347", head)
        self.assertIn("one-column", head)


class CatalogPinTests(unittest.TestCase):
    """The catalog registers the round and keeps its shape."""

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("single-column-table-delimiter", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "single-column-table-delimiter")
        self.assertEqual(entry["since"], "r347")
        self.assertIn("one-column", entry["summary"])
        self.assertIn("r244", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 197 before r347; r348 (and later rounds) keep appending above
        # it, so this pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 198)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertTrue(callable(mindseam.markdown_structural_lines))
        self.assertIsInstance(mindseam.TABLE_DELIMITER.pattern, str)


if __name__ == "__main__":
    unittest.main()
