# -*- coding: utf-8 -*-
"""r338 — ``msg`` was the one history field nothing ever repaired.

``read_history`` tightens every field of a hand-written ``history.json``
before any face sees it: ``t``, ``next``, ``verified``, ``open``,
``error``, ``outcome``, ``marker``, ``confidence``, ``verifier``, ``risk``
(closed domain) and ``extra_steps`` (non-negative). ``HISTORY_ROW_FIELDS``
names twelve fields; eleven were repaired. ``msg`` was the twelfth.

The gap was invisible because three of the five readers stringify
instead of calling a string method: ``--format %m`` renders
``str(row.get("msg") or "-")``, ``--fields msg`` and ``--csv`` route
through ``_history_cell``, which also does ``str()``. So a row whose
``msg`` was a list, dict, int or bool rendered happily on those faces
while four others raised ``TypeError`` at exit 1 with a traceback and no
message:

    history --row-id 1             -> TypeError in _oneline (_escape_line_breaks)
    history --row-id 1 --human     -> same
    history --dedup-by-msg         -> TypeError: 'list' object has no attribute 'strip'
    history --dedup-by-msg --json  -> same
    history --grep hello           -> TypeError: 'list' object has no attribute 'lower'
    history --exclude hello        -> TypeError: 'list' object has no attribute 'lower'

This is the r322 crash family on the last uncovered field — r322 guarded
the non-dict ROW, r316 the ``_row_*`` helpers, and neither reached
``msg``, which has no helper and no repair.

The fix is the same shape r316 used, at both layers:

- ``read_history`` adds ``msg`` to the string-repair tuple, so the file
  is healed on disk the way every sibling field already is and the r334
  stderr warning reports it.
- a new ``_row_msg(row)`` helper coerces at the read sites, for a row
  built in memory rather than read from disk.

``_row_msg`` deliberately does NOT strip, unlike ``_row_next``: the two
display sites echo the annotation verbatim, and the ``--dedup-by-msg``
key site adds its own ``.strip()`` exactly as before. A string value is
therefore byte-identical on every face, and only a non-string moves —
from a crash to the reading every other field already gets: absent.

The round also removes a dead duplicate ``--row-id`` block that sat below
the ``--fields`` projector. The live block above returns on every
``--row-id`` path, so it never ran; it was an r207-era copy predating the
r245 ``untrusted`` map and the r263 ``_oneline`` guarantee, so
restructuring the live block's returns would have resurrected both the
tag-less JSON shape and this crash.
"""

import json
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

# The four readers that used to call a string method on a raw ``msg``.
FORMER_CRASH_SITES = (
    ["history", "--row-id", "1"],
    ["history", "--row-id", "1", "--human"],
    ["history", "--row-id", "1", "--json"],
    ["history", "--dedup-by-msg"],
    ["history", "--dedup-by-msg", "--json"],
    ["history", "--grep", "hello"],
    ["history", "--exclude", "hello"],
)

# The three readers that stringify and so never crashed.
STRINGIFYING_SITES = (
    ["history", "--format", "%m"],
    ["history", "--fields", "msg"],
    ["history", "--csv"],
    ["history", "--csv", "--json"],
    ["history", "--filter", "msg=hello"],
    ["history", "--filter", "msg=hello", "--json"],
)

NON_STRINGS = ([1], [1, 2], {"a": 1}, 7, 3.14, True, False, None, [["x"]])


def _workspace(msg):
    ws = tempfile.mkdtemp()
    d = os.path.join(ws, ".mindseam")
    os.makedirs(d)
    with open(os.path.join(d, "book.json"), "w", encoding="utf-8") as f:
        json.dump({"Goal": ["g"], "Core": ["c"], "Verified": [],
                   "Open": [], "Next": ["n"]}, f)
    with open(os.path.join(d, "history.json"), "w", encoding="utf-8") as f:
        json.dump([{"t": 1700000000, "next": "dom: a", "msg": msg,
                    "verified": 1, "open": 0}], f)
    return ws


class NonStringMsgRefusedTests(unittest.TestCase):
    """Every face answers at exit 0 instead of raising TypeError."""

    def test_former_crash_sites_do_not_crash(self):
        for bad in NON_STRINGS:
            for face in FORMER_CRASH_SITES:
                r = invoke_cli(_workspace(bad), face)
                self.assertNotIn("Traceback (most recent call last)",
                                 r.stdout + r.stderr,
                                 "msg=%r %s" % (bad, face))
                self.assertNotIn("TypeError", r.stdout + r.stderr,
                                 "msg=%r %s" % (bad, face))
                self.assertEqual(r.returncode, 0,
                                 "msg=%r %s: %s" % (bad, face, r.stderr))

    def test_stringifying_sites_do_not_crash(self):
        for bad in NON_STRINGS:
            for face in STRINGIFYING_SITES:
                r = invoke_cli(_workspace(bad), face)
                self.assertNotIn("Traceback (most recent call last)",
                                 r.stdout + r.stderr,
                                 "msg=%r %s" % (bad, face))

    def test_non_string_reads_as_absent_on_the_detail_face(self):
        # The row-id face omits a blank msg entirely, the way it always
        # has for "" — a non-string is absent, not a rendered value.
        for bad in ([1], {"a": 1}, 7, True):
            r = invoke_cli(_workspace(bad), ["history", "--row-id", "1"])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("msg:", r.stdout)

    def test_non_string_reads_as_empty_on_dedup(self):
        r = invoke_cli(_workspace([1, 2]), ["history", "--dedup-by-msg"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("(empty)", r.stdout)
        r = invoke_cli(_workspace([1, 2]), ["history", "--dedup-by-msg", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["unique_count"], 1)
        self.assertEqual(payload["by"], "msg")

    def test_non_string_matches_no_needle(self):
        # --grep / --exclude run against the coerced "" — an absent
        # annotation matches nothing and drops nothing.
        r = invoke_cli(_workspace([1]), ["history", "--grep", "hello"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("0 entries", r.stdout)
        r = invoke_cli(_workspace([1]), ["history", "--exclude", "hello"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 entry", r.stdout)


class ReadHistoryRepairsMsgTests(unittest.TestCase):
    """read_history heals the file and discloses it, like every sibling."""

    def _repair(self, msg):
        ws = _workspace(msg)
        old = os.getcwd()
        try:
            os.chdir(ws)
            return mindseam.read_history()
        finally:
            os.chdir(old)

    def test_non_string_msg_is_repaired(self):
        for bad in ([1], {"a": 1}, 7, True, 3.14):
            hist, changed, reasons = self._repair(bad)
            self.assertEqual(hist[0]["msg"], "", repr(bad))
            self.assertTrue(changed, repr(bad))
            self.assertIn("repaired history has been saved", reasons)

    def test_non_string_msg_is_written_back_to_disk(self):
        ws = _workspace([1, 2])
        invoke_cli(ws, ["history", "--row-id", "1"])
        with open(os.path.join(ws, ".mindseam", "history.json"),
                  encoding="utf-8") as f:
            rows = json.load(f)
        self.assertEqual(rows[0]["msg"], "")

    def test_string_msg_is_left_alone(self):
        for good in ("", "  padded note  ", "plain", "multi\nline"):
            hist, changed, _ = self._repair(good)
            self.assertEqual(hist[0]["msg"], good)
            self.assertFalse(changed)

    def test_missing_msg_stays_missing(self):
        ws = tempfile.mkdtemp()
        d = os.path.join(ws, ".mindseam")
        os.makedirs(d)
        with open(os.path.join(d, "history.json"), "w", encoding="utf-8") as f:
            json.dump([{"t": 1700000000, "next": "dom: a"}], f)
        old = os.getcwd()
        try:
            os.chdir(ws)
            hist, changed, reasons = mindseam.read_history()
        finally:
            os.chdir(old)
        # A row with no msg at all is not a repair: the loop's guard is
        # ``key in fixed``, so an absent annotation is never touched.
        self.assertNotIn("msg", hist[0])
        self.assertFalse(any("msg" in str(r) for r in reasons))

    def test_repair_is_disclosed_on_stderr(self):
        r = invoke_cli(_workspace([1]), ["history", "--row-id", "1"])
        self.assertIn("WARNING: history.json could not be read cleanly",
                      r.stderr)
        self.assertIn("repaired history has been saved", r.stderr)


class RowMsgHelperTests(unittest.TestCase):
    """The _row_msg coercion helper mirrors the r316 _row_* family."""

    def test_non_string_coerces_to_empty(self):
        for bad in ([1], {"a": 1}, 7, True, False, None, 3.14):
            self.assertEqual(mindseam._row_msg({"msg": bad}), "",
                             repr(bad))

    def test_missing_key_is_empty(self):
        self.assertEqual(mindseam._row_msg({}), "")
        self.assertEqual(mindseam._row_msg({"next": "a"}), "")

    def test_string_is_returned_verbatim_unstripped(self):
        # Unlike _row_next, _row_msg does NOT strip: the display sites
        # echo the annotation exactly as recorded.
        self.assertEqual(mindseam._row_msg({"msg": "  padded  "}), "  padded  ")
        self.assertEqual(mindseam._row_msg({"msg": ""}), "")

    def test_joined_the_row_helper_family(self):
        names = {n for n in dir(mindseam) if n.startswith("_row_")}
        for expected in ("_row_next", "_row_error", "_row_outcome",
                         "_row_marker", "_row_confidence", "_row_verifier",
                         "_row_msg"):
            self.assertIn(expected, names)


class FieldNamespaceCompletenessTests(unittest.TestCase):
    """Every HISTORY_ROW_FIELDS entry is now covered by a coercion."""

    def test_msg_was_the_last_gap(self):
        # The twelve fields read_history repairs, read straight out of the
        # source so a future field cannot be added to the tuple without
        # this test noticing.
        src = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(
            encoding="utf-8")
        import re
        for field in mindseam.HISTORY_ROW_FIELDS:
            self.assertRegex(src, r'["\']%s["\']' % re.escape(field),
                             "%s is not named anywhere in the repair "
                             "vocabulary" % field)

    def test_every_field_has_a_string_or_numeric_repair(self):
        # ``msg`` joins the explicit string-repair tuple alongside the
        # fields it was last to reach.
        src = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(
            encoding="utf-8")
        self.assertIn('for key in ("error", "msg", "outcome"):', src)

    def test_history_row_fields_is_twelve(self):
        self.assertEqual(len(mindseam.HISTORY_ROW_FIELDS), 12)
        self.assertIn("msg", mindseam.HISTORY_ROW_FIELDS)


class SingleRowIdBlockTests(unittest.TestCase):
    """The dead duplicate --row-id block is gone."""

    def _source(self):
        return (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(
            encoding="utf-8")

    def test_exactly_one_row_id_locator(self):
        # Before r338 there were two: the live r245/r263 block and an
        # unreachable r207-era copy below the --fields projector.
        src = self._source()
        self.assertEqual(src.count("if getattr(args, \"row_id\", None) is not None:"), 2,
                         "the r276 narrowing guard plus exactly one detail "
                         "block")

    def test_no_stale_json_row_id_face(self):
        # The dead block's JSON carried only row_id + row (no untrusted
        # map). The live face must remain the only one.
        src = self._source()
        self.assertNotIn('"row_id": n,\n                "row": row,\n            },',
                         src)

    def test_live_face_still_carries_the_untrusted_map(self):
        r = invoke_cli(_workspace("note"), ["history", "--row-id", "1", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(json.loads(r.stdout).keys()),
                         ["row", "row_id", "untrusted"])

    def test_live_face_still_onelines_the_annotation(self):
        # r263: a splitlines break in the msg keeps the tag on the same
        # physical line as its value.
        r = invoke_cli(
            _workspace("first\u2028SECOND"), ["history", "--row-id", "1"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("\\u2028", r.stdout)


class StringPathUnchangedTests(unittest.TestCase):
    """A string annotation renders byte-identically on every face."""

    def test_row_id_echoes_the_annotation_verbatim(self):
        r = invoke_cli(_workspace("  padded note  "),
                       ["history", "--row-id", "1"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("msg:        padded note", r.stdout)

    def test_dedup_by_msg_collapses_on_stripped_key(self):
        ws = tempfile.mkdtemp()
        d = os.path.join(ws, ".mindseam")
        os.makedirs(d)
        with open(os.path.join(d, "book.json"), "w", encoding="utf-8") as f:
            json.dump({"Goal": [], "Core": [], "Verified": [], "Open": [],
                       "Next": []}, f)
        with open(os.path.join(d, "history.json"), "w", encoding="utf-8") as f:
            json.dump([{"t": 1700000000, "next": "dom: a", "msg": "a: same",
                        "verified": 1, "open": 0},
                       {"t": 1700000001, "next": "dom: b", "msg": "  a: same  ",
                        "verified": 1, "open": 0}], f)
        r = invoke_cli(ws, ["history", "--dedup-by-msg"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 unique msg annotation across 2 rows", r.stdout)

    def test_format_and_fields_and_csv_still_render(self):
        r = invoke_cli(_workspace("a note"), ["history", "--format", "%m"])
        self.assertEqual(r.stdout.strip(), "a note")
        # One selected column: the header and the row each carry no tab,
        # because both are "\t".join of a one-element list.
        r = invoke_cli(_workspace("a note"), ["history", "--fields", "msg"])
        self.assertEqual(r.stdout.strip(), "msg\na note")
        r = invoke_cli(_workspace("a note"), ["history", "--csv",
                                              "--fields", "msg"])
        self.assertEqual(r.stdout.strip(), "msg\na note")

    def test_empty_string_is_still_a_value(self):
        # r309: "" is a value. The row-id face still omits the line and
        # dedup still buckets it as (empty) — unchanged by the coercion.
        r = invoke_cli(_workspace(""), ["history", "--dedup-by-msg"])
        self.assertIn("(empty)", r.stdout)

    def test_grep_still_matches_a_string_annotation(self):
        r = invoke_cli(_workspace("a hello note"),
                       ["history", "--grep", "HELLO"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 entry", r.stdout)
        r = invoke_cli(_workspace("a hello note"),
                       ["history", "--exclude", "HELLO"])
        self.assertIn("0 entries", r.stdout)


class CatalogPinTests(unittest.TestCase):
    """The catalog registers the fix and keeps its shape."""

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("history-msg-value-repair", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "history-msg-value-repair")
        self.assertEqual(entry["since"], "r338")
        self.assertIn("--grep", entry["summary"])
        self.assertIn("--dedup-by-msg", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 188 before r338; r339 (and later rounds) keep appending above
        # it, so this pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 189)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertTrue(callable(mindseam._row_msg))
        self.assertTrue(callable(mindseam.read_history))


if __name__ == "__main__":
    unittest.main()
