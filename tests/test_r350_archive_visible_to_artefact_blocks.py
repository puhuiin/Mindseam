# -*- coding: utf-8 -*-
"""r350 — the three artefact blocks were blind to the history archive.

``info --mtime``, ``info --content-hash`` and ``info --changed`` all
report on the ledger's files. All three derive from one function,
``_workspace_files_snapshot()``, which listed FOUR artefacts by hand::

    artefacts = ["WORKSPACE.md", "history.json",
                 "metacognition.json", "skillbook.md"]

The directory holds a fifth that the controller itself writes:
``history.archive.json``, which ``compact_history()`` creates every time
history rotates past ``HISTORY_MAX``. It is the only unbounded file in
``.mindseam/`` and the only record of rows that have aged out of
``history.json``, so it is precisely the artefact a host most wants to
see move.

Live before-fix, seeding ``HISTORY_MAX + 1`` rows so the next seam
compacts::

    .mindseam/ on disk : history.archive.json  history.json
                         metacognition.json    skillbook.md
    info --mtime       : WORKSPACE.md  history.json
                         metacognition.json  skillbook.md
    files on disk not named by --mtime : ['history.archive.json']

And the consequence, which is the actual defect: ``--changed`` answers
"which ledger artefacts changed since the last info call", so a
rotation reported ``any_changed`` for the four files it could see and
said NOTHING about the one file the rotation actually created. A host
watching for rotation — a cache to invalidate, a backup to take, an
audit trail to close — saw a change report that was true of everything
except the thing it was watching for. That is the r202/r205/r337
family again, and r349's family too: a closed set restated by hand and
left behind.

Found by asking the SECOND question r348 did not. r348 enumerated the
six payload blocks and asked which ones render a section. The follow-up
nobody asked is the one that found this: for each block that DOES
render, is its CONTENT complete? This repository's own ``.mindseam/``
holds five files, and the blocks named four.

THE FIX introduces ``LEDGER_ARTEFACTS`` as the single source of truth
and has ``_workspace_files_snapshot()`` iterate it, so the next
artefact cannot be omitted the way the archive was.

TWO EXCLUSIONS ARE DELIBERATE and pinned, because a closed set is only
meaningful if what is left out is as decided as what is in:

- ``info-state.json`` is the controller's OWN bookkeeping for
  ``--changed``. Hashing it would make every ``info --changed`` call
  rewrite the state file and therefore report itself as changed — a
  self-referential loop where the answer is always "yes".
- ``aliases.json`` is host-authored configuration, not a ledger
  artefact: the controller reads it and never writes it, so its mtime
  says when a human edited their config, which is a different question
  from "what moved in the ledger".

A note on how the probe was wrong twice before it was right, because
the wrong turns are the useful part. The first attempt used
``history --keep 2`` and no archive appeared. The second seeded 501
rows and called ``info`` — still no archive, because
``compact_history()`` is called from ``append_history()`` (line 1230),
so it is on the WRITE path and nothing on the read path compacts. Only
a ``seam`` produces one. An early version of the coverage probe also
read the block as a list when it is a dict, and reported COUNT 0 for
all four artefacts, which would have made the comparison meaningless.
"""

import ast
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

SRC = ROOT / "mindseam" / "scripts" / "mindseam.py"
ARCHIVE = "history.archive.json"
DELIBERATELY_EXCLUDED = ("info-state.json", "aliases.json")


def _seed_over_limit(ws):
    """Write a history.json one row past HISTORY_MAX and return the path.

    Going through the CLI would need 501 seams; seeding the file and
    letting the next WRITE compact it exercises the same code path a
    long-running workspace reaches, which is the point.
    """
    md = os.path.join(ws, ".mindseam")
    os.makedirs(md, exist_ok=True)
    row = {"t": 1700000000, "next": "do a thing", "verified": [],
           "open": [], "msg": "m", "marker": "", "confidence": "",
           "verifier": "", "risk": "", "error": "", "outcome": "",
           "extra_steps": 0}
    rows = [dict(row, t=1700000000 + i, next="seam %d" % i)
            for i in range(mindseam.HISTORY_MAX + 1)]
    with open(os.path.join(md, "history.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh)
    return md


def _ws_with_archive():
    """A workspace that really has an archive, or skip."""
    ws = tempfile.mkdtemp(prefix="r350arch")
    _seed_over_limit(ws)
    r = invoke_cli(ws, ["seam", "--message", "the seam that compacts"])
    md = os.path.join(ws, ".mindseam")
    if r.returncode != 0 or not os.path.exists(os.path.join(md, ARCHIVE)):
        return None, None
    return ws, md


class ArchiveIsSeenTests(unittest.TestCase):
    """The defect itself: the archive is in all three blocks."""

    def test_mtime_block_names_the_archive(self):
        ws, _ = _ws_with_archive()
        self.assertIsNotNone(ws, "could not produce a real archive")
        p = json.loads(invoke_cli(ws, ["info", "--mtime", "--json"]).stdout)
        self.assertIn(ARCHIVE, p["workspace_files"])

    def test_content_hash_block_names_the_archive(self):
        ws, _ = _ws_with_archive()
        self.assertIsNotNone(ws)
        p = json.loads(invoke_cli(ws, ["info", "--content-hash", "--json"]).stdout)
        self.assertIn(ARCHIVE, p["content_hash"])

    def test_content_hash_of_the_archive_is_a_real_digest(self):
        # Not just a key: a present file must carry a real 8-char prefix,
        # the way a missing one carries "" (r166's contract).
        ws, md = _ws_with_archive()
        self.assertIsNotNone(ws)
        p = json.loads(invoke_cli(ws, ["info", "--content-hash", "--json"]).stdout)
        digest = p["content_hash"][ARCHIVE]
        self.assertTrue(digest, "the archive is present but hashes to empty")
        self.assertEqual(len(digest), 8, digest)

    def test_mtime_entry_carries_size_and_mtime(self):
        ws, md = _ws_with_archive()
        self.assertIsNotNone(ws)
        p = json.loads(invoke_cli(ws, ["info", "--mtime", "--json"]).stdout)
        entry = p["workspace_files"][ARCHIVE]
        self.assertTrue(entry["exists"])
        self.assertGreater(entry["size"], 0)
        self.assertGreater(entry["mtime"], 0)
        self.assertEqual(
            entry["size"],
            os.path.getsize(os.path.join(md, ARCHIVE)))

    def test_every_file_the_controller_writes_is_named(self):
        # The general form of the defect: nothing the controller writes
        # into .mindseam/ may be invisible to --mtime. Before the fix
        # this failed on exactly ['history.archive.json'].
        #
        # info-state.json is not asserted as present here: it is only
        # created once --changed has run, and this test has not called
        # it. The direction that matters is "on disk implies named", and
        # the bookkeeping file is checked for EXCLUSION separately in
        # TheSetIsClosedTests.
        ws, md = _ws_with_archive()
        self.assertIsNotNone(ws)
        p = json.loads(invoke_cli(ws, ["info", "--mtime", "--json"]).stdout)
        on_disk = set(os.listdir(md))
        named = set(p["workspace_files"])
        self.assertEqual(on_disk - named, set(),
                         "files on disk that --mtime cannot see: %s"
                         % sorted(on_disk - named))

    def test_changed_block_reports_the_archive(self):
        # The consequence that matters: a host asking "what changed?"
        # must hear about the rotation.
        ws, _ = _ws_with_archive()
        self.assertIsNotNone(ws)
        invoke_cli(ws, ["info", "--changed", "--json"])       # baseline
        # rotate again so the archive's content genuinely moves
        _seed_over_limit(ws)
        invoke_cli(ws, ["seam", "--message", "second rotation"])
        p = json.loads(invoke_cli(ws, ["info", "--changed", "--json"]).stdout)
        self.assertIn(ARCHIVE, p["changed"]["files"])
        self.assertTrue(p["changed"]["files"][ARCHIVE],
                        "the archive changed on disk but was reported unchanged")

    def test_text_faces_render_the_archive(self):
        # r348 gave every block a text face; the new artefact must
        # appear there too, not only in the JSON.
        ws, _ = _ws_with_archive()
        self.assertIsNotNone(ws)
        for args in (["info", "--mtime"], ["info", "--content-hash"]):
            r = invoke_cli(ws, args)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(ARCHIVE, r.stdout, "%s text face omits it" % args[1])


class TheSetIsClosedTests(unittest.TestCase):
    """The exclusions are as deliberate as the inclusions."""

    def test_info_state_is_excluded(self):
        # Hashing the controller's own --changed bookkeeping would make
        # every call rewrite it and report itself as changed.
        self.assertNotIn("info-state.json", mindseam.LEDGER_ARTEFACTS)
        ws, _ = _ws_with_archive()
        self.assertIsNotNone(ws)
        invoke_cli(ws, ["info", "--changed", "--json"])
        p = json.loads(invoke_cli(ws, ["info", "--changed", "--json"]).stdout)
        self.assertNotIn("info-state.json", p["changed"]["files"])

    def test_aliases_is_excluded(self):
        # Host-authored config, not a ledger artefact: the controller
        # reads it and never writes it.
        self.assertNotIn("aliases.json", mindseam.LEDGER_ARTEFACTS)
        ws, _ = _ws_with_archive()
        self.assertIsNotNone(ws)
        p = json.loads(invoke_cli(ws, ["info", "--mtime", "--json"]).stdout)
        self.assertNotIn("aliases.json", p["workspace_files"])

    def test_the_artefact_set_is_exactly_five_named_things(self):
        # A floor on completeness AND a ceiling on sprawl, both stated
        # as one equality so neither can drift alone.
        self.assertEqual(
            set(mindseam.LEDGER_ARTEFACTS),
            {"WORKSPACE.md", "history.json", ARCHIVE,
             "metacognition.json", "skillbook.md"})

    def test_every_member_is_actually_written_by_the_controller(self):
        # Each name must correspond to a real path constant, so the set
        # cannot accumulate a typo.
        for name, path in (
            ("WORKSPACE.md", mindseam.LEDGER),
            ("history.json", mindseam.HISTORY),
            (ARCHIVE, mindseam.HISTORY_ARCHIVE),
            ("metacognition.json", mindseam.METACOGNITION),
            ("skillbook.md", mindseam.SKILLBOOK),
        ):
            self.assertEqual(os.path.basename(path), name)
            self.assertTrue(path.startswith(".mindseam"), path)

    def test_a_missing_artefact_still_reports_rather_than_disappears(self):
        # The archive is usually absent. Its absence must be REPORTED
        # (exists: false / "" hash), not silently dropped from the
        # block — otherwise a host cannot tell "no archive yet" from
        # "this build does not know about archives".
        ws = tempfile.mkdtemp(prefix="r350noarch")
        p = json.loads(invoke_cli(ws, ["info", "--mtime", "--json"]).stdout)
        self.assertIn(ARCHIVE, p["workspace_files"])
        self.assertFalse(p["workspace_files"][ARCHIVE]["exists"])
        c = json.loads(invoke_cli(ws, ["info", "--content-hash", "--json"]).stdout)
        self.assertEqual(c["content_hash"][ARCHIVE], "")

    def test_missing_artefact_shows_on_the_text_face(self):
        ws = tempfile.mkdtemp(prefix="r350txt")
        r = invoke_cli(ws, ["info", "--mtime"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("(missing)", r.stdout)


class SingleSourceOfTruthTests(unittest.TestCase):
    """The fix removes the CAUSE: there is no second list to drift."""

    def test_the_snapshot_iterates_the_shared_tuple(self):
        src = SRC.read_text(encoding="utf-8")
        i = src.index("def _workspace_files_snapshot")
        body = src[i:src.index("\ndef ", i + 10)]
        self.assertIn("LEDGER_ARTEFACTS", body)
        # and no inline list of the artefacts survives in that function
        self.assertNotIn('"metacognition.json"', body,
                         "the inline artefact list is back")

    def test_there_is_exactly_one_artefact_tuple(self):
        # AST-level: a second literal list of the same names would be
        # the r349 failure mode all over again.
        tree = ast.parse(SRC.read_text(encoding="utf-8"))
        hits = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.List, ast.Tuple)):
                try:
                    vals = [ast.literal_eval(e) for e in node.elts]
                except Exception:
                    continue
                if "history.json" in vals and "metacognition.json" in vals:
                    hits += 1
        self.assertEqual(hits, 1,
                         "found %d places listing the artefacts; there must "
                         "be exactly one (LEDGER_ARTEFACTS)" % hits)

    def test_the_help_text_names_the_archive(self):
        # The --mtime help spelled out four names by hand and would
        # have stayed wrong; r349's lesson applied here too.
        ws = tempfile.mkdtemp(prefix="r350help")
        h = invoke_cli(ws, ["info", "--help"]).stdout
        h = h.replace("-\n", "-")
        self.assertIn(ARCHIVE, h)

    def test_the_module_documents_the_omission(self):
        src = SRC.read_text(encoding="utf-8")
        i = src.index("LEDGER_ARTEFACTS = (")
        lead = src[max(0, i - 2600):i]
        self.assertIn(ARCHIVE, lead,
                      "the archive's addition is not written down where the "
                      "tuple is defined")
        self.assertIn("info-state.json", lead)
        self.assertIn("aliases.json", lead)

    def test_catalog_entry_exists(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("archive-in-artefact-blocks", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "archive-in-artefact-blocks")
        self.assertEqual(entry["since"], "r350")
        self.assertTrue(entry["default"])

    def test_catalog_len_is_a_floor_not_an_exact_count(self):
        # A FLOOR on purpose, the same discipline r349 applied: an
        # exact catalog count is a self-invalidating pin, because the
        # next round's entry breaks it for no reason. There is no
        # exact-max head pin anywhere in the suite to retire this
        # round (searched: assertEqual(max( and == 349 both come up
        # empty), so this round adds none either.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 201)

    def test_the_new_entry_is_reachable_from_the_index(self):
        ws = tempfile.mkdtemp(prefix="r350idx")
        r = invoke_cli(ws, ["info", "--index"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("info.archive-in-artefact-blocks", r.stdout)


class SurroundingContractUnchangedTests(unittest.TestCase):
    """One thing only. The other artefacts and blocks keep their shape."""

    def test_the_four_original_artefacts_are_still_named(self):
        ws = tempfile.mkdtemp(prefix="r350orig")
        p = json.loads(invoke_cli(ws, ["info", "--mtime", "--json"]).stdout)
        for name in ("WORKSPACE.md", "history.json",
                     "metacognition.json", "skillbook.md"):
            self.assertIn(name, p["workspace_files"])

    def test_the_four_original_content_hashes_are_still_present(self):
        ws = tempfile.mkdtemp(prefix="r350orig2")
        p = json.loads(invoke_cli(ws, ["info", "--content-hash", "--json"]).stdout)
        for name in ("WORKSPACE.md", "history.json",
                     "metacognition.json", "skillbook.md"):
            self.assertIn(name, p["content_hash"])

    def test_the_per_artefact_entry_shape_is_unchanged(self):
        ws, _ = _ws_with_archive()
        self.assertIsNotNone(ws)
        p = json.loads(invoke_cli(ws, ["info", "--mtime", "--json"]).stdout)
        for name, entry in p["workspace_files"].items():
            self.assertEqual(sorted(entry),
                             ["exists", "mtime", "path", "size"], name)
            self.assertTrue(os.path.isabs(entry["path"]), name)

    def test_history_itself_still_compacts(self):
        # The fix is a reporting change; it must not alter the rotation
        # that creates the archive in the first place.
        ws, md = _ws_with_archive()
        self.assertIsNotNone(ws)
        with open(os.path.join(md, "history.json"), encoding="utf-8") as fh:
            hist = json.load(fh)
        self.assertEqual(len(hist), mindseam.HISTORY_MAX)
        with open(os.path.join(md, ARCHIVE), encoding="utf-8") as fh:
            arch = json.load(fh)
        self.assertEqual(len(arch) + len(hist), mindseam.HISTORY_MAX + 2)

    def test_mtime_and_content_hash_still_agree_on_the_set(self):
        ws, _ = _ws_with_archive()
        self.assertIsNotNone(ws)
        m = json.loads(invoke_cli(ws, ["info", "--mtime", "--json"]).stdout)
        c = json.loads(invoke_cli(ws, ["info", "--content-hash", "--json"]).stdout)
        self.assertEqual(sorted(m["workspace_files"]), sorted(c["content_hash"]))

    def test_first_run_still_reports_previous_run_false(self):
        ws, _ = _ws_with_archive()
        self.assertIsNotNone(ws)
        p = json.loads(invoke_cli(ws, ["info", "--changed", "--json"]).stdout)
        self.assertFalse(p["changed"]["previous_run"])

    def test_an_empty_workspace_still_answers(self):
        ws = tempfile.mkdtemp(prefix="r350empty")
        r = invoke_cli(ws, ["info", "--mtime", "--json"])
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        self.assertIn(ARCHIVE, p["workspace_files"])


if __name__ == "__main__":
    unittest.main()
