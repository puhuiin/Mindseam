# -*- coding: utf-8 -*-
"""r363 — an all-empty --tag was not "no tag", it was silence.

``--tag`` parses comma-separated names with
``[t.strip() for t in tags.split(",") if t.strip()]``, so a value of
``,`` or ``,,`` or `` , `` filtered down to an empty ``chosen`` — and
the empty list fell through the ``if chosen:`` projection branch as
if no tag had been given at all. Live before-fix, on a ledger with
five findings:

    audit --json            -> 5 findings, tags = all nine
    audit --json --tag ,    -> 5 findings, tags = all nine
    audit --json --tag ,,,  -> 5 findings, tags = all nine

Byte-identical to a bare audit at exit 0: the flag was given, the
projection silently dropped, and the JSON ``tags`` key even answered
with the FULL tag list — no face could tell a dropped flag from a
full audit. The r310 principle applies directly: an empty needle is
not the absence of a needle (`--grep ''` was refused for the same
reason on the history face), and here the silent drop is worse
because the caller asked for a PROJECTION and got the whole picture.

The fix refuses a value that names nothing with exit 2, naming the
tags the caller meant to choose from (rendered from AUDIT_TAGS, the
r349-rendered list the unknown-tag refusal already uses). Mixed
values keep working — `--tag " shrink ,,"` still projects to shrink,
because a whitespace segment between commas is separator noise, not
a needle; only a value whose every segment is empty is refused.
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


class TagBase(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        d = os.path.join(self.ws, ".mindseam")
        os.makedirs(d)
        with open(os.path.join(d, "WORKSPACE.md"), "w",
                  encoding="utf-8") as f:
            f.write("# Mindseam Workspace Ledger\n\n## Goal\ng\n\n"
                    "## Core\n- c1 — work\n- c2 — review\n- c3 — three\n\n"
                    "## Verified\n\n## Open\n\n## Next\nbuild: the parser\n")
        rows = [{"t": 1700000000 + i, "next": "build: the parser",
                 "msg": "m", "verified": 1, "open": 0} for i in range(12)]
        with open(os.path.join(d, "history.json"), "w",
                  encoding="utf-8") as f:
            json.dump(rows, f)


class EmptyTagProjectionTests(TagBase):
    def test_every_all_empty_value_is_refused(self):
        for value in (",", ",,", " , ", " ", " , , "):
            r = invoke_cli(self.ws, ["audit", "--json", "--tag", value])
            self.assertEqual(r.returncode, 2, repr(value))
            self.assertIn("CANNOT: --tag %r names no tag." % value,
                          r.stderr)
            self.assertIn(", ".join(mindseam.AUDIT_TAGS), r.stderr)
            self.assertEqual(r.stdout, "", repr(value))

    def test_mixed_value_still_projects(self):
        # A blank segment between commas is separator noise, not a
        # needle; only a value that names NOTHING is refused.
        r = invoke_cli(self.ws, ["audit", "--json", "--tag", " shrink ,,"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["tags"], ["shrink"])

    def test_the_before_fix_repro_now_differs_from_bare(self):
        bare = invoke_cli(self.ws, ["audit", "--json"])
        dropped = invoke_cli(self.ws, ["audit", "--json", "--tag", ",,"])
        self.assertEqual(bare.returncode, 0)
        self.assertEqual(dropped.returncode, 2)
        self.assertNotEqual(bare.stdout, dropped.stdout)

    def test_single_valid_tag_unchanged(self):
        # r159/r349's projection, re-pinned through the new guard.
        payload = json.loads(invoke_cli(
            self.ws, ["audit", "--json", "--tag",
                      "next-stall"]).stdout)
        self.assertEqual(payload["tags"], ["next-stall"])
        self.assertEqual(sorted({f["tag"] for f in payload["findings"]}),
                         ["next-stall"])


class NeighbouringGuardsTests(TagBase):
    def test_r159_unknown_tag_refusal_untouched(self):
        r = invoke_cli(self.ws, ["audit", "--tag", "bogus"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("is not a recognised audit tag", r.stderr)
        self.assertIn(", ".join(mindseam.AUDIT_TAGS), r.stderr)

    def test_r349_tag_help_still_renders_every_tag(self):
        r = invoke_cli(self.ws, ["audit", "--help"])
        self.assertEqual(r.returncode, 0)
        flat = " ".join(r.stdout.split())
        for tag in mindseam.AUDIT_TAGS:
            self.assertIn(tag, flat)

    def test_r328_repeated_tag_still_refused(self):
        r = invoke_cli(self.ws, ["audit", "--tag", "shrink",
                                 "--tag", "goal-stale"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)

    def test_r310_empty_needle_refusal_on_history_unchanged(self):
        # The family precedent, re-pinned: history --grep '' refuses.
        r = invoke_cli(self.ws, ["history", "--grep", ""])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)

    def test_explain_face_refuses_an_empty_name_independently(self):
        # --explain takes its own value and its own static face; an
        # empty name is simply not a tag there.
        r = invoke_cli(self.ws, ["audit", "--explain", ","])
        self.assertEqual(r.returncode, 2)
        self.assertIn("is not a recognised audit tag", r.stderr)


class CatalogPinTests(unittest.TestCase):
    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("empty-tag-projection-refused", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "empty-tag-projection-refused")
        self.assertEqual(entry["since"], "r363")
        self.assertIn("r310", entry["summary"])
        self.assertIn("AUDIT_TAGS", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 213 before r363; later rounds keep appending above it, so this
        # pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 214)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertTrue(callable(mindseam.scan_untrusted))


if __name__ == "__main__":
    unittest.main()
