# -*- coding: utf-8 -*-
"""Round 322 guards: detector entry points skip non-dict rows.

A history list with [1, 'x', {...}] crashed every inline h.get() in
the detector family. read_history drops non-dicts, but the detectors
are callable directly.
"""

import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam

ENTRY_POINTS = (
    "observations", "session_health_score", "heal_actions",
    "assess_risk", "extract_skillbook", "detect_stall",
    "detect_volatility", "detect_recovery", "detect_risk_escalation",
)


class HistRowTypeGuardTests(unittest.TestCase):

    def test_dict_rows_filters_non_dicts(self):
        rows = mindseam._dict_rows([1, "x", {"a": 1}, None, True])
        self.assertEqual(rows, [{"a": 1}])

    def test_dict_rows_nonlist_is_empty(self):
        self.assertEqual(mindseam._dict_rows(None), [])
        self.assertEqual(mindseam._dict_rows(5), [])
        self.assertEqual(mindseam._dict_rows("x"), [])

    def test_entry_points_tolerate_non_dict_rows(self):
        degenerate = [1, "x", {"t": 1, "next": "a: one"}, None, True]
        for name in ENTRY_POINTS:
            fn = getattr(mindseam, name)
            try:
                fn(degenerate)
            except TypeError:
                pass
            except (SystemExit, KeyboardInterrupt):
                pass
            except Exception as exc:
                self.fail("%s crashed on non-dict rows: %s" % (name, exc))

    def test_entry_points_tolerate_all_nondict(self):
        for name in ENTRY_POINTS:
            fn = getattr(mindseam, name)
            try:
                fn([1, "x", None])
            except TypeError:
                pass
            except (SystemExit, KeyboardInterrupt):
                pass
            except Exception as exc:
                self.fail("%s crashed on all-nondict: %s" % (name, exc))

    def test_entry_points_tolerate_empty(self):
        for name in ENTRY_POINTS:
            fn = getattr(mindseam, name)
            try:
                fn([])
            except TypeError:
                pass
            except (SystemExit, KeyboardInterrupt):
                pass
            except Exception as exc:
                self.fail("%s crashed on empty: %s" % (name, exc))

    def test_valid_rows_unchanged(self):
        rows = [{"t": 1, "next": "a: one", "verified": 0, "open": 0,
                 "marker": "", "confidence": ""}]
        level, reasons = mindseam.assess_risk(rows)
        self.assertIn(level, ("low", "medium", "high"))
        entries = mindseam.extract_skillbook(rows)
        self.assertIsInstance(entries, list)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("hist-row-type-guard", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "hist-row-type-guard")
        self.assertEqual(entry["since"], "r322")
        self.assertIn("_dict_rows", entry["summary"])


if __name__ == "__main__":
    unittest.main()
