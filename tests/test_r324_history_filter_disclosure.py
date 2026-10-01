# -*- coding: utf-8 -*-
"""r324 — the history faces disclose every filter that narrowed the rows.

``mode_history`` narrows its row set with four filters parsed in one
block: ``--since`` / ``--until`` (a time window) and ``--grep`` /
``--exclude`` (text). The two faces that report what happened disclosed
only HALF of them:

* ``history --json`` carried ``"since"`` and ``"grep"`` but had no key
  for ``until`` or ``exclude``.
* the text header printed ", last N s" for ``--since`` and
  ", grep '…'" for ``--grep`` but nothing for ``--until`` or
  ``--exclude``.

There is no principled reason for the split — all four are row-narrowing
filters, ``--grep`` and ``--exclude`` are validated as a pair (r310
refuses both when empty), and ``--since``/``--until`` bracket one window
(r220). The consequence is that a host reading
``history --json --exclude deploy`` receives the surviving rows with no
key at all, which is indistinguishable from a history that simply holds
that many rows: the narrowing is invisible on the machine face.

This is the r245/r270 doctrine — a host must be able to tell what
narrowed the rows it is about to act on — and the r254/r259
enumerate-every-projector discipline: four filters, two faces, and the
disclosure was enumerated per filter rather than per family.

Probe (before the fix), on a three-row history::

    history --exclude deploy      -> header "history (2 entries)"
                                   JSON keys: no "exclude"
    history --until 7200          -> header "history (3 entries)"
                                   JSON keys: no "until"
    history --grep build          -> header "history (1 entry, grep 'build')"
                                   JSON "grep": "build"

The fix discloses the missing two on both faces, mirroring the shape the
existing clauses already use: ``"until"``/``"exclude"`` in the payload
and ", older than N s" / ", exclude '…'" in the header. Every existing
clause is byte-identical, so a call with neither flag still renders
exactly as before.

Scope: only the general ``history`` face's payload and header changed.
``--since``/``--until``/``--grep``/``--exclude`` keep their r220/r310
semantics, the r222 inverted-window refusal, and the r275/r278
filter-then-truncate order. A repeated ``--grep``/``--exclude`` took the
last value (argparse ``store``); that silent drop was this round's
pre-identified carrier and r325 fixed it, so the test that documented the
old behaviour now pins the refusal instead.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _controller_helper import invoke_cli, run_controller  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "mindseam", "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import mindseam  # noqa: E402

ROWS = [
    {"t": 1000, "next": "build: alpha", "msg": "m", "verified": 1,
     "open": 0, "risk": "high", "marker": "M1", "confidence": "strong",
     "outcome": "ok", "error": "", "verifier": "alice"},
    {"t": 2000, "next": "deploy: beta", "msg": "m", "verified": 0,
     "open": 2, "risk": "", "marker": "", "confidence": "shaky",
     "outcome": "", "error": "boom", "verifier": "bob"},
    {"t": 3000, "next": "test: gamma", "msg": "m", "verified": 3,
     "open": 1, "risk": "high", "marker": "M2", "confidence": "thin",
     "outcome": "ok", "error": "", "verifier": "alice"},
]


class _Base(unittest.TestCase):
    def setUp(self):
        self._workspaces = []
        self.ws = self._fresh()
        invoke_cli(self.ws, ["note", "--goal", "ship it",
                             "--next", "verify it"])
        self._write_rows(ROWS)

    def tearDown(self):
        for ws in self._workspaces:
            shutil.rmtree(ws, ignore_errors=True)

    def _fresh(self):
        ws = tempfile.mkdtemp(prefix="r324_")
        self._workspaces.append(ws)
        return ws

    def _write_rows(self, rows):
        path = os.path.join(self.ws, ".mindseam", "history.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)

    def _json(self, *extra):
        r = run_controller(self.ws, "history", "--json", *extra)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def _header(self, *extra):
        r = run_controller(self.ws, "history", *extra)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        self.assertTrue(lines, r.stdout)
        return lines[0]


class JsonDisclosureTests(_Base):
    """The machine face carries a key for every row filter."""

    def test_no_filters_leaves_the_new_keys_null(self):
        payload = self._json()
        self.assertEqual(len(payload["rows"]), 3)
        self.assertIsNone(payload["until"])
        self.assertIsNone(payload["exclude"])
        self.assertIsNone(payload["since"])
        self.assertIsNone(payload["grep"])

    def test_until_key_carries_its_seconds(self):
        payload = self._json("--until", "7200")
        self.assertEqual(payload["until"], 7200)
        self.assertIsNone(payload["since"])

    def test_exclude_key_carries_its_text(self):
        payload = self._json("--exclude", "deploy")
        self.assertEqual(payload["exclude"], "deploy")
        self.assertEqual(len(payload["rows"]), 2)
        self.assertIsNone(payload["grep"])

    def test_all_four_keys_present_in_one_payload(self):
        payload = self._json("--since", "100000", "--until", "1",
                             "--grep", "build", "--exclude", "deploy")
        self.assertEqual(payload["since"], 100000)
        self.assertEqual(payload["until"], 1)
        self.assertEqual(payload["grep"], "build")
        self.assertEqual(payload["exclude"], "deploy")

    def test_every_row_filter_has_a_key(self):
        # The discipline: enumerate the filter family, not the two that
        # happened to be implemented first.
        payload = self._json()
        for key in ("history_count", "limit", "since", "until", "grep",
                    "exclude", "reverse", "rows", "untrusted"):
            self.assertIn(key, payload)


class HeaderDisclosureTests(_Base):
    """The human face names every row filter too."""

    def test_header_names_exclude(self):
        header = self._header("--exclude", "deploy")
        self.assertIn("(2 entries, exclude 'deploy')", header)

    def test_header_names_until(self):
        header = self._header("--until", "7200")
        self.assertIn("(3 entries, older than 7200 s)", header)

    def test_header_still_names_grep_and_since(self):
        header = self._header("--grep", "build")
        self.assertIn("grep 'build'", header)
        header = self._header("--since", "3600")
        self.assertIn("last 3600 s", header)

    def test_header_names_all_four_together(self):
        header = self._header("--since", "100000", "--until", "1",
                              "--grep", "build", "--exclude", "deploy")
        for clause in ("last 100000 s", "older than 1 s",
                       "grep 'build'", "exclude 'deploy'"):
            self.assertIn(clause, header)

    def test_no_filters_header_is_unchanged(self):
        # A call with neither flag renders exactly as before.
        self.assertEqual(self._header(),
                         "── mindseam ─ history (3 entries)")

    def test_faces_disclose_the_same_values(self):
        # The two faces project the same four numbers/strings.
        for extra in (("--until", "7200"), ("--exclude", "deploy"),
                      ("--grep", "build"), ("--since", "3600")):
            payload = self._json(*extra)
            header = self._header(*extra)
            flag = extra[0].lstrip("-")
            self.assertIn(str(payload[flag]), header,
                          "%s applied=%r not named in %r"
                          % (extra[0], payload[flag], header))


class SemanticsPreservedTests(_Base):
    """The fix is disclosure only; the filtering behaviour is unchanged."""

    def test_exclude_still_narrows(self):
        payload = self._json("--exclude", "deploy")
        self.assertEqual([r["next"] for r in payload["rows"]],
                         ["build: alpha", "test: gamma"])

    def test_until_still_drops_the_fresh_rows(self):
        # Rows are stamped 1000..3000 (1970), so a 7200s until-bound
        # keeps every row (they are all far older than 7200s).
        payload = self._json("--until", "7200")
        self.assertEqual(len(payload["rows"]), 3)

    def test_inverted_window_still_refuses(self):
        r = run_controller(self.ws, "history", "--since", "3600",
                           "--until", "7200")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--since 3600 is after --until 7200", r.stderr)

    def test_empty_needles_still_refuse(self):
        for flag in ("--grep", "--exclude"):
            r = run_controller(self.ws, "history", flag, "")
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_filter_then_truncate_order_unchanged(self):
        # r275: the selector picks from the filter survivors, not the
        # raw window. "e" matches rows 2 and 3 only, so --head 1 under
        # filter-then-truncate returns the FIRST MATCHING row; under the
        # old truncate-then-filter order it would return the first raw
        # row and then drop it for not matching, i.e. 0 rows.
        payload = self._json("--grep", "e", "--head", "1")
        self.assertEqual([r["next"] for r in payload["rows"]],
                         ["deploy: beta"])
        self.assertEqual(payload["grep"], "e")

    def test_tail_picks_from_the_survivors(self):
        payload = self._json("--grep", "e", "--tail", "2")
        self.assertEqual([r["next"] for r in payload["rows"]],
                         ["deploy: beta", "test: gamma"])

    def test_repeated_flag_is_now_refused(self):
        # r324 scoped this out: a repeated --grep/--exclude took the last
        # value (argparse store), so the earlier needle was silently
        # dropped. r325 fixed it — the repetition is now refused with
        # exit 2, and the disclosure this round added makes the applied
        # value visible before the refusal ever needed to.
        r = run_controller(self.ws, "history", "--exclude", "deploy",
                           "--exclude", "build")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("CANNOT: --exclude was given 2 times", r.stderr)
        self.assertEqual(r.stdout, "")
        payload = self._json("--exclude", "deploy")
        self.assertEqual(payload["exclude"], "deploy")
        self.assertIn("exclude 'deploy'", self._header("--exclude", "deploy"))


class CatalogPinTests(unittest.TestCase):

    def _since_ints(self):
        out = []
        for e in mindseam._FEATURE_CATALOG:
            since = e.get("since")
            if isinstance(since, str) and since.startswith("r"):
                try:
                    out.append(int(since.lstrip("r")))
                except ValueError:
                    pass
        return out

    def test_entry_present_since_r324_default_true(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "history-filter-disclosure"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r324")
        self.assertTrue(entry["default"])

    def test_r324_is_now_the_highest_round(self):
        self.assertGreaterEqual(max(self._since_ints()), 324)


if __name__ == "__main__":
    unittest.main()
