# -*- coding: utf-8 -*-
"""r358 — two narrowing flags were never disclosed, on any face.

The r349 rule caught this one by comparing two copies of the SAME
closed set. r320's ``--row-id`` refusal list enumerates ELEVEN
narrowing flags: --filter, --since, --until, --grep, --exclude,
--empty, --head, --tail, --limit, --reverse, --keep — every one of
them "changes which rows exist". r324/r354/r357 built the disclosure
keys by a different enumeration — r324's "four filters parsed in one
block" plus r354's selectors — and reached EIGHT keys. The copies
drifted the day they were written:

    history --filter next=build --json   -> rows narrowed, no filter key
    history --empty --json               -> rows narrowed, no empty key

Live before-fix, on a five-row history: ``--filter next=dom1: action
1`` answered one row and ``--empty`` answered zero rows under the
same key set the bare call answers with — a host reading the payload
could not tell a content-filtered window from an empty history, on
every face the helper feeds (the general --json face and, since
r357, the --csv/--dedup/--empty machine faces). The refusal list is
the authoritative enumeration — r320 wrote it to describe exactly
the flags that change which rows exist — so the disclosure keys now
cover it member for member: --filter discloses its KEY=VALUE list
(repeatable, ANDs — the list is the truth) and --empty discloses its
boolean; --tail keeps sharing --limit's key (r354's alias merge).

The completeness itself is pinned in the test as a flag→key map over
all eleven refusal-list members: no orphan keys, no undisclosed
flags, and a live call per flag shows its key answering.
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
         "msg": "m" if i % 2 else "other", "verified": 1, "open": 0}
        for i in range(5)]

# r320's refusal list, verbatim — the authoritative enumeration of
# every flag that narrows (or reorders) the rows a face ships.
NARROWING_FLAGS = ("--filter", "--since", "--until", "--grep",
                   "--exclude", "--empty", "--head", "--tail",
                   "--limit", "--reverse", "--keep")
# The disclosure key each flag answers through. --tail shares
# --limit's key: r354 merged the alias, one dest at runtime.
KEY_FOR_FLAG = {
    "--filter": "filter", "--since": "since", "--until": "until",
    "--grep": "grep", "--exclude": "exclude", "--empty": "empty",
    "--head": "head", "--tail": "limit", "--limit": "limit",
    "--reverse": "reverse", "--keep": "keep",
}


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


class FilterDisclosureTests(SubProjectorBase):
    def test_filter_key_null_when_unset(self):
        self.assertIsNone(self._json()["filter"])

    def test_filter_key_discloses_the_needle(self):
        payload = self._json("--filter", "next=dom1: action 1")
        self.assertEqual(payload["filter"], ["next=dom1: action 1"])
        self.assertEqual(len(payload["rows"]), 1)

    def test_filter_list_is_the_and_truth(self):
        # --filter is repeatable and ANDs; the key discloses the LIST,
        # because a scalar would understate a multi-needle call.
        payload = self._json("--filter", "msg=m", "--filter", "verified=1")
        self.assertEqual(payload["filter"], ["msg=m", "verified=1"])
        self.assertEqual(len(payload["rows"]), 2)

    def test_empty_key_discloses_its_boolean(self):
        payload = self._json("--empty")
        self.assertIs(payload["empty"], True)
        self.assertEqual(payload["rows"], [])
        self.assertIs(self._json()["empty"], False)

    def test_sub_faces_carry_the_keys_too(self):
        # --dedup and --empty are mutually exclusive renderers (r274),
        # so each gets its own call; --empty on the empty face is the
        # renderer itself, verified on the dedup face instead.
        csv = self._json("--csv", "--filter", "msg=other")
        self.assertEqual(csv["filter"], ["msg=other"])
        dedup = self._json("--dedup", "--filter", "msg=m")
        self.assertEqual(dedup["filter"], ["msg=m"])
        empty = self._json("--empty", "--filter", "msg=m")
        self.assertEqual(empty["filter"], ["msg=m"])
        self.assertIs(empty["empty"], True)

    def test_key_set_is_stable(self):
        self.assertEqual(
            sorted(self._json().keys()),
            ["empty", "exclude", "filter", "grep", "head",
             "history_count", "keep", "limit", "reverse", "rows",
             "since", "until", "untrusted"])


class RefusalListCompletenessTests(SubProjectorBase):
    def test_the_helper_covers_the_refusal_list_exactly(self):
        # Two directions of the r349 rule: no orphan keys (a key no
        # refusal-list flag maps to) and no undisclosed flags (a
        # refusal-list member with no key). --tail's alias merge is
        # the one deliberate many-to-one.
        helper_keys = set(KEY_FOR_FLAG.values())
        payload = mindseam._history_narrowing_payload(
            self._ns(), None, None, None, None, None)
        self.assertEqual(set(payload.keys()), helper_keys)

    def test_every_narrowing_flag_answers_its_key(self):
        calls = {
            "--filter": ["--filter", "msg=m"],
            "--since": ["--since", "100000000000"],
            "--until": ["--until", "100000000000"],
            "--grep": ["--grep", "dom"],
            "--exclude": ["--exclude", "nothing-matches-this"],
            "--empty": ["--empty"],
            "--head": ["--head", "1"],
            "--tail": ["--tail", "1"],
            "--limit": ["--limit", "1"],
            "--reverse": ["--reverse"],
            "--keep": ["--keep", "4"],
        }
        self.assertEqual(sorted(calls), sorted(NARROWING_FLAGS))
        for flag, argv in calls.items():
            payload = self._json(*argv)
            self.assertTrue(
                payload[KEY_FOR_FLAG[flag]],
                "%s narrowed the rows but its key answered falsy" % flag)

    def _ns(self):
        import argparse
        ns = argparse.Namespace()
        for key in ("head", "tail", "limit", "keep", "grep", "exclude",
                    "filter"):
            setattr(ns, key, None)
        ns.empty = False
        ns.reverse = False
        return ns


class NeighbouringGuardsTests(SubProjectorBase):
    def test_r320_row_id_refuses_the_new_keys_flags(self):
        for flag in (["--filter", "msg=m"], ["--empty"]):
            r = invoke_cli(self.ws, ["history", "--row-id", "1", *flag])
            self.assertEqual(r.returncode, 2, flag)
            self.assertIn("CANNOT", r.stderr)

    def test_filter_key_validation_untouched(self):
        r = invoke_cli(self.ws, ["history", "--filter", "bogus=1"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)
        r = invoke_cli(self.ws, ["history", "--filter", "nokey"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)

    def test_r278_empty_predicate_still_in_the_filter_chain(self):
        # --empty is a content filter that runs BEFORE head/tail, so a
        # combined call narrows coherently and the empty key still
        # answers True.
        payload = self._json("--empty", "--head", "1")
        self.assertIs(payload["empty"], True)
        self.assertEqual(payload["head"], 1)
        self.assertEqual(payload["rows"], [])

    def test_r310_empty_needle_refusal_untouched(self):
        r = invoke_cli(self.ws, ["history", "--grep", ""])
        self.assertEqual(r.returncode, 2)
        self.assertIn("CANNOT", r.stderr)

    def test_untrusted_map_still_rides(self):
        self.assertIsInstance(self._json("--filter", "msg=m")["untrusted"],
                              dict)


class CatalogPinTests(unittest.TestCase):
    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("narrowing-disclosure-complete", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "narrowing-disclosure-complete")
        self.assertEqual(entry["since"], "r358")
        self.assertIn("filter", entry["summary"])
        self.assertIn("r320", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 208 before r358; later rounds keep appending above it, so this
        # pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 209)

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
