# -*- coding: utf-8 -*-
"""r360 — the intensity ladder's doc copies predated lite.

``INTENSITY_LEVELS = ("off", "lite", "full")`` is the runtime truth:
the argparse help names all three ("lite caps the report at 3
findings, full prints all (default), off refuses to run"), the
invalid-value refusal renders the whole tuple ("valid levels: off,
lite, full"), and every level is accepted live — r349 even cited
--intensity's help as the CONTROL case proving the module does not
loosely describe its sets. But r349 enumerated the tag vocabulary's
surfaces, not the ladder's, and the ladder's three DOC copies were
left at a snapshot from before lite arrived:

    SKILL.md       "cap the printed findings at 3 (full/off; ...)"
    README.md      "Cap the printed findings at 3 (`full` default,
                    `off` refuses; ...)"
    README.zh-CN.md  默认 `full`，`off` 拒绝执行 ...

All three omitted lite — while the SKILL line itself was the command
``audit --intensity lite``, so the line demonstrated a level its own
parenthetical denied existed. A host reading any of the three could
conclude the ladder had two rungs; the CLI would never correct them
(every level works). The --explain face of r202 is static prose, but
the intensity set is NOT: it renders, and this round renders the one
refusal that still hand-typed a slice of it — the off refusal's
"set --intensity lite|full" is now derived from INTENSITY_LEVELS, so
a fourth rung cannot go missing there the way lite went missing in
the docs.

The doc test derives its needles from mindseam.INTENSITY_LEVELS
(the r352 discipline: build the expectation from the live authority)
and asserts the stale two-rung spellings are gone.
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

LEVELS = mindseam.INTENSITY_LEVELS
assert LEVELS == ("off", "lite", "full"), LEVELS


class IntensityBase(unittest.TestCase):
    def _workspace(self):
        ws = tempfile.mkdtemp()
        d = os.path.join(ws, ".mindseam")
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
        return ws


class RuntimeLadderTests(IntensityBase):
    def test_every_level_is_accepted_live(self):
        import json
        for lv in LEVELS:
            r = invoke_cli(self._workspace(),
                           ["audit", "--json", "--intensity", lv])
            if lv == "off":
                self.assertEqual(r.returncode, 2)
                self.assertIn("audit intensity is off", r.stderr)
            else:
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(json.loads(r.stdout)["intensity"], lv)

    def test_unknown_level_refused_with_the_rendered_ladder(self):
        r = invoke_cli(self._workspace(),
                       ["audit", "--json", "--intensity", "bogus"])
        self.assertEqual(r.returncode, 2)
        self.assertIn(", ".join(LEVELS), r.stderr)

    def test_off_refusal_renders_the_runnable_rungs(self):
        # r360: "lite|full" used to be hand-typed; it now renders from
        # INTENSITY_LEVELS minus off, so the message cannot lose a
        # rung.
        r = invoke_cli(self._workspace(), ["audit", "--intensity", "off"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("|".join(lv for lv in LEVELS if lv != "off"),
                      r.stderr)

    def test_env_variable_uppercase_is_normalised(self):
        import json
        ws = self._workspace()
        r = invoke_cli(ws, ["audit", "--json"],
                       env={"MINDSEAM_INTENSITY": "LITE"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["intensity"], "lite")

    def test_env_variable_bogus_refused(self):
        r = invoke_cli(self._workspace(), ["audit", "--json"],
                       env={"MINDSEAM_INTENSITY": "bogus"})
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)


class DocsCopyTests(IntensityBase):
    """Needles derived from INTENSITY_LEVELS, scoped to the intensity
    LINE of each doc (r352's discipline) — full-text assertions would
    collide with this round's own prose about the old state."""

    def _line(self, rel, marker):
        for ln in (ROOT / rel).read_text(encoding="utf-8").splitlines():
            if marker in ln:
                return ln
        raise AssertionError("no line with %r in %s" % (marker, rel))

    def test_skill_line_names_all_three_levels(self):
        line = self._line(os.path.join("mindseam", "SKILL.md"),
                          "MINDSEAM_INTENSITY")
        self.assertIn("/".join(LEVELS), line)
        self.assertNotIn("full/off", line)

    def test_readme_line_names_all_three_levels_backticked(self):
        line = self._line("README.md", "`audit --intensity lite`")
        self.assertIn(" / ".join("`%s`" % lv for lv in LEVELS), line)
        # The stale two-rung spelling is gone from the line itself.
        self.assertNotIn("`full` default, `off` refuses", line)

    def test_chinese_readme_line_names_all_three_levels(self):
        line = self._line("README.zh-CN.md", "`audit --intensity lite`")
        self.assertIn(" / ".join("`%s`" % lv for lv in LEVELS), line)
        self.assertNotIn("默认 `full`，`off` 拒绝执行", line)

    def test_parser_help_still_names_all_three(self):
        # The control case r349 cited, re-pinned. argparse word-wraps
        # help and splits hyphenated tokens mid-word, so compare
        # whitespace-free text (the r352 lesson).
        r = invoke_cli(self._workspace(), ["audit", "--help"])
        self.assertEqual(r.returncode, 0)
        import re
        flat = re.sub(r"\s+", "", r.stdout)
        self.assertIn("litecapsthereportat3findings", flat)
        self.assertIn("offrefusestorun", flat)


class CatalogPinTests(unittest.TestCase):
    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("intensity-ladder-copies-rendered", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "intensity-ladder-copies-rendered")
        self.assertEqual(entry["since"], "r360")
        self.assertIn("INTENSITY_LEVELS", entry["summary"])
        self.assertIn("lite", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 210 before r360; later rounds keep appending above it, so this
        # pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 211)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertEqual(mindseam.INTENSITY_LEVELS, ("off", "lite", "full"))
        self.assertTrue(callable(mindseam.scan_untrusted))

if __name__ == "__main__":
    unittest.main()
