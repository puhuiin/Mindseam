# -*- coding: utf-8 -*-
"""Round 317 guards: book-side helpers tolerate malformed values.

r316 hardened the _row_* helpers against malformed history rows.
one(), last_verifier, print_ledger, stale_core_count, append_history,
_audit_norm and audit_findings' goal-stale path kept the same shape of
hole on the book side.
"""

import contextlib
import inspect
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def _book(**kw):
    d = {"Goal": ["g"], "Core": [], "Verified": [], "Open": [],
         "Next": ["a: one"]}
    d.update(kw)
    return d


class BookHelpersTypeGuardTests(unittest.TestCase):

    def test_one_nonlist_is_empty(self):
        self.assertEqual(mindseam.one({"Next": {"a": 1}}, "Next"), "")
        self.assertEqual(mindseam.one({"Next": 5}, "Next"), "")
        self.assertEqual(mindseam.one({}, "Next"), "")
        self.assertEqual(mindseam.one(_book(), "Next"), "a: one")

    def test_last_verifier_missing_key(self):
        self.assertEqual(mindseam.last_verifier({}), "")
        self.assertEqual(mindseam.last_verifier({"Verified": [1]}), "")

    def test_print_ledger_degenerate(self):
        for bk in ({}, {"Core": {}}, {"Verified": 5}, {"Goal": "g"}):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                mindseam.print_ledger(bk)
            self.assertIn("Goal", buf.getvalue())

    def test_print_full_ledger_degenerate(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mindseam.print_full_ledger({"Core": [{}], "Verified": [1],
                                        "Open": [None], "Next": [True]})
        self.assertIn("Core", buf.getvalue())

    def test_stale_core_count_degenerate(self):
        n = mindseam.stale_core_count({"Core": [{}], "Verified": [1]})
        self.assertIsInstance(n, int)

    def test_append_history_degenerate(self):
        hist, reasons, problem = mindseam.append_history(
            {"Next": {"a": 1}, "Verified": 5}, write=False)
        self.assertIsInstance(hist, list)

    def test_audit_norm_nonstring(self):
        self.assertEqual(mindseam._audit_norm(1), "")
        self.assertEqual(mindseam._audit_norm(["x"]), "")
        self.assertEqual(mindseam._audit_norm(None), "")

    def test_audit_findings_degenerate_book(self):
        findings = mindseam.audit_findings(
            {"Goal": [["g"]], "Core": [{}], "Verified": [1],
             "Open": [None], "Next": [True]},
            [{"t": 1, "next": 5}])
        self.assertIsInstance(findings, list)

    def test_all_book_functions_tolerate_degenerate(self):
        degenerate = [
            {},
            {"Goal": None, "Core": None, "Verified": None,
             "Open": None, "Next": None},
            {"Goal": "g", "Core": {}, "Verified": 5, "Open": [],
             "Next": {"a": 1}},
            {"foo": "bar"},
            {"Goal": [["g"]], "Core": [{}], "Verified": [1],
             "Open": [None], "Next": [True]},
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
            if not params or params[0] not in ("book", "ledger"):
                continue
            for bk in degenerate:
                try:
                    fn(bk)
                except TypeError:
                    pass
                except (SystemExit, KeyboardInterrupt):
                    pass
                except Exception as exc:
                    self.fail("%s crashed on %r: %s" % (name, bk, exc))

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("book-helpers-type-guard", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "book-helpers-type-guard")
        self.assertEqual(entry["since"], "r317")
        self.assertIn("validate_book", entry["summary"])


if __name__ == "__main__":
    unittest.main()
