# -*- coding: utf-8 -*-
"""r349 — the tag list in `audit --tag`'s help was a hand copy, and it
had drifted.

``AUDIT_TAGS`` carries nine tags. The help string for ``--tag`` named
seven of them by hand, and the two it dropped — ``thin-evidence``
(r341) and ``msg-stall`` (r340) — were both accepted at runtime with
exit 0. So the CLI contradicted itself: ``audit --help`` said seven
tags existed, while the refusal message a few lines away printed all
nine::

    $ audit --help | grep -o 'thin-evidence'      # nothing, before the fix
    $ audit --tag zzz
    CANNOT: --tag zzz is not a recognised audit tag.
      known tags: delete, stdlib, thin-evidence, yagni, shrink,
                  goal-stale, next-stall, msg-stall, core-drift

The drift was ORDER-PRESERVING — the help was ``AUDIT_TAGS`` with the
two later tags deleted, which is exactly what appending a tag to the
tuple without revisiting the prose produces. That is the diagnosis
this round records, because it says the seven-of-nine state was never a
stable fact: it was a snapshot that had already expired twice.

Why a stale tag list is a defect and not a cosmetic one: r171 added
``audit --explain <tag>`` so a host meeting a finding can look the tag
up, and an unknown tag is refused with exit 2. The help is therefore
the only surface on which a host can DISCOVER the vocabulary before
guessing at it, and it was the one surface understating it. A host
that read the help could conclude those two tags were not tags, and
nothing in the CLI would ever correct it — the r202/r205/r337
silently-wrong-at-exit-0 family, arriving through documentation rather
than through a dropped flag.

FOUND BY family enumeration, applied to the vocabulary instead of to a
single flag: enumerate ``AUDIT_TAGS``, then ask which surfaces name a
tag, and compare the two sets. The control case is what separates a
defect from a house style — ``--intensity`` names its own runtime set
(``INTENSITY_LEVELS``) in its own help and names all THREE of its
members, so loose description of a set is not a convention here. An AST
sweep of every module-level enumerated family confirmed ``--tag`` is
the only place in the module that copies a runtime set into prose by
hand, which is what makes a one-site fix the whole fix.

THE FIX renders the list from ``AUDIT_TAGS`` rather than writing it
out. Correcting today's omission would have left the cause in place and
the next appended tag would have gone missing the same way; there is now
no copy to keep in step. Everything else about the flag is untouched —
the 'unknown tags are refused' clause, the 'the full audit still runs'
semantics, and the exit-2 contract.

Measured churn: ZERO. No test asserted the seven-tag spelling, because
none of them expected it to be wrong.
"""

import ast
import re
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

# The two tags the hand-written copy had dropped, named here so the
# regression test fails by NAME rather than by a count going wrong.
THE_TWO_OMITTED = ("thin-evidence", "msg-stall")


def _help_text(*args):
    ws = tempfile.mkdtemp(prefix="r349help")
    r = invoke_cli(ws, list(args))
    assert r.returncode == 0, r.stderr
    return r.stdout


def _unwrap(text):
    """argparse hard-wraps help at ~24 columns and breaks INSIDE a
    hyphenated token, so the raw text contains ``goal-\\n stale``.

    Every assertion below runs against the unwrapped string, because
    asserting on the wrapped one would pin argparse's column budget
    instead of the tag list. Note this is also why the original defect
    was not visible by eye in a terminal: the two missing tags were
    missing from a paragraph that was already wrapped.
    """
    out = re.sub(r"-\s*\n\s*", "-", text)   # rejoin a hyphen-broken token
    return re.sub(r"\s+", " ", out)


class TagHelpNamesEveryTagTests(unittest.TestCase):
    """The defect itself: the help must name every tag that exists."""

    def test_help_names_every_audit_tag(self):
        h = _unwrap(_help_text("audit", "--help"))
        for tag in mindseam.AUDIT_TAGS:
            self.assertIn(tag, h,
                          "audit --help does not name the %r tag" % tag)

    def test_help_names_the_two_that_were_dropped(self):
        # The named pair, so a future regression says WHICH tags went
        # missing instead of only that some count is off.
        h = _unwrap(_help_text("audit", "--help"))
        for tag in THE_TWO_OMITTED:
            self.assertIn(tag, h)

    def test_help_no_longer_understates_the_vocabulary(self):
        # The shape of the before-fix defect, stated as an equality:
        # every tag the runtime accepts is a tag the help documents.
        h = _unwrap(_help_text("audit", "--help"))
        undocumented = [t for t in mindseam.AUDIT_TAGS if t not in h]
        self.assertEqual(undocumented, [])

    def test_help_agrees_with_the_refusal_message(self):
        # The self-contradiction is the sharpest statement of the
        # defect, so it is pinned directly: the two lists a caller can
        # reach must be the same list.
        ws = tempfile.mkdtemp(prefix="r349refuse")
        h = _unwrap(invoke_cli(ws, ["audit", "--help"]).stdout)
        bad = invoke_cli(ws, ["audit", "--tag", "definitely-not-a-tag"])
        self.assertEqual(bad.returncode, 2)
        for tag in mindseam.AUDIT_TAGS:
            self.assertIn(tag, h)
            self.assertIn(tag, bad.stderr)

    def test_every_documented_tag_is_really_accepted(self):
        # The other direction. A help that listed a tag the parser
        # refuses would be the same defect wearing the opposite face,
        # and the fix must not have introduced it.
        ws = tempfile.mkdtemp(prefix="r349accept")
        h = _unwrap(invoke_cli(ws, ["audit", "--help"]).stdout)
        for tag in mindseam.AUDIT_TAGS:
            self.assertIn(tag, h)
            r = invoke_cli(ws, ["audit", "--tag", tag])
            self.assertEqual(r.returncode, 0,
                             "help names %r but the parser refused it: %s"
                             % (tag, r.stderr))

    def test_help_lists_the_tags_in_registry_order(self):
        # Order is AUDIT_TAGS' order, not alphabetical and not the order
        # the flags happen to be declared in — the refusal message uses
        # registry order too, and the two are expected to read alike.
        h = _unwrap(_help_text("audit", "--help"))
        m = re.search(r"comma-separated list of audit tags to include \(([^)]*)\)",
                      h)
        self.assertIsNotNone(m, "the --tag help no longer enumerates tags")
        listed = [t for t in m.group(1).split(",") if t]
        self.assertEqual(listed, list(mindseam.AUDIT_TAGS))


class HelpIsRenderedNotWrittenTests(unittest.TestCase):
    """The fix removes the CAUSE, so these pin the shape rather than the
    text. A hand copy that happens to be correct today is exactly the
    state this round was found in."""

    def _tag_help_node(self):
        """AST: the ``--tag`` add_argument call, located by dest."""
        tree = ast.parse(SRC.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (isinstance(fn, ast.Attribute)
                    and fn.attr == "add_argument"):
                continue
            for kw in node.keywords:
                if kw.arg == "dest" and getattr(kw.value, "value", None) == "tag":
                    for kw2 in node.keywords:
                        if kw2.arg == "help":
                            return node, kw2.value
        return None, None

    def test_the_help_is_not_a_bare_literal(self):
        # The drift could only happen because the list was a literal.
        # A literal help string here would be the regression.
        node, help_value = self._tag_help_node()
        self.assertIsNotNone(node, "the --tag argument is gone")
        self.assertNotIsInstance(
            help_value, ast.Constant,
            "audit --tag's help is a bare literal again — the tag list is "
            "hand-written and can drift from AUDIT_TAGS a second time")

    def test_the_help_is_rendered_from_audit_tags(self):
        node, help_value = self._tag_help_node()
        self.assertIsNotNone(node)
        src = ast.dump(help_value)
        self.assertIn("AUDIT_TAGS", src,
                      "the --tag help is no longer derived from AUDIT_TAGS")
        self.assertIn("join", src)

    def test_no_module_level_literal_lists_the_tags(self):
        """No hand-written enumeration of the tag vocabulary survives.

        Scans the ``--tag`` help for a comma-joined run of tag-shaped
        literals. With the fix in place the enumeration is a runtime
        join, so this is the check that would have caught the original
        defect on the day it was written.
        """
        node, help_value = self._tag_help_node()
        self.assertIsNotNone(node)
        for sub in ast.walk(help_value):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                # a literal carrying three or more of the real tags is
                # exactly the shape that drifted
                found = [t for t in mindseam.AUDIT_TAGS if t in sub.value]
                self.assertLess(
                    len(found), 3,
                    "a literal in the --tag help names %d tags (%r) — this "
                    "is the hand copy that drifted"
                    % (len(found), sub.value[:120]))

    def test_the_only_hand_copied_runtime_set_is_gone(self):
        """The AST sweep that justified a one-site fix, kept as a pin.

        Every module-level enumerated family is compared against the
        module's own prose: a family whose members are named nowhere
        else is fine (INVARIANTS is prose by nature), but this test
        pins the specific claim r349 rested on — ``--tag`` was the only
        surface copying a runtime set into a help string by hand.
        """
        src = SRC.read_text(encoding="utf-8")
        tree = ast.parse(src)
        families = []
        for node in tree.body:
            targets = []
            value = None
            if isinstance(node, ast.Assign) and isinstance(
                    node.value, (ast.Tuple, ast.List, ast.Set)):
                targets, value = [node.targets[0]], node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(
                    node.target, ast.Name) and isinstance(
                    node.value, (ast.Tuple, ast.List, ast.Set)):
                targets, value = [node.target], node.value
            if not targets or not isinstance(targets[0], ast.Name):
                continue
            try:
                vals = [ast.literal_eval(e) for e in value.elts]
            except Exception:
                continue
            if len(vals) >= 3 and all(
                    isinstance(v, str) and v for v in vals):
                families.append((targets[0].id, vals))

        self.assertTrue(families)
        # AUDIT_TAGS is in the sweep, with nine members.
        names = {n for n, _ in families}
        self.assertIn("AUDIT_TAGS", names)
        audit_family = dict(families)["AUDIT_TAGS"]
        self.assertEqual(list(audit_family), list(mindseam.AUDIT_TAGS))


class SurroundingContractUnchangedTests(unittest.TestCase):
    """One thing only. The rest of the flag keeps its behaviour."""

    def test_unknown_tag_is_still_refused_with_exit_2(self):
        ws = tempfile.mkdtemp(prefix="r349unknown")
        r = invoke_cli(ws, ["audit", "--tag", "not-a-tag"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a recognised audit tag", r.stderr)

    def test_the_refusal_message_still_names_every_tag(self):
        ws = tempfile.mkdtemp(prefix="r349msg")
        r = invoke_cli(ws, ["audit", "--tag", "not-a-tag"])
        for tag in mindseam.AUDIT_TAGS:
            self.assertIn(tag, r.stderr)

    def test_the_help_still_says_the_full_audit_runs(self):
        h = _unwrap(_help_text("audit", "--help"))
        self.assertIn("The full audit still runs", h)

    def test_the_help_still_says_unknown_tags_are_refused(self):
        h = _unwrap(_help_text("audit", "--help"))
        self.assertIn("unknown tags are refused", h)

    def test_a_single_tag_still_narrows_the_report(self):
        ws = tempfile.mkdtemp(prefix="r349narrow")
        r = invoke_cli(ws, ["audit", "--tag", "yagni"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_comma_separated_tags_still_parse(self):
        ws = tempfile.mkdtemp(prefix="r349csv")
        r = invoke_cli(ws, ["audit", "--tag", "yagni,shrink"])
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_repeating_the_flag_is_refused_not_accumulated(self):
        # r328's contract, pinned here because this round touched the
        # flag's help and the temptation is to "improve" the repeat
        # behaviour while in the neighbourhood. It is NOT a defect:
        # a repeated --tag means the findings you see are not the ones
        # you asked for, so it refuses with exit 2. Do not reverse this
        # — the refusal IS the contract.
        ws = tempfile.mkdtemp(prefix="r349rep")
        r = invoke_cli(ws, ["audit", "--tag", "yagni", "--tag", "shrink"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("--tag", r.stderr)

    def test_explain_still_works_for_every_tag(self):
        # r171's per-tag documentation is the reason a stale tag list
        # matters; the lookup itself must remain complete.
        ws = tempfile.mkdtemp(prefix="r349explain")
        for tag in mindseam.AUDIT_TAGS:
            r = invoke_cli(ws, ["audit", "--explain", tag])
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_explain_and_the_help_cover_the_same_tags(self):
        # The two discovery surfaces agree, so a host that learned the
        # vocabulary from one can use the other.
        ws = tempfile.mkdtemp(prefix="r349both")
        h = invoke_cli(ws, ["audit", "--help"]).stdout
        for tag in mindseam.AUDIT_TAGS:
            self.assertIn(tag, h)
            self.assertEqual(
                invoke_cli(ws, ["audit", "--explain", tag]).returncode, 0)


class CatalogPinTests(unittest.TestCase):
    def test_entry_exists(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("audit-tag-help-rendered", ids)

    def test_entry_since_is_this_round(self):
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "audit-tag-help-rendered")
        self.assertEqual(entry["since"], "r349")
        self.assertTrue(entry["default"])

    def test_entry_names_the_two_dropped_tags(self):
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "audit-tag-help-rendered")
        for tag in THE_TWO_OMITTED:
            self.assertIn(tag, entry["summary"])

    def test_catalog_len_floor(self):
        self.assertGreaterEqual(len(mindseam._FEATURE_CATALOG), 200)

    def test_previous_round_entry_survived(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("manifest-text-face", ids)

    def test_the_entry_is_reachable_from_the_explain_surface(self):
        # A catalog entry nobody can read back is not documentation.
        ws = tempfile.mkdtemp(prefix="r349cat")
        r = invoke_cli(ws, ["info", "--explain", "audit-tag-help-rendered"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("audit-tag-help-rendered", r.stdout)


class IndexCountTests(unittest.TestCase):
    """r175's recent-count pin, advanced by this round's entry."""

    def test_the_new_entry_appears_in_the_full_index(self):
        ws = tempfile.mkdtemp(prefix="r349idx")
        r = invoke_cli(ws, ["info", "--index"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("info.audit-tag-help-rendered", r.stdout)

    def test_the_new_entry_appears_in_the_since_window(self):
        ws = tempfile.mkdtemp(prefix="r349since")
        r = invoke_cli(ws, ["info", "--index", "--index-since", "r349"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("info.audit-tag-help-rendered", r.stdout)

    def test_the_new_entry_is_excluded_before_this_round(self):
        ws = tempfile.mkdtemp(prefix="r349before")
        r = invoke_cli(ws, ["info", "--index", "--index-since", "r170"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("info.audit-tag-help-rendered", r.stdout)


if __name__ == "__main__":
    unittest.main()