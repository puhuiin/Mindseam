# -*- coding: utf-8 -*-
"""Round 316 guards: _row_* helpers and fact_age_seconds tolerate
malformed values.

The helpers did (row.get(K) or '').strip() — a truthy non-string
passed the or-guard and crashed .strip(). fact_age_seconds did
int((h.get('t') or 0)) and crashed on t: 'x'.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


class RowHelpersTypeGuardTests(unittest.TestCase):

    def test_nonstring_fields_treated_as_absent(self):
        row = {"next": 5, "error": 3.14, "outcome": [], "marker": {},
               "confidence": True, "verifier": b"x"}
        self.assertEqual(mindseam._row_next(row), "")
        self.assertEqual(mindseam._row_error(row), "")
        self.assertEqual(mindseam._row_outcome(row), "")
        self.assertEqual(mindseam._row_marker(row), "")
        self.assertEqual(mindseam._row_confidence(row), "")
        self.assertEqual(mindseam._row_verifier(row), "")

    def test_string_fields_still_strip(self):
        row = {"next": "  a: one  ", "marker": "  GO  ",
               "confidence": " strong "}
        self.assertEqual(mindseam._row_next(row), "a: one")
        self.assertEqual(mindseam._row_marker(row), "GO")
        self.assertEqual(mindseam._row_confidence(row), "strong")

    def test_missing_fields_still_empty(self):
        self.assertEqual(mindseam._row_next({}), "")
        self.assertEqual(mindseam._row_marker({}), "")

    def test_fact_age_nonint_t_is_zero(self):
        for t in ("x", 3.14, True, [], {}, None):
            age = mindseam.fact_age_seconds([{"t": t, "next": "a"}])
            self.assertIsInstance(age, int)

    def test_fact_age_valid_t_unchanged(self):
        import time
        now = int(time.time())
        age = mindseam.fact_age_seconds([{"t": now, "next": "a"}])
        self.assertLessEqual(age, 2)

    def test_assess_risk_degenerate_rows(self):
        level, reasons = mindseam.assess_risk([
            {"confidence": 3.14, "marker": {}},
            {"next": 5, "risk": ["low"]},
        ])
        self.assertIn(level, ("low", "medium", "high"))

    def test_extract_skillbook_degenerate_rows(self):
        entries = mindseam.extract_skillbook([
            {"error": 5, "outcome": {}, "next": 3.14, "extra_steps": "x"},
        ])
        self.assertIsInstance(entries, list)

    def test_all_hist_functions_tolerate_degenerate(self):
        import inspect
        degenerate = [
            [{}],
            [{"t": "x", "next": 5, "verified": "y", "marker": {}}],
            [{"t": True, "next": None, "confidence": 3.14}],
            [{"foo": "bar"}],
        ]
        for name in dir(mindseam):
            if name.startswith("_"):
                continue
            fn = getattr(mindseam, name)
            if not callable(fn):
                continue
            try:
                params = list(inspect.signature(fn).parameters.keys())
            except Exception:
                continue
            if not params or params[0] not in ("hist", "history"):
                continue
            for hist in degenerate:
                try:
                    fn(hist)
                except TypeError:
                    pass
                except (SystemExit, KeyboardInterrupt):
                    pass
                except Exception as exc:
                    self.fail("%s crashed on %r: %s" % (name, hist, exc))

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("row-helpers-type-guard", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "row-helpers-type-guard")
        self.assertEqual(entry["since"], "r316")
        self.assertIn("isinstance", entry["summary"])


if __name__ == "__main__":
    unittest.main()
