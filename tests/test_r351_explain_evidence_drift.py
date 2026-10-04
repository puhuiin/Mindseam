# -*- coding: utf-8 -*-
"""r351 — AUDIT_TAG_EXPLAIN is nine hand-typed copies of nine evidence shapes.

r349 stated the rule and proved it twice in the same session: every
hand-typed copy of a closed set drifts by exactly the amount the set has
grown since someone typed it. ``audit --tag``'s help had drifted to seven
of nine tags because two tags were appended to ``AUDIT_TAGS`` without
revisiting the prose, and the fix was to render the help from the source
so the copy that can go stale no longer exists.

``AUDIT_TAG_EXPLAIN`` is the next copy, and it cannot be rendered the same
way. r202 established that ``audit --explain`` runs NO audit — the face is
static data by design — so the evidence description has to stay
hand-written prose. That makes the r349 remedy unavailable, and it makes
the drift it cannot prevent real:

    "thin-evidence" live keys:  count, row_text, rows, verifier
    "thin-evidence" doc string: "row index, the verifier text,
                                 the rows sharing it"

The entry named a ``row`` key that does not exist and never mentioned
``row_text`` or ``count``. The drift happened INSIDE r341: the entry was
written first, and ``row_text`` was added to the evidence later in the
same round so the r245 framing had a row pointer to ride. The round's own
tests asserted the entry was PRESENT and its three fields were non-empty —
never that it matched what the detector emits — so a green suite
coexisted with a wrong doc.

THE FIX has two halves, because the drift has two sides.

  1. The entry now names all four keys the detector emits.
  2. A test fires EVERY tag on ledgers built to trip all nine (plus a
     second ledger for ``delete``'s answered-by branch), reads the LIVE
     evidence keys each detector emits, and asserts both directions:
     every key has a corresponding phrase in the entry, and the phrase
     map covers exactly the keys that exist — no orphans naming keys
     the detector dropped.

The second half is the r349-style guard rebuilt for a copy that cannot
be rendered: the phrase map lives in the TEST, so a detector that gains
or loses an evidence key fails the test until both the map and the entry
are updated. The drift becomes a red suite instead of a silent lie.

The guard is deliberately per-tag rather than generic because the
entries are prose — ``seam_indices`` is documented as "seam indices",
``row_text`` as itself — so the key-to-phrase correspondence has to be
stated once, and the two set-equalities are what keep that statement
honest in both directions.
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

CHECK = "\u2713"

# The phrase map: for each tag, each LIVE evidence key maps to the
# substring its explain entry uses to name it. This is the statement the
# two set-equalities below keep honest — a detector that gains or drops
# a key fails until both this map and the entry are updated.
PHRASES = {
    "delete": {
        "row": "row",
        "row_text": "normalised row text",
        "first_seen": "first_seen",
        "first_seen_index": "first_seen",
        # the answered_by branch of the same detector
        "answered_by": "answered_by",
        "answered_by_index": "answered_by",
    },
    "stdlib": {
        "row": "row index",
        "row_text": "normalised row text",
        "canonical": "canonical row",
        "canonical_index": "canonical row",
    },
    "thin-evidence": {
        "verifier": "the verifier text",
        "row_text": "row_text",
        "rows": "the rows sharing it",
        "count": "their count",
    },
    "yagni": {
        "core_total": "core_total",
        "live_slots": "live_slots",
        "parked": "parked count",
        "parked_indices": "parked indices",
    },
    "shrink": {
        "blank_count": "blank_count",
        "blank_indices": "blank 1-based indices",
        "history_total": "history_total",
    },
    "goal-stale": {
        "goal": "goal text",
        "window": "window size",
        "stale_indices": "stale 1-based seam indices",
        "window_first": "window brackets",
        "window_last": "window brackets",
    },
    "next-stall": {
        "next": "the next value",
        "seam_indices": "seam indices",
        "count": "count",
        "window": "window brackets",
        "window_first": "window brackets",
        "window_last": "window brackets",
    },
    "msg-stall": {
        "msg": "the msg value",
        "seam_indices": "seam indices",
        "count": "count",
        "window": "window brackets",
        "window_first": "window brackets",
        "window_last": "window brackets",
    },
    "core-drift": {
        "live_next": "live_next",
        "core_items": "core_items",
        "direction": "direction",
    },
}


def _write_ledger(ws, text):
    d = os.path.join(ws, ".mindseam")
    os.makedirs(d)
    with open(os.path.join(d, "WORKSPACE.md"), "w", encoding="utf-8") as f:
        f.write(text)
    return d


def _ledger_all_tags():
    """A workspace whose audit fires all nine tags.

    Built by firing each detector once and reading what came back:
    ``delete`` needs a duplicate Open row, ``stdlib`` a duplicate Verified
    row, ``thin-evidence`` a keyword-only verifier, ``yagni`` three parked
    Core items, ``shrink`` one blank-next history row (placed FIRST so it
    stays out of the last-5 window and does not starve ``next-stall``),
    ``goal-stale`` twelve seams with no re-anchor, ``next-stall`` a
    repeated non-blank next, ``msg-stall`` a repeated non-empty message,
    and ``core-drift`` a live Next that is not in Core.
    """
    ws = tempfile.mkdtemp()
    rows_text = [
        "# L", "", "## Goal", "g", "", "## Core",
        "- c1 — work", "- c2 — review", "- c3 — three",
        "- c4 — parked one", "- c5 — parked two", "",
        "## Verified",
        CHECK + "01 done a — verified by: brute force, n <= 6",
        CHECK + "02 done b — verified by: cases",
        CHECK + "03 done c — verified by: brute force, n <= 6",
        CHECK + "04 done a — verified by: brute force, n <= 6", "",
        "## Open",
        "?01 q — settled by: t",
        "?02 q — settled by: t", "",
        "## Next", "n", "",
    ]
    d = _write_ledger(ws, "\n".join(rows_text))
    rows = [{"t": 1700000000, "next": "", "msg": "m",
             "verified": 0, "open": 0}]
    rows += [{"t": 1700000000 + i, "next": "dom: a", "msg": "m",
              "verified": 0, "open": 0} for i in range(1, 12)]
    with open(os.path.join(d, "history.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f)
    return ws


def _ledger_answered_open():
    """A second delete branch: an Open row answered by a Verified row.

    ``delete`` has two branches and this one needs its own ledger,
    because the duplicate branch and the answered branch cannot fire on
    the same row.
    """
    ws = tempfile.mkdtemp()
    # _audit_norm strips only the ?NN / ✓NN prefix, so the two rows must
    # be byte-identical AFTER it for the answered branch to fire.
    rows_text = [
        "# L", "", "## Goal", "g", "", "## Core", "- c1 — work", "",
        "## Verified",
        CHECK + "01 done — verified by: a test", "",
        "## Open",
        "?01 done — verified by: a test", "",
        "## Next", "n", "",
    ]
    d = _write_ledger(ws, "\n".join(rows_text))
    with open(os.path.join(d, "history.json"), "w", encoding="utf-8") as f:
        json.dump([{"t": 1700000000 + i, "next": "dom: a", "msg": "m",
                    "verified": 0, "open": 0} for i in range(12)], f)
    return ws


def _live_keys():
    """The evidence keys each detector actually emits, per tag.

    Two ledgers: the all-tags ledger fires every detector, and the
    answered-Open ledger fires ``delete``'s second branch. The union of
    both is what the phrase map has to cover exactly.
    """
    out = {}
    for ledger in (_ledger_all_tags(), _ledger_answered_open()):
        p = json.loads(invoke_cli(ledger, ["audit", "--json"]).stdout)
        for finding in p["findings"]:
            out.setdefault(finding["tag"], set()).update(
                finding["evidence"].keys())
    return out


class ExplainMatchesLiveEvidenceTests(unittest.TestCase):
    """The two-sided guard: the phrase map equals the live key set."""

    def test_both_ledgers_fire_every_tag(self):
        # The guard only means something if every detector runs.
        live = _live_keys()
        for tag in mindseam.AUDIT_TAGS:
            self.assertIn(tag, live,
                          "%s did not fire; the guard cannot check it" % tag)

    def test_every_phrase_is_in_its_entry(self):
        # Direction 1: every key's phrase appears in the entry.
        live = _live_keys()
        for tag in mindseam.AUDIT_TAGS:
            entry = mindseam.AUDIT_TAG_EXPLAIN[tag]["evidence"]
            for key, phrase in PHRASES[tag].items():
                self.assertIn(phrase, entry,
                             "%s: %r names key %r nowhere"
                             % (tag, entry, key))

    def test_no_orphan_phrases(self):
        # Direction 2: the map covers exactly the live keys — an entry
        # that names a key the detector dropped is caught here.
        live = _live_keys()
        for tag in mindseam.AUDIT_TAGS:
            self.assertEqual(set(PHRASES[tag]), live[tag],
                             "%s: map=%s live=%s"
                             % (tag, sorted(PHRASES[tag]),
                                sorted(live[tag])))

    def test_the_r351_drift_is_fixed(self):
        # The exact defect: the entry once said "row index" and never
        # mentioned row_text or count.
        entry = mindseam.AUDIT_TAG_EXPLAIN["thin-evidence"]["evidence"]
        self.assertNotIn("row index", entry)
        for token in ("row_text", "count", "verifier", "rows"):
            self.assertIn(token, entry)


class ExplainFaceTests(unittest.TestCase):
    """The face still renders, and the entry is reachable through it."""

    def test_explain_thin_evidence_prints_the_new_text(self):
        ws = tempfile.mkdtemp()
        r = invoke_cli(ws, ["audit", "--explain", "thin-evidence"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("row_text", r.stdout)
        self.assertIn("their count", r.stdout)
        self.assertNotIn("row index", r.stdout)

    def test_explain_still_refuses_every_audit_flag(self):
        # r202's contract is untouched by a data fix.
        ws = tempfile.mkdtemp()
        for flag in ("--strict", "--tag", "--since", "--until", "--at",
                     "--baseline", "--baseline-write", "--format"):
            r = invoke_cli(ws, ["audit", "--explain", "delete", flag, "x"])
            self.assertEqual(r.returncode, 2, flag)

    def test_every_entry_is_nonempty(self):
        # r171's completeness contract, unchanged.
        for tag in mindseam.AUDIT_TAGS:
            for field in ("trigger", "fix", "evidence"):
                self.assertTrue(mindseam.AUDIT_TAG_EXPLAIN[tag][field],
                                "%s.%s" % (tag, field))


class RulePinnedTests(unittest.TestCase):
    """The r349 rule, stated where the next drift will be looked for."""

    def test_the_source_names_the_round(self):
        src = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(
            encoding="utf-8")
        i = src.find("# r351: this entry drifted inside its own round")
        self.assertGreater(i, 0)
        head = src[i:i + 1400]
        self.assertIn("r349", head)
        self.assertIn("row_text", head)

    def test_the_guard_covers_every_tag(self):
        # A tag added to AUDIT_TAGS without a phrase map fails here, the
        # r349 lesson applied one surface over.
        self.assertEqual(set(PHRASES), set(mindseam.AUDIT_TAGS))


class CatalogPinTests(unittest.TestCase):
    """The catalog registers the round and keeps its shape."""

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("explain-evidence-drift", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "explain-evidence-drift")
        self.assertEqual(entry["since"], "r351")
        self.assertIn("thin-evidence", entry["summary"])
        self.assertIn("r349", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 201 before r351; one entry lands.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 202)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertTrue(callable(mindseam.audit_findings))
        self.assertEqual(len(mindseam.AUDIT_TAG_EXPLAIN),
                         len(mindseam.AUDIT_TAGS))


if __name__ == "__main__":
    unittest.main()
