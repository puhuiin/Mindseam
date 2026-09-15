# -*- coding: utf-8 -*-
"""Round 238 guards: retread prior strip and assumption_diversity book disclosure.

Two small closures on the r227-r237 family:

1. narrative_knot_detector's ``prior_nexts`` set comprehension filtered
   on ``r.get("next")`` truthiness while mapping through ``_row_next``
   — a whitespace-only prior counted as a prior. r238 strips the
   filter.

2. assumption_diversity declares ``book`` and never reads it. The r43
   finding treated that as signature-uniform (harmless); r223 taught
   the disclosure pattern for unused params. This round adds the
   disclosure.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam

SOURCE = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(encoding="utf-8")


def _row(i, **kw):
    base = {
        "t": i, "next": "build: x", "verified": 0, "open": 0,
        "marker": "DONE", "confidence": "strong",
        "verifier": "pytest", "risk": "low",
        "error": "", "outcome": "", "extra_steps": 0,
    }
    base.update(kw)
    return base


class RetreadPriorStripAndBookDisclosureTests(unittest.TestCase):

    def test_prior_nexts_ignores_whitespace_prior(self):
        # narrative_knot_detector: six whitespace priors then a real
        # next. The whitespace rows must not form a prior set the
        # real next retreads. Need >= STALL_RUN*2 (6) rows.
        hist = [_row(i, next="   ") for i in range(1, 7)]
        hist.append(_row(7, next="audit: check"))
        score = mindseam.narrative_knot_detector(hist)
        # With no real priors, no retread → 100.
        self.assertEqual(score, 100)

    def test_prior_nexts_still_detects_real_retread(self):
        # Seven identical nexts: the recent window retreads the prior.
        hist = [_row(i, next="build: x") for i in range(1, 8)]
        score = mindseam.narrative_knot_detector(hist)
        self.assertLess(score, 100)

    def test_assumption_diversity_book_is_disclosed(self):
        doc = mindseam.assumption_diversity.__doc__ or ""
        self.assertIn("currently ignored", doc)
        self.assertIn("book", doc)

    def test_no_truthiness_next_filter_remains(self):
        offenders = [
            line for line in SOURCE.splitlines()
            if 'if r.get("next")' in line or 'if h.get("next")' in line
            or 'if row.get("next")' in line
        ]
        self.assertEqual(offenders, [], offenders)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("retread-prior-strip-and-book-disclosure", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "retread-prior-strip-and-book-disclosure")
        self.assertEqual(entry["since"], "r238")
        self.assertIn("prior_nexts", entry["summary"])
        self.assertIn("assumption_diversity", entry["summary"])


if __name__ == "__main__":
    unittest.main()
