# -*- coding: utf-8 -*-
"""Round 223 guards: run-ignored disclosure is complete.

The r74 guard only scanned for a top-level ``run = hist[...]``
Assign. A second family declares ``run`` and never reads it —
same latent defect (no live caller passes run= today), same
disclosure duty. Ten detectors now say "currently ignored"; the
r74 guard gained a never-loaded scanner.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


class RunIgnoredDisclosureCatalogTests(unittest.TestCase):

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("run-ignored-disclosure-complete", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "run-ignored-disclosure-complete")
        self.assertEqual(entry["since"], "r223")
        self.assertIn("currently ignored", entry["summary"])
        self.assertIn("convergence_index", entry["summary"])

    def test_the_ten_functions_disclose(self):
        for name in (
            "convergence_index", "error_recovery_speed",
            "outcome_completeness", "thread_management",
            "meta_stability", "reset_efficacy",
            "story_switch_detection", "narrative_knot_detector",
            "verification_temporal_bias", "book_thread_alignment",
        ):
            doc = getattr(mindseam, name).__doc__ or ""
            self.assertIn("currently ignored", doc, name)


if __name__ == "__main__":
    unittest.main()
