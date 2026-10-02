# -*- coding: utf-8 -*-
"""r345 — the dense-notation class was the ASCII half of its family.

r305 made the repetition message honest: it used to claim "a character
run of 20 or more" while ``REPETITION_CHAR_RUN`` matched four notation
characters, so 25 x's and a markdown hyphen rule both scanned clean and
the message implied they would not. The fix named what the detector
matched — "dots, ellipsis, hyphens, apostrophes" — and left the pattern
alone.

Naming the four was accurate and incomplete in the same way. They are the
ASCII half of the family. A run of em dashes, en dashes, horizontal bars,
figure dashes, minus signs, swung dashes or equals signs renders exactly
the dense horizontal line INVARIANTS[6] is about ("Dense notation appears
in something a person or a task-facing tool reads"), and none of them
matched. Live before-fix, one line of 25 of each, through ``ship``:

    "…"  * 25                  -> fires
    "—"  * 25 (em dash)        -> clean
    "–"  * 25 (en dash)        -> clean
    "―"  * 25 (horizontal bar) -> clean
    "‒"  * 25 (figure dash)    -> clean
    "−"  * 25 (minus sign)     -> clean
    "⁓"  * 25 (swung dash)     -> clean
    "="  * 25 (equals)         -> clean

That is a substitution available to anything that wanted to route around
the check — the same shape r339 found in ``INVISIBLE_CHARS``, where
seventeen of twenty-eight assigned invisible code points were missing and
a planted directive read clean behind any of them.

THE FIX widens the class by seven characters and updates the r305 message
to name the whole family, because a message that undercounts what it
matches is the same defect as one that overcounts. The message keeps
"dots" in it, which r305's own test pins.

THE EXCLUSIONS ARE THE POINT. The characters deliberately NOT here are the
ones Markdown already owns, and adding them would make this pattern
disagree with the structural classifier about one line:

    "-"  a thematic break and a setext underline
    "_"  a thematic break
    "*"  a thematic break
    "~"  a fence
    "#"  a heading

``markdown_structural_lines`` excludes those before this pattern is
consulted, so a line of them is data the author chose to format, not dense
notation they squeezed in. Letters and digits stay out too, exactly as
r305 documented: 25 x's is repetition, not density.

This is a pure recall widening, the mirror of r344 and the opposite of
r343. r343 left the injection family's negation hole alone because a
widened negation costs recall; r344 closed a shape hole because a shape
requirement can only remove matches. This round closes a class hole,
because adding characters to a detection class can only add matches. All
three are the same discipline from different directions: widen where the
direction is free, and pin the direction you chose.
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

# The seven characters the class was missing, with the name a reader needs
# to understand why each belongs.
NEWLY_COVERED = (
    ("\u2014", "em dash"),
    ("\u2013", "en dash"),
    ("\u2015", "horizontal bar"),
    ("\u2012", "figure dash"),
    ("\u2212", "minus sign"),
    ("\u2053", "swung dash"),
    ("=", "equals"),
)

# The four r305 named. They must still match.
ALREADY_COVERED = (".", "\u2026", "-", "'")

# Characters that must stay out: the ones Markdown already owns, plus the
# letters and digits r305 documented as repetition rather than density.
NOT_NOTATION = (
    ("_", "underscore — a thematic break"),
    ("*", "asterisk — a thematic break"),
    ("~", "tilde — a fence"),
    ("#", "hash — a heading"),
    ("+", "plus — a list marker"),
    ("x", "a letter"),
    ("a", "a letter"),
    ("1", "a digit"),
    (" ", "a space"),
)


def _ship(line):
    ws = tempfile.mkdtemp()
    path = os.path.join(ws, "draft.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Draft\n\n%s\n" % line)
    return invoke_cli(ws, ["ship", path])


class NewlyCoveredTests(unittest.TestCase):
    """Each widened character fires the finding."""

    def test_every_new_character_fires_the_pattern(self):
        for char, name in NEWLY_COVERED:
            self.assertTrue(mindseam.REPETITION_CHAR_RUN.search(char * 25),
                            "%s (U+%04X) still misses" % (name, ord(char)))

    def test_every_new_character_fires_the_finding(self):
        for char, name in NEWLY_COVERED:
            r = _ship(char * 25)
            self.assertIn("20 or more repeated notation", r.stdout,
                          "%s (U+%04X) still clean" % (name, ord(char)))

    def test_every_new_character_fires_inline(self):
        # Inline, not only on its own line, because the standalone line
        # is where the structural exclusion could hide.
        for char, name in NEWLY_COVERED:
            r = _ship("text: " + char * 25 + " more text")
            self.assertIn("20 or more repeated notation", r.stdout,
                          "%s (U+%04X) inline still clean" % (name,
                                                              ord(char)))

    def test_a_mixed_run_is_not_a_run(self):
        # One backreference over the whole class: the detector is a run of
        # ONE character, so ten equals followed by ten em dashes is two
        # short runs of two different characters and stays clean.
        self.assertIsNone(mindseam.REPETITION_CHAR_RUN.search(
            "=" * 10 + "\u2014" * 10))
        r = _ship("=" * 10 + "\u2014" * 10)
        self.assertNotIn("repetition loop", r.stdout)


class AlreadyCoveredTests(unittest.TestCase):
    """r305's four characters still match, unchanged."""

    def test_the_four_still_fire_the_pattern(self):
        for char in ALREADY_COVERED:
            self.assertTrue(mindseam.REPETITION_CHAR_RUN.search(char * 25),
                            repr(char))

    def test_dots_still_fire_the_finding(self):
        r = _ship("." * 25)
        self.assertIn("20 or more repeated notation", r.stdout)

    def test_nineteen_still_clean(self):
        # r305's threshold, unchanged: 19 is not a run.
        for char in ALREADY_COVERED + tuple(c for c, _ in NEWLY_COVERED):
            self.assertIsNone(mindseam.REPETITION_CHAR_RUN.search(char * 19),
                              repr(char))

    def test_twenty_is_the_bar(self):
        for char in ALREADY_COVERED + tuple(c for c, _ in NEWLY_COVERED):
            self.assertIsNotNone(
                mindseam.REPETITION_CHAR_RUN.search(char * 20), repr(char))


class ExcludedTests(unittest.TestCase):
    """The exclusions, pinned from both sides."""

    def test_markdown_owned_characters_stay_out_of_the_pattern(self):
        for char, name in NOT_NOTATION:
            self.assertIsNone(
                mindseam.REPETITION_CHAR_RUN.search(char * 25),
                "%s is now in the class" % name)

    def test_markdown_owned_lines_are_structural_not_dense(self):
        # The classifier, not the pattern, is what excludes them — so a
        # line of them is data the author chose to format.
        for label, lines in (
                ("thematic break", ["-" * 25]),
                ("thematic underscore", ["_" * 25]),
                ("thematic asterisk", ["*" * 25]),
                ("fence tilde", ["~" * 25, "code", "~" * 25]),
                ("setext h1", ["Title", "=" * 25]),
                ("setext h2", ["Title", "-" * 25])):
            got = mindseam.markdown_structural_lines(lines)
            # Every one of these lines is structural, so the pattern is
            # never consulted about them.
            self.assertEqual(sorted(got), list(range(len(lines))), label)

    def test_a_hyphen_line_is_still_not_a_finding(self):
        # r305's pin: a markdown rule is skipped, not flagged.
        r = _ship("-" * 25)
        self.assertNotIn("repetition loop", r.stdout)

    def test_letters_stay_out_as_r305_documented(self):
        r = _ship("x" * 25)
        self.assertNotIn("repetition loop", r.stdout)
        r = _ship("-" * 25)
        self.assertNotIn("repetition loop", r.stdout)


class MessageTests(unittest.TestCase):
    """The r305 message must name the widened family."""

    def test_the_message_names_the_new_family(self):
        r = _ship("\u2014" * 25)
        self.assertIn("dots", r.stdout)
        self.assertIn("ellipsis", r.stdout)
        self.assertIn("dashes", r.stdout)
        self.assertIn("apostrophes", r.stdout)
        self.assertIn("equals", r.stdout)

    def test_the_message_still_does_not_overclaim(self):
        # r305's own pin: it must not read as a general character-run
        # detector.
        r = _ship("." * 25)
        self.assertNotIn("a character run of 20 or more", r.stdout)

    def test_the_message_is_unchanged_for_the_original_family(self):
        # r305 pinned "20 or more repeated notation" as the prefix; that
        # is still the prefix.
        r = _ship("." * 25)
        self.assertIn("20 or more repeated notation", r.stdout)


class PatternShapeTests(unittest.TestCase):
    """The class's own construction."""

    def test_the_class_holds_every_character(self):
        pattern = mindseam.REPETITION_CHAR_RUN.pattern
        for char, name in NEWLY_COVERED:
            if ord(char) > 0x7F:
                self.assertIn(r"\u%04x" % ord(char), pattern, name)
            else:
                self.assertIn(char, pattern, name)

    def test_the_original_four_are_still_in_the_class(self):
        pattern = mindseam.REPETITION_CHAR_RUN.pattern
        for char in ALREADY_COVERED:
            if ord(char) > 0x7F:
                self.assertIn(r"\u%04x" % ord(char), pattern, repr(char))
            else:
                self.assertIn(char, pattern, repr(char))

    def test_the_backreference_is_unchanged(self):
        # One backreference over the whole class: a run of ONE character.
        # A mixed 25-character run of different dashes is not a run.
        self.assertIsNone(
            mindseam.REPETITION_CHAR_RUN.search(
                "\u2014\u2013" * 10))

    def test_the_threshold_is_unchanged(self):
        self.assertIn(r"\1{19,}", mindseam.REPETITION_CHAR_RUN.pattern)

    def test_the_source_documents_the_round(self):
        src = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(
            encoding="utf-8")
        i = src.find("REPETITION_CHAR_RUN = re.compile(")
        self.assertGreater(i, 0)
        head = src[max(0, i - 2600):i]
        self.assertIn("r345", head)
        self.assertIn("r305", head)


class InvisibleNeighbourTests(unittest.TestCase):
    """The r339 class is the same family and must not have drifted."""

    def test_the_r339_class_is_untouched(self):
        for cp in (0x200B, 0x3164, 0x200E, 0x034F, 0x2063, 0xFFA0):
            self.assertIsNotNone(
                mindseam.INVISIBLE_CHARS.search("x" + chr(cp) + "y"),
                "U+%04X dropped" % cp)

    def test_the_two_classes_stay_separate(self):
        # One is about invisible bytes, the other about dense runs. A
        # line of em dashes is dense, not invisible; a zero-width joiner
        # is invisible, not dense.
        self.assertIsNotNone(
            mindseam.REPETITION_CHAR_RUN.search("\u2014" * 25))
        self.assertIsNone(mindseam.INVISIBLE_CHARS.search("\u2014" * 25))
        self.assertIsNotNone(
            mindseam.INVISIBLE_CHARS.search("\u200d"))
        self.assertIsNone(mindseam.REPETITION_CHAR_RUN.search("\u200d" * 25))


class CatalogPinTests(unittest.TestCase):
    """The catalog registers the round and keeps its shape."""

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("dense-notation-char-class", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "dense-notation-char-class")
        self.assertEqual(entry["since"], "r345")
        self.assertIn("em dash", entry["summary"].lower())
        self.assertIn("r305", entry["summary"])
        self.assertIn("r339", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 195 before r345; r346 (and later rounds) keep appending above
        # it, so this pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 196)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertTrue(callable(mindseam.markdown_structural_lines))
        self.assertIsInstance(mindseam.REPETITION_CHAR_RUN.pattern, str)


if __name__ == "__main__":
    unittest.main()
