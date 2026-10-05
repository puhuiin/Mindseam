# -*- coding: utf-8 -*-
"""r359 — a successful --baseline-write used to be invisible.

``--baseline-write`` is destructive: it creates or OVERWRITES the
baseline file that every later ``audit --baseline`` gates against.
Live before-fix, on a ledger with five findings, at exit 0:

    audit --baseline-write b.json
        -> stdout byte-identical to a plain audit; no line names the
           file, the write, or the five findings it committed
    (overwrite)   -> same silence
    audit --json --baseline-write b.json
        -> payload keys unchanged; no baseline_write key

Worse, the write records the UNPROJECTED finding list by design ("a
baseline is a commitment about the ledger state, not about this
run's projection") — so under ``--tag next-stall`` the display showed
"Grade: B (1 fresh item)" while the file silently recorded all five
findings, and nothing on any face named that split. A host reading
the tagged run would believe it had committed one finding to the
baseline; a later full audit would report the other four as
[baselined] — acknowledged debt the host never acknowledged.

The fix closes it the way r354 closed --keep (the clause is the only
stdout trace of the destructive side) and r356 closed the clean
line: the JSON payload gains a ``baseline_write`` key (null when not
writing; {path, recorded, overwritten, previous_count} when it ran),
and both the findings path and the clean path print a confirmation
line — "Baseline written: P (N findings recorded)." /
"Baseline overwritten: P (N findings recorded; was M)." — with the
tagged run appending "The write records the full ledger state; --tag
shaped the display above only."
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

FIVE = ("# Mindseam Workspace Ledger\n\n## Goal\ng\n\n## Core\n"
        "- c1 — work\n- c2 — review\n- c3 — three\n\n"
        "## Verified\n\n## Open\n\n## Next\nbuild: the parser\n")
LEAN = ("# Mindseam Workspace Ledger\n\n## Goal\ng\n\n## Core\n\n"
        "## Verified\n\n## Open\n\n## Next\n\n")


class BaselineBase(unittest.TestCase):
    def _workspace(self, ledger=FIVE, rows_n=12):
        ws = tempfile.mkdtemp()
        d = os.path.join(ws, ".mindseam")
        os.makedirs(d)
        with open(os.path.join(d, "WORKSPACE.md"), "w",
                  encoding="utf-8") as f:
            f.write(ledger)
        rows = [{"t": 1700000000 + i, "next": "build: the parser",
                 "msg": "m", "verified": 1, "open": 0}
                for i in range(rows_n)]
        with open(os.path.join(d, "history.json"), "w",
                  encoding="utf-8") as f:
            json.dump(rows, f)
        return ws

    def _run(self, ws, *flags):
        r = invoke_cli(ws, ["audit", *flags])
        self.assertEqual(r.returncode, 0, r.stderr)
        return r


class TextConfirmationTests(BaselineBase):
    def test_new_write_confirms(self):
        ws = self._workspace()
        r = self._run(ws, "--baseline-write", "b.json")
        self.assertEqual(r.stdout.splitlines()[-1],
                         "Baseline written: b.json (5 findings recorded).")

    def test_overwrite_confirms_with_the_previous_count(self):
        ws = self._workspace()
        self._run(ws, "--baseline-write", "b.json")
        r = self._run(ws, "--baseline-write", "b.json")
        self.assertEqual(
            r.stdout.splitlines()[-1],
            "Baseline overwritten: b.json (5 findings recorded; was 5).")

    def test_tagged_write_names_the_split(self):
        ws = self._workspace()
        r = self._run(ws, "--tag", "next-stall",
                      "--baseline-write", "b.json")
        self.assertEqual(r.stdout.splitlines()[1],
                         "Grade: B (1 fresh item)")
        self.assertEqual(
            r.stdout.splitlines()[-1],
            "Baseline written: b.json (5 findings recorded). "
            "The write records the full ledger state; --tag shaped "
            "the display above only.")
        # The file really does hold the full state, not the projection.
        data = json.load(open(os.path.join(ws, "b.json"),
                              encoding="utf-8"))
        self.assertEqual(len(data), 5)
        self.assertEqual(len({f["tag"] for f in data}), 5)

    def test_clean_write_confirms_too(self):
        ws = self._workspace(ledger=LEAN, rows_n=0)
        r = self._run(ws, "--baseline-write", "b.json")
        self.assertEqual(r.stdout.splitlines(),
                         ["Lean already. Ship.",
                          "Baseline written: b.json (0 findings recorded)."])

    def test_plain_audit_has_no_confirmation_line(self):
        ws = self._workspace()
        r = self._run(ws)
        self.assertNotIn("Baseline written", r.stdout)
        self.assertNotIn("Baseline overwritten", r.stdout)


class JsonFaceTests(BaselineBase):
    def test_key_null_when_not_writing(self):
        payload = json.loads(self._run(self._workspace(),
                                       "--json").stdout)
        self.assertIsNone(payload["baseline_write"])

    def test_key_discloses_the_write(self):
        ws = self._workspace()
        payload = json.loads(self._run(ws, "--json", "--baseline-write",
                                       "b.json").stdout)
        self.assertEqual(payload["baseline_write"],
                         {"path": "b.json", "recorded": 5,
                          "overwritten": False, "previous_count": None})

    def test_overwrite_discloses_the_previous_count(self):
        ws = self._workspace()
        self._run(ws, "--baseline-write", "b.json")
        payload = json.loads(self._run(ws, "--json", "--baseline-write",
                                       "b.json").stdout)
        self.assertTrue(payload["baseline_write"]["overwritten"])
        self.assertEqual(payload["baseline_write"]["previous_count"], 5)

    def test_key_set_grows_by_one_and_is_stable(self):
        payload = json.loads(self._run(self._workspace(),
                                       "--json").stdout)
        self.assertEqual(sorted(payload.keys()),
                         ["baseline_write", "baselined",
                          "baselined_findings",
                          "by_tag", "findings", "gate", "grade",
                          "history_window", "intensity", "lean", "model",
                          "net", "tags"])


class NeighbouringGuardsTests(BaselineBase):
    def test_r201_window_refusal_untouched(self):
        r = invoke_cli(self._workspace(),
                       ["audit", "--baseline-write", "b.json",
                        "--since", "100"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)

    def test_failed_write_still_refuses(self):
        ws = self._workspace()
        blocker = os.path.join(ws, "adir")
        os.makedirs(blocker)
        r = invoke_cli(ws, ["audit", "--baseline-write", blocker])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)

    def test_r162_chained_write_then_baseline_still_gates(self):
        ws = self._workspace()
        r = self._run(ws, "--baseline-write", "b.json", "--baseline",
                      "b.json")
        self.assertIn("Baseline written: b.json (5 findings recorded).",
                      r.stdout)
        self.assertIn("(5 baselined)", r.stdout)
        payload = json.loads(self._run(ws, "--json", "--baseline",
                                       "b.json").stdout)
        self.assertEqual(payload["net"], 0)
        self.assertEqual(payload["gate"], "clean")

    def test_written_file_stays_a_finding_list(self):
        ws = self._workspace()
        self._run(ws, "--baseline-write", "b.json")
        data = json.load(open(os.path.join(ws, "b.json"),
                              encoding="utf-8"))
        self.assertIsInstance(data, list)
        for item in data:
            self.assertIn("tag", item)
            self.assertIn("what", item)

    def test_r356_r156_clean_literals_without_a_write(self):
        ws = self._workspace(ledger=LEAN, rows_n=0)
        r = self._run(ws)
        self.assertEqual(r.stdout, "Lean already. Ship.\n")


class CatalogPinTests(unittest.TestCase):
    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("baseline-write-disclosed", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "baseline-write-disclosed")
        self.assertEqual(entry["since"], "r359")
        self.assertIn("baseline_write", entry["summary"])
        self.assertIn("--tag", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 209 before r359; later rounds keep appending above it, so this
        # pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 210)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertTrue(callable(mindseam._audit_baseline_write))
        self.assertTrue(callable(mindseam._audit_baseline_confirm))
        self.assertTrue(callable(mindseam.scan_untrusted))


if __name__ == "__main__":
    unittest.main()
