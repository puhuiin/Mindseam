# -*- coding: utf-8 -*-
"""r342 — the last modifier that answered nothing when its face was absent.

r337 closed one half of the info surface: the five short-circuit faces
that swallowed every payload block asked for alongside them. Its own
scope note named the exclusion — "``--index``'s own modifiers
(``--index-since``/``--index-until``) are not payload blocks and still
compose" — and that clause is correct. It left the mirror case open.

``--index-since`` and ``--index-until`` narrow the ``--index`` listing
and nothing else. They are the only modifier-shaped flags in the tool
with no independent answer of their own: every other modifier renders
something on its own (``--format`` and ``--field`` print a value,
``--tag`` projects the audit, ``--explain`` prints the static doc,
``--fields`` prints a column). Without ``--index``, these two were
silently dropped at exit 0 with output byte-identical to plain ``info``.
Live before this round:

    info --index-since r170      -> rc 0, the full report, no difference
    info --index-until r200      -> rc 0, the full report, no difference

and the INVALID-value case was the sharp one, because the round-tag
parse (r294) lives inside the ``--index`` branch:

    info --index --index-since bad   -> rc 2, "expects a round tag like r156"
    info --index-since bad           -> rc 0, the full report

A host that typo'd a tag got a full report and no signal that its window
never ran — the r188/r205/r337 silent-wrong-at-exit-0 family, on the one
modifier pair r337 had explicitly left out of its guard.

THE FIX is a guard in the info dispatcher, before the index branch runs:
when ``--index`` is absent and either window flag is present, refuse with
exit 2 naming the flags, the way r337's payload-block guard does. The
round-tag validation then only ever runs on the ``--index`` path, where
the value is genuinely used, and the two refusals compose (no face plus
an invalid value reports the face clash first, which is the more useful
of the two).

Measured churn: zero. No test used a window flag without ``--index``,
because the flags' only documented job is narrowing the index.
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


def _workspace():
    ws = tempfile.mkdtemp()
    d = os.path.join(ws, ".mindseam")
    os.makedirs(d)
    with open(os.path.join(d, "WORKSPACE.md"), "w", encoding="utf-8") as f:
        f.write("# Mindseam Workspace Ledger\n\n## Goal\ng\n\n## Core\n"
                "- c1 — work\n\n## Verified\n\n## Open\n\n## Next\nn\n")
    with open(os.path.join(d, "history.json"), "w", encoding="utf-8") as f:
        json.dump([{"t": 1700000000 + i, "next": "dom: a%d" % i,
                    "msg": "m%d" % i, "verified": i, "open": 0}
                   for i in range(8)], f)
    return ws


class WindowWithoutIndexRefusedTests(unittest.TestCase):
    """The guard itself: a window flag without its face refuses."""

    def test_index_since_alone_is_refused(self):
        r = invoke_cli(_workspace(),
                       ["info", "--index-since", "r170"])
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_index_until_alone_is_refused(self):
        r = invoke_cli(_workspace(),
                       ["info", "--index-until", "r200"])
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_both_alone_are_refused(self):
        r = invoke_cli(_workspace(), ["info", "--index-since", "r170",
                                      "--index-until", "r200"])
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_the_refusal_names_the_flags(self):
        r = invoke_cli(_workspace(),
                       ["info", "--index-since", "r170"])
        self.assertIn("--index-since", r.stderr)
        self.assertIn("--index", r.stderr)
        self.assertIn("CANNOT", r.stderr)

    def test_both_named_when_both_given(self):
        r = invoke_cli(_workspace(), ["info", "--index-since", "r170",
                                      "--index-until", "r200"])
        self.assertIn("--index-since", r.stderr)
        self.assertIn("--index-until", r.stderr)

    def test_the_output_is_not_the_plain_report(self):
        # Before the round these two were byte-identical, which is the
        # whole defect: the flag did nothing and said nothing.
        plain = invoke_cli(_workspace(), ["info"]).stdout
        r = invoke_cli(_workspace(),
                       ["info", "--index-since", "r170"])
        self.assertNotEqual(r.stdout, plain)
        self.assertEqual(r.stdout, "")

    def test_the_invalid_value_case_is_refused(self):
        # The sharp one: the round-tag parse lives inside the --index
        # branch, so a typo'd tag was swallowed with the flag.
        for bad in ("bad", "172", "R170", "r0156", "", "-1", "r"):
            r = invoke_cli(_workspace(),
                           ["info", "--index-since", bad])
            self.assertEqual(r.returncode, 2,
                             "--index-since %r was swallowed" % bad)

    def test_no_index_plus_a_face_still_refuses(self):
        # A face that cannot honour the window refuses it too, rather
        # than dropping it.
        # --index is NOT in the list: it is the face the window belongs
        # to, so the pair is the documented composition and answers 0.
        for face in ("--check", "--version", "--manifest", "--health",
                     "--features", "--mtime", "--aliases", "--human",
                     "--memory", "--list-fields", "--workspace-id",
                     "--text", "--warnings-only", "--explain"):
            r = invoke_cli(_workspace(),
                           ["info", face, "--index-since", "r170"])
            self.assertEqual(r.returncode, 2, face)
        r = invoke_cli(_workspace(),
                       ["info", "--warnings-only", "--index-until", "r200"])
        self.assertEqual(r.returncode, 2)


class IndexPathUnchangedTests(unittest.TestCase):
    """Every index contract r174-r176 and r294 pinned still holds."""

    def test_index_with_window_still_works(self):
        r = invoke_cli(_workspace(), ["info", "--index",
                                      "--index-since", "r170"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip())

    def test_order_does_not_matter(self):
        a = invoke_cli(_workspace(), ["info", "--index",
                                      "--index-since", "r170"])
        b = invoke_cli(_workspace(), ["info", "--index-since", "r170",
                                      "--index"])
        self.assertEqual(a.returncode, 0, b.stderr)
        self.assertEqual(a.stdout, b.stdout)

    def test_both_windows_with_index_still_work(self):
        r = invoke_cli(_workspace(), ["info", "--index", "--index-since",
                                      "r170", "--index-until", "r200"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_index_alone_still_works(self):
        r = invoke_cli(_workspace(), ["info", "--index"])
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = [l for l in r.stdout.splitlines() if l]
        self.assertGreaterEqual(len(lines), len(mindseam._FEATURE_CATALOG))

    def test_invalid_round_tag_with_index_still_refused(self):
        # r294's contract, unchanged: the guard only changes WHEN it runs,
        # not what it refuses.
        for bad in ("bad", "172", "R170", "r0156", "", "-1", "r",
                    "r１７０", "r00"):
            r = invoke_cli(_workspace(), ["info", "--index",
                                          "--index-since", bad])
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn("round tag", r.stderr)

    def test_inverted_bracket_with_index_still_refused(self):
        # r295: an inverted pair refuses, whichever face it is asked on.
        r = invoke_cli(_workspace(), ["info", "--index", "--index-since",
                                      "r200", "--index-until", "r170"])
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--index-since", r.stderr)

    def test_json_face_still_carries_the_window(self):
        r = invoke_cli(_workspace(), ["info", "--index", "--json",
                                      "--index-since", "r100"])
        self.assertEqual(r.returncode, 0, r.stderr)
        entries = json.loads(r.stdout)["index"]
        self.assertTrue(entries)
        self.assertTrue(all(e.startswith("info.") or "." in e
                            for e in entries))

    def test_repeated_window_flag_still_refused(self):
        # r328's single-use guard fires before this one names the clash,
        # and both must keep refusing.
        r = invoke_cli(_workspace(), ["info", "--index", "--index-since",
                                      "r200", "--index-since", "r100"])
        self.assertEqual(r.returncode, 2, r.stdout)


class EveryOtherModifierStillAnswersTests(unittest.TestCase):
    """The invariant the guard depends on: these two flags are the only
    modifiers with no independent answer. Pin the rest."""

    MODIFIERS = (
        (["info", "--format", "goal"], 0),
        (["info", "--field", "goal"], 0),
        (["audit", "--tag", "delete"], 0),
        (["audit", "--format", "net"], 0),
        (["audit", "--explain", "delete"], 0),
        (["history", "--fields", "next"], 0),
        (["history", "--format", "%n"], 0),
        (["seam", "--dry-run", "--format", "goal"], 0),
        (["resume", "--format", "goal"], 0),
        (["skillbook", "--format", "entries"], 0),
        (["discover", "--format", "domains"], 0),
    )

    def test_every_other_modifier_answers_without_a_face(self):
        for args, want in self.MODIFIERS:
            r = invoke_cli(_workspace(), args)
            self.assertEqual(r.returncode, want,
                             "%s -> %s" % (args, r.stderr[:60]))

    def test_info_alone_still_answers(self):
        r = invoke_cli(_workspace(), ["info"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip())

    def test_every_info_face_alone_still_answers(self):
        # --check is excluded: it is r333's fsck-style gate and answers
        # non-zero when the ledger has issues, which this bare fixture does
        # by design. Its contract is pinned by r333's own file.
        for face in ("--version", "--manifest", "--health",
                     "--features", "--mtime", "--aliases", "--index",
                     "--warnings-only", "--human", "--memory",
                     "--list-fields", "--workspace-id", "--text"):
            r = invoke_cli(_workspace(), ["info", face])
            self.assertEqual(r.returncode, 0,
                             "%s -> %s" % (face, r.stderr[:60]))

    def test_check_alone_still_runs_its_gate(self):
        # r333: --check answers non-zero on a ledger with issues and zero
        # on a clean one. Neither is a crash.
        r = invoke_cli(_workspace(), ["info", "--check"])
        self.assertIn(r.returncode, (0, 2))
        self.assertNotIn("Traceback", r.stdout + r.stderr)


class InteractionTests(unittest.TestCase):
    """The new guard composes with the ones around it."""

    def test_r337_block_guard_still_fires(self):
        # A face + a block is still r337's refusal, not this one.
        r = invoke_cli(_workspace(), ["info", "--version", "--health"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--health", r.stderr)

    def test_r337_guard_wins_over_the_window_guard(self):
        # Two flags refused for two different reasons: the face/block pair
        # is checked first and names the more specific problem.
        r = invoke_cli(_workspace(), ["info", "--version", "--health",
                                      "--index-since", "r170"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--health", r.stderr)

    def test_window_guard_fires_with_a_block_alone(self):
        # A block is not a face, so r337 does not apply and this guard does.
        r = invoke_cli(_workspace(), ["info", "--health",
                                      "--index-since", "r170"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--index-since", r.stderr)

    def test_a_block_alone_still_answers(self):
        # r337 pinned these; the new guard must not touch them.
        for block in ("--health", "--manifest", "--mtime", "--features",
                      "--aliases", "--human", "--workspace-id",
                      "--content-hash", "--changed", "--text"):
            r = invoke_cli(_workspace(), ["info", block])
            self.assertEqual(r.returncode, 0, block)

    def test_renderers_alone_still_answer(self):
        r = invoke_cli(_workspace(), ["info", "--format", "goal"])
        self.assertEqual(r.returncode, 0, r.stderr)
        r = invoke_cli(_workspace(), ["info", "--field", "goal"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_renderers_are_not_faces(self):
        # r337's guard is scoped to the five faces that predate r202/r205;
        # a renderer with a face is still r337's own refusal.
        r = invoke_cli(_workspace(), ["info", "--version", "--format", "goal"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--format", r.stderr)


class RegistryTests(unittest.TestCase):
    """The flags are registered, and the guard sees them."""

    def test_both_flags_are_registered_on_info(self):
        r = invoke_cli(_workspace(), ["info", "--help"])
        self.assertIn("--index-since", r.stdout)
        self.assertIn("--index-until", r.stdout)

    def test_help_documents_them_as_index_modifiers(self):
        # The help text says the flags narrow the index, which is the
        # fact the guard enforces.
        r = invoke_cli(_workspace(), ["info", "--help"])
        for line in r.stdout.splitlines():
            if "--index-since" in line:
                self.assertIn("--index", line)
                break
        else:
            self.fail("--index-since not in info --help")

    def test_the_docstrings_name_the_round(self):
        src = (ROOT / "mindseam" / "scripts" / "mindseam.py").read_text(
            encoding="utf-8")
        i = src.find('if args.cmd == "info" and not getattr(args, "index"')
        self.assertGreater(i, 0)
        head = src[i:i + 1400]
        self.assertIn("r342", head)
        self.assertIn("--index-since", head)


class CatalogPinTests(unittest.TestCase):
    """The catalog registers the round and keeps its shape."""

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("index-window-requires-index", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "index-window-requires-index")
        self.assertEqual(entry["since"], "r342")
        self.assertIn("--index-since", entry["summary"])
        self.assertIn("--index-until", entry["summary"])

    def test_catalog_grew_by_one(self):
        # 192 before r342; r343 (and later rounds) keep appending above
        # it, so this pin is a floor: the count can only grow.
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 193)

    def test_catalog_shape_unchanged(self):
        for entry in mindseam._FEATURE_CATALOG:
            self.assertEqual(sorted(entry.keys()),
                             ["default", "id", "since", "summary"])
            self.assertTrue(entry["summary"])
            self.assertRegex(entry["since"], r"^r\d+$")

    def test_module_still_loads(self):
        self.assertTrue(callable(mindseam.main))
        self.assertTrue(callable(mindseam.mode_info))


if __name__ == "__main__":
    unittest.main()
