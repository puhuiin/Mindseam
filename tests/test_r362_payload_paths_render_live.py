# -*- coding: utf-8 -*-
"""r362 — the payload-path schema never named most of the payload.

r361 rendered the schema's history_row section from
``HISTORY_ROW_FIELDS`` and left ``info_payload`` for this round: its
hand copy listed SIX paths (ledger, history_count, last_seam.t,
last_seam.gap_seconds, last_seam.long_gap, warnings) while the live
``info --json`` payload carries ELEVEN top-level keys. Seven blocks
were never named — audit_summary, lock_state, meta_keys, risk,
skillbook_entries, untrusted and features — and every one of them is
addressable by ``info --format`` right now:

    info --format audit_summary.net   -> printed 5, at exit 0,
                                         while the schema stayed
                                         silent about the block

A host that built a --format consumer off the introspection face
(the face whose docstring promises to describe "what info will
produce") would not know those paths exist — the r349 shape one
layer up from r361, complicated by the payload key set being PARTLY
dynamic (r189 computes audit_summary lazily; --content-hash,
--changed, --health, --manifest, --mtime and --workspace-id add
their blocks only when asked).

The guard shape that fits: INFO_PAYLOAD_DOCS describes the
ALWAYS-PRESENT payload, and the test pins its first segments against
the top-level keys of a REAL invocation in both directions — no
orphan path naming a block that is not there, no live block without
a path. The flag-conditional blocks are deliberately out of scope
(their flags document them) and the scoping is itself pinned:
content_hash must NOT be in the table, because a no-flag invocation
never carries it.
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


class PayloadSchemaBase(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        d = os.path.join(self.ws, ".mindseam")
        os.makedirs(d)
        with open(os.path.join(d, "WORKSPACE.md"), "w",
                  encoding="utf-8") as f:
            f.write("# Mindseam Workspace Ledger\n\n## Goal\ng\n\n"
                    "## Core\n\n## Verified\n\n## Open\n\n## Next\n\n")
        with open(os.path.join(d, "history.json"), "w",
                  encoding="utf-8") as f:
            json.dump([], f)

    def _live_keys(self):
        r = invoke_cli(self.ws, ["info", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        return set(json.loads(r.stdout).keys())

    def _schema(self):
        r = invoke_cli(self.ws, ["info", "--list-fields", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class PayloadPathCompletenessTests(PayloadSchemaBase):
    def test_schema_first_segments_cover_the_live_payload(self):
        # BOTH directions, against a real invocation: no orphan path,
        # no live block without a path.
        schema = self._schema()
        firsts = {p.split(".")[0] for p in schema["info_payload"]}
        live = self._live_keys()
        self.assertEqual(firsts, live)

    def test_the_docs_table_matches_the_schema_and_the_live_payload(self):
        firsts = {p.split(".")[0] for p in mindseam.INFO_PAYLOAD_DOCS}
        self.assertEqual(firsts, self._live_keys())
        self.assertEqual(sorted(mindseam.INFO_PAYLOAD_DOCS),
                         sorted(self._schema()["info_payload"]))

    def test_every_doc_is_non_empty(self):
        for path, doc in mindseam.INFO_PAYLOAD_DOCS.items():
            self.assertTrue(doc.strip(), "%s has an empty doc" % path)

    def test_every_top_level_path_formats_live(self):
        for path in mindseam.INFO_PAYLOAD_DOCS:
            r = invoke_cli(self.ws, ["info", "--format", path])
            self.assertEqual(r.returncode, 0,
                             "--format %s refused" % path)

    def test_the_six_original_paths_survive(self):
        # No regression: the hand copy's six entries are all still
        # described.
        for path in ("ledger", "history_count", "last_seam.t",
                     "last_seam.gap_seconds", "last_seam.long_gap",
                     "warnings"):
            self.assertIn(path, mindseam.INFO_PAYLOAD_DOCS)

    def test_the_seven_newly_named_blocks_are_present(self):
        for first in ("audit_summary", "lock_state", "meta_keys",
                      "risk", "skillbook_entries", "untrusted",
                      "features"):
            self.assertIn(first, mindseam.INFO_PAYLOAD_DOCS)


class ScopingTests(PayloadSchemaBase):
    def test_flag_conditional_blocks_stay_out(self):
        # --content-hash adds its block only when asked; the table
        # describes the ALWAYS-PRESENT payload, so naming it here
        # would break the two-directional pin on a no-flag call.
        self.assertNotIn("content_hash", mindseam.INFO_PAYLOAD_DOCS)
        self.assertNotIn("changed", mindseam.INFO_PAYLOAD_DOCS)

    def test_r361_history_row_guard_still_holds(self):
        schema = self._schema()
        self.assertEqual(list(schema["history_row"].keys()),
                         list(mindseam.HISTORY_ROW_FIELDS))

    def test_r167_features_is_always_populated(self):
        self.assertIn("features", self._live_keys())

    def test_format_of_a_new_path_actually_renders(self):
        # The before-fix repro: the block was real, the schema was
        # silent. Now both the block and its path are documented AND
        # the path renders a value from the live payload.
        r = invoke_cli(self.ws, ["info", "--format", "audit_summary.net"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(r.stdout.strip(),
                      {"0", "", "-"},
                      "unexpected rendering: %r" % r.stdout)


class CatalogPinTests(unittest.TestCase):
    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("payload-paths-render-live", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "payload-paths-render-live")
        self.assertEqual(entry["since"], "r362")
        self.assertIn("INFO_PAYLOAD_DOCS", entry["summary"])
        self.assertIn("audit_summary", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 212 before r362; later rounds keep appending above it, so this
        # pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 213)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertTrue(mindseam.INFO_PAYLOAD_DOCS)
        self.assertTrue(callable(mindseam.scan_untrusted))


if __name__ == "__main__":
    unittest.main()
