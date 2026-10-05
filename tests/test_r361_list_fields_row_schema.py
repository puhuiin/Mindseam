# -*- coding: utf-8 -*-
"""r361 — the self-describing schema understated its own row schema.

``info --list-fields`` exists so "a host or human can introspect what
info / history / seam will produce without reading the source", and
its docstring promises "both expose the same section names and field
names" across the text and JSON faces. But the schema's
``history_row`` section was a HAND-TYPED copy of the row schema that
stopped at the five original fields — while ``HISTORY_ROW_FIELDS``
carries TWELVE. The seven r4-era detector fields (marker, confidence,
verifier, risk, error, outcome, extra_steps) were invisible on the
one face whose whole job is self-description, and the CLI
contradicted itself live:

    info --list-fields --json     -> history_row has 5 keys
    history --filter confidence=0 -> rc 0 (the field is accepted)
    history --fields confidence,verifier -> rc 0

A host that built a consumer off the schema would believe confidence
or risk could not be filtered on — the r349 shape, where the closed
set (HISTORY_ROW_FIELDS) is owned by the filter/field validators and
the reporting face was a hand copy that predated the detector layer.

The fix renders the schema's key set from HISTORY_ROW_FIELDS itself;
the prose stays hand-written in HISTORY_ROW_FIELD_DOCS, which the
test pins against HISTORY_ROW_FIELDS in BOTH directions (no missing
doc, no orphan doc — r351's discipline for prose that cannot be
derived). The ledger section gets the same two-directional guard
against SECTIONS, and a live call per field proves --filter accepts
everything the schema now describes.
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


class SchemaBase(unittest.TestCase):
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

    def _schema(self):
        r = invoke_cli(self.ws, ["info", "--list-fields", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class SchemaCompletenessTests(SchemaBase):
    def test_history_row_keys_render_from_the_authority(self):
        schema = self._schema()
        self.assertEqual(list(schema["history_row"].keys()),
                         list(mindseam.HISTORY_ROW_FIELDS))

    def test_every_schema_field_is_accepted_by_filter_live(self):
        for name in mindseam.HISTORY_ROW_FIELDS:
            r = invoke_cli(self.ws, ["history", "--json",
                                     "--filter", "%s=" % name])
            self.assertEqual(r.returncode, 0,
                             "--filter %s= refused" % name)

    def test_every_schema_field_is_accepted_by_fields_live(self):
        r = invoke_cli(self.ws, ["history", "--fields",
                                 ",".join(mindseam.HISTORY_ROW_FIELDS)])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_ledger_keys_match_sections(self):
        schema = self._schema()
        self.assertEqual(list(schema["ledger"].keys()),
                         [s.lower() for s in mindseam.SECTIONS])

    def test_the_docs_table_covers_the_fields_both_ways(self):
        # r351's discipline: the prose cannot be derived, so the guard
        # pins it — every field has a doc, and no doc names a field
        # that does not exist.
        self.assertEqual(sorted(mindseam.HISTORY_ROW_FIELD_DOCS),
                         sorted(mindseam.HISTORY_ROW_FIELDS))
        for name, doc in mindseam.HISTORY_ROW_FIELD_DOCS.items():
            self.assertTrue(doc.strip(), "%s has an empty doc" % name)

    def test_risk_doc_names_its_closed_domain(self):
        # risk is not free text — RISK_LEVELS is a closed domain the
        # health score indexes; the schema says so.
        doc = mindseam.HISTORY_ROW_FIELD_DOCS["risk"]
        for lv in mindseam.RISK_LEVELS:
            self.assertIn(lv, doc)


class TextFaceTests(SchemaBase):
    def test_text_face_renders_every_field(self):
        r = invoke_cli(self.ws, ["info", "--list-fields"])
        self.assertEqual(r.returncode, 0, r.stderr)
        block = r.stdout.split("── mindseam ─ info history_row")[1]
        block = block.split("── mindseam ─")[0]
        rows = [l for l in block.splitlines() if l.strip()]
        self.assertEqual(len(rows), len(mindseam.HISTORY_ROW_FIELDS))

    def test_both_faces_expose_the_same_vocabulary(self):
        # The docstring's promise, pinned: text and JSON carry the
        # same section names and field names.
        schema = self._schema()
        r = invoke_cli(self.ws, ["info", "--list-fields"])
        for section, fields in schema.items():
            self.assertIn("── mindseam ─ info %s" % section, r.stdout)
            for name in fields:
                self.assertIn(name, r.stdout)


class NeighbouringGuardsTests(SchemaBase):
    def test_unknown_field_still_refused(self):
        r = invoke_cli(self.ws, ["history", "--filter", "bogus=1"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)
        r = invoke_cli(self.ws, ["history", "--fields", "bogus"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)

    def test_filter_renders_the_field_set_in_its_refusal(self):
        # The refusal message renders HISTORY_ROW_FIELDS — the same
        # authority the schema now renders from.
        r = invoke_cli(self.ws, ["history", "--filter", "bogus=1"])
        self.assertIn("fields: %s" % ", ".join(mindseam.HISTORY_ROW_FIELDS),
                      r.stderr)

    def test_risk_repair_boundary_untouched(self):
        # risk values outside RISK_LEVELS are repaired at the boundary
        # (r316-era guard) — the schema describing the domain does not
        # change the repair.
        ws = self.ws
        d = os.path.join(ws, ".mindseam")
        rows = [{"t": 1, "next": "x: y", "verified": 0, "open": 0,
                 "msg": "", "risk": "catastrophic"}]
        with open(os.path.join(d, "history.json"), "w",
                  encoding="utf-8") as f:
            json.dump(rows, f)
        r = invoke_cli(ws, ["history", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        repaired = [row.get("risk", "") for row in payload["rows"]]
        self.assertEqual(repaired, [""])


class CatalogPinTests(unittest.TestCase):
    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("list-fields-renders-row-fields", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "list-fields-renders-row-fields")
        self.assertEqual(entry["since"], "r361")
        self.assertIn("HISTORY_ROW_FIELDS", entry["summary"])
        self.assertIn("twelve", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 211 before r361; later rounds keep appending above it, so this
        # pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 212)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertEqual(len(mindseam.HISTORY_ROW_FIELDS), 12)
        self.assertTrue(callable(mindseam.scan_untrusted))


if __name__ == "__main__":
    unittest.main()
