# -*- coding: utf-8 -*-
"""r357 — the sub-projector machine faces narrowed silently.

r324 gave the general ``history --json`` face its disclosure keys and
scoped the fix to that face; r354 extended the same keys to the
truncation selectors on the same face and scoped out the
sub-projectors again, "r324 scoped to the general face and this round
follows the same scoping". Two rounds of scoping left three faces that
ship rows with NO disclosure at all. Live before-fix, on a five-row
history:

    history --csv   --json --head 2  -> rows=2 under
                                        {columns, rows, untrusted}
    history --dedup --json --head 2  -> rows=2 under
                                        {history_count, unique_count,
                                         by, rows, untrusted}
    history --empty --json --since 3600 -> no key naming the window

A host reading the --csv machine face could not tell a head-truncated
window from a two-row history — the exact pre-r324 lie, surviving on
the faces the pre-r324 round itself had set aside.

The fix extracts the disclosure keys into ONE helper
(``_history_narrowing_payload``) that every row-shipping face spreads
into its payload: the general face keeps r354's exact key order and
semantics (the --tail alias still fills the limit key), and the three
sub-faces gain the same eight keys — null when unset, so each face's
key set is stable, and the same narrowing says the same thing on
every face. --span and --domains stay scoped out: they are aggregate
reflections, not row shipments; --row-id refuses narrowing outright
(r276/r320), so it has nothing to disclose.
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

ROWS = [{"t": 1700000000 + i, "next": "dom%d: action %d" % (i % 3, i),
         "msg": "m%d" % (i % 2), "verified": 1, "open": 0} for i in range(5)]

NARROWING_KEYS = ("head", "limit", "since", "until", "grep", "exclude",
                  "filter", "empty", "keep", "reverse")
CSV_KEYS = sorted(["columns", "rows", "untrusted"] + list(NARROWING_KEYS))
DEDUP_KEYS = sorted(["history_count", "unique_count", "by", "rows",
                     "untrusted"] + list(NARROWING_KEYS))
EMPTY_KEYS = sorted(["history_count", "rows", "untrusted"]
                    + list(NARROWING_KEYS))


class SubProjectorBase(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        d = os.path.join(self.ws, ".mindseam")
        os.makedirs(d)
        with open(os.path.join(d, "history.json"), "w",
                  encoding="utf-8") as f:
            json.dump(ROWS, f)

    def _json(self, *flags):
        r = invoke_cli(self.ws, ["history", "--json", *flags])
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class CsvFaceTests(SubProjectorBase):
    def test_head_is_disclosed(self):
        payload = self._json("--csv", "--head", "2")
        self.assertEqual(len(payload["rows"]), 2)
        self.assertEqual(payload["head"], 2)

    def test_grep_is_disclosed(self):
        payload = self._json("--csv", "--grep", "dom0")
        self.assertEqual(payload["grep"], "dom0")
        self.assertEqual(len(payload["rows"]), 2)

    def test_key_set_is_stable_and_null_when_unset(self):
        payload = self._json("--csv")
        self.assertEqual(sorted(payload.keys()), CSV_KEYS)
        for key in NARROWING_KEYS:
            self.assertIsNone(payload[key]) if key not in ("reverse", "empty") else \
                self.assertIsInstance(payload[key], bool)
        self.assertEqual(len(payload["rows"]), 5)

    def test_r299_machine_shape_still_holds(self):
        payload = self._json("--csv", "--head", "2")
        self.assertEqual(payload["columns"],
                         ["t", "next", "verified", "open"])
        # untrusted is keyed by row INDEX and holds only flagged rows,
        # so a clean fixture yields {} — the shape, not the length,
        # is the contract.
        self.assertIsInstance(payload["untrusted"], dict)
        self.assertEqual(payload["untrusted"], {})


class DedupFaceTests(SubProjectorBase):
    def test_head_is_disclosed(self):
        payload = self._json("--dedup", "--head", "2")
        self.assertEqual(len(payload["rows"]), 2)
        self.assertEqual(payload["head"], 2)

    def test_tail_fills_the_limit_key_here_too(self):
        # One helper, so the r354 alias semantics ride along.
        payload = self._json("--dedup", "--tail", "2")
        self.assertEqual(payload["limit"], 2)
        self.assertIsNone(payload["head"])

    def test_key_set_is_stable_and_null_when_unset(self):
        payload = self._json("--dedup")
        self.assertEqual(sorted(payload.keys()), DEDUP_KEYS)
        for key in NARROWING_KEYS:
            self.assertIsNone(payload[key]) if key not in ("reverse", "empty") else \
                self.assertIsInstance(payload[key], bool)

    def test_r277_untrusted_map_still_rides(self):
        payload = self._json("--dedup", "--head", "2")
        self.assertIsInstance(payload["untrusted"], dict)
        self.assertEqual(payload["untrusted"], {})


class EmptyFaceTests(SubProjectorBase):
    def test_since_is_disclosed(self):
        payload = self._json("--empty", "--since", "3600")
        self.assertEqual(payload["since"], 3600)
        self.assertEqual(payload["rows"], [])

    def test_key_set_is_stable_and_null_when_unset(self):
        payload = self._json("--empty")
        self.assertEqual(sorted(payload.keys()), EMPTY_KEYS)
        for key in NARROWING_KEYS:
            self.assertIsNone(payload[key]) if key not in ("reverse", "empty") else \
                self.assertIsInstance(payload[key], bool)

    def test_r277_untrusted_map_still_rides(self):
        payload = self._json("--empty")
        self.assertEqual(payload["untrusted"], {})


class GeneralFaceRegressionTests(SubProjectorBase):
    def test_r354_semantics_unchanged_through_the_helper(self):
        self.assertEqual(self._json("--head", "2")["head"], 2)
        self.assertIsNone(self._json("--head", "2")["limit"])
        self.assertEqual(self._json("--tail", "2")["limit"], 2)
        self.assertEqual(self._json("--limit", "2")["limit"], 2)
        self.assertEqual(self._json("--keep", "3")["keep"], 3)

    def test_general_key_set_matches_r354(self):
        self.assertEqual(
            sorted(self._json().keys()),
            sorted(["history_count", "rows"] + list(NARROWING_KEYS)
                   + ["untrusted"]))

    def test_the_helper_is_the_single_source(self):
        payload = mindseam._history_narrowing_payload(
            self._args_for(head=None, tail=4), None, None, None, None,
            None)
        self.assertEqual(sorted(payload.keys()), sorted(NARROWING_KEYS))
        self.assertEqual(payload["limit"], 4)

    def _args_for(self, **kw):
        import argparse
        ns = argparse.Namespace()
        for key in ("head", "tail", "limit", "keep", "grep", "exclude"):
            setattr(ns, key, None)
        ns.reverse = False
        for key, val in kw.items():
            setattr(ns, key, val)
        return ns


class NeighbouringGuardsTests(SubProjectorBase):
    def test_csv_text_face_has_no_json_keys(self):
        # The --csv TEXT face is data for a parser — no disclosure keys
        # ride into the cells.
        r = invoke_cli(self.ws, ["history", "--csv", "--head", "2"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0],
                         "t,next,verified,open")

    def test_r320_row_id_still_refuses_narrowing(self):
        for flag in (["--head", "2"], ["--limit", "2"]):
            r = invoke_cli(self.ws, ["history", "--row-id", "1", *flag])
            self.assertEqual(r.returncode, 2, flag)
            self.assertIn("CANNOT", r.stderr)

    def test_r278_empty_filter_then_truncate_unchanged(self):
        # dom0 rows are i=0 and i=3; --head 1 keeps the first (oldest).
        payload = self._json("--empty", "--grep", "dom0", "--head", "1")
        self.assertEqual(payload["rows"], [])

    def test_r217_negative_refusal_precedes_every_face(self):
        for extra in (["--csv"], ["--dedup"], ["--empty"]):
            r = invoke_cli(self.ws, ["history", *extra, "--head", "-1"])
            self.assertEqual(r.returncode, 2, extra)
            self.assertIn("CANNOT", r.stderr)


class CatalogPinTests(unittest.TestCase):
    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("subprojector-faces-disclosed", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "subprojector-faces-disclosed")
        self.assertEqual(entry["since"], "r357")
        self.assertIn("--csv", entry["summary"])
        self.assertIn("--dedup", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 207 before r357; later rounds keep appending above it, so this
        # pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 208)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertTrue(callable(mindseam._history_narrowing_payload))
        self.assertTrue(callable(mindseam.scan_untrusted))


if __name__ == "__main__":
    unittest.main()
