# -*- coding: utf-8 -*-
"""Round 253: history --format resolves its template in one pass.

The renderer replaced its ``%X`` placeholders with a chain of
``str.replace`` calls, and the chain broke two ways.

1. It substituted ``%n`` before ``%next``. Because ``%next`` *contains*
   ``%n``, the shorter token clobbered the longer one first, so the
   ``%next`` alias the docstring and the ``--format`` help both advertise
   came out as ``<next>ext`` — a documented placeholder that worked
   nowhere.

2. Each pass re-scanned the text the previous pass had written, so a row
   whose ``next`` / ``msg`` free text held a literal placeholder had it
   rewritten. ``next="ship %h now"`` rendered under ``%n`` as
   ``ship 1 now`` (the ``%h`` became the row index); ``msg`` holding
   ``%next`` lost it. The row's own words are model- and
   attacker-authored (the r239-r252 boundary), so this was the one
   projection that trusted its input to be inert, silently rewriting the
   host's chosen template.

r253 replaces the chain with a single ``re.sub`` pass over one
alternation whose alternatives are tried longest-first (so ``%next``
beats ``%n``) and whose callback emits each substituted value whole (so a
value is never re-scanned as a placeholder). Every r197 contract holds:
``%t %n`` renders both fields, ``%%`` is a literal percent, an unknown
``%z`` drops the lone ``%`` and keeps the ``z``, a missing field renders
as ``-``, and the text face and the ``--json`` ``lines`` face stay
byte-identical.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _controller_helper import invoke_cli

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam


def row(nxt="ship", msg="did work", t=1000, verified=1, open_=0):
    return {"t": t, "next": nxt, "msg": msg,
            "verified": verified, "open": open_}


class NextAliasTests(unittest.TestCase):
    """The documented ``%next`` alias renders the next action, not garbage."""

    def setUp(self):
        self.hist = [row(nxt="ship")]

    def one(self, template):
        return mindseam._render_format_lines(self.hist, template)[0]

    def test_next_alias_renders_the_next_action(self):
        self.assertEqual(self.one("%next"), "ship")

    def test_next_alias_no_longer_leaves_a_trailing_ext(self):
        # The exact pre-r253 breakage: %n substituted first turned
        # "%next" into "shipext".
        self.assertNotEqual(self.one("%next"), "shipext")

    def test_next_alias_agrees_with_the_short_form(self):
        self.assertEqual(self.one("%next"), self.one("%n"))

    def test_next_alias_inside_a_wrapper(self):
        self.assertEqual(self.one("[%next]"), "[ship]")

    def test_next_alias_composes_with_other_placeholders(self):
        self.assertEqual(self.one("%t %next"), "1000 ship")

    def test_short_next_still_works_beside_the_alias(self):
        self.assertEqual(self.one("%n/%next"), "ship/ship")


class NoRescanTests(unittest.TestCase):
    """A value that itself contains a ``%X`` is not re-read as a placeholder."""

    def one(self, hist, template):
        return mindseam._render_format_lines(hist, template)[0]

    def test_percent_h_in_next_is_not_rewritten_to_the_row_index(self):
        # Pre-r253 this rendered "ship 1 now": the %h inside the value
        # was caught by the later %h pass.
        h = [row(nxt="ship %h now")]
        self.assertEqual(self.one(h, "[%n]"), "[ship %h now]")

    def test_percent_next_in_msg_survives(self):
        h = [row(msg="has %next inside")]
        self.assertEqual(self.one(h, "[%m]"), "[has %next inside]")

    def test_percent_t_in_next_survives(self):
        h = [row(nxt="run at %t")]
        self.assertEqual(self.one(h, "%n"), "run at %t")

    def test_a_value_holding_double_percent_is_left_alone(self):
        h = [row(nxt="100%% sure")]
        self.assertEqual(self.one(h, "%n"), "100%% sure")

    def test_two_placeholders_each_keep_their_own_value(self):
        h = [row(nxt="ship %h now", msg="has %next inside")]
        self.assertEqual(self.one(h, "%n|%m"),
                         "ship %h now|has %next inside")

    def test_value_placeholder_does_not_bleed_into_a_neighbour(self):
        # The %h literal in next must not consume the real %h that
        # follows it in the template.
        h = [row(nxt="ship %h", t=1000)]
        self.assertEqual(self.one(h, "%n @ %h"), "ship %h @ 1")


class ContractTests(unittest.TestCase):
    """Every r197 rendering contract holds through the single pass."""

    def setUp(self):
        self.hist = [row(nxt="ship", msg="did work", t=1000,
                         verified=2, open_=1)]

    def one(self, template):
        return mindseam._render_format_lines(self.hist, template)[0]

    def test_two_fields_render(self):
        self.assertEqual(self.one("%t %n"), "1000 ship")

    def test_all_fields_render(self):
        self.assertEqual(self.one("%t|%n|%m|%v|%o|%h"),
                         "1000|ship|did work|2|1|1")

    def test_double_percent_is_a_literal_percent(self):
        self.assertEqual(self.one("%%"), "%")

    def test_escaped_percent_before_a_letter_stays_literal(self):
        self.assertEqual(self.one("%%n"), "%n")
        self.assertEqual(self.one("%%t"), "%t")

    def test_escaped_percent_before_next_stays_literal(self):
        self.assertEqual(self.one("%%next"), "%next")

    def test_unknown_placeholder_drops_the_percent_keeps_the_letter(self):
        self.assertEqual(self.one("%z"), "z")

    def test_trailing_bare_percent_is_dropped(self):
        self.assertEqual(self.one("50%"), "50")

    def test_row_index_is_one_based(self):
        hist = [row(t=1000), row(t=1001), row(t=1002)]
        self.assertEqual(mindseam._render_format_lines(hist, "%h"),
                         ["1", "2", "3"])

    def test_missing_field_renders_as_dash(self):
        self.assertEqual(mindseam._render_format_lines([{"t": 1000}], "%n"),
                         ["-"])

    def test_zero_counts_render_as_the_digit_not_dash(self):
        # r-earlier contract: verified/open of 0 is a real count, not a
        # missing field, so it must render "0" not "-".
        h = [row(verified=0, open_=0)]
        self.assertEqual(mindseam._render_format_lines(h, "%v/%o")[0], "0/0")


class _CliBase(unittest.TestCase):
    """Both faces run over the real CLI so parity is end-to-end."""

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.workspace, True)
        self.ledger = Path(self.workspace) / ".mindseam"
        self.ledger.mkdir(parents=True, exist_ok=True)
        body = ["# workspace", "", "## Goal", "keep the ledger lean", "",
                "## Core", "one core line", "", "## Verified",
                "an earlier step", "", "## Open", "", "## Next",
                "the next pass", ""]
        (self.ledger / "WORKSPACE.md").write_text(
            "\n".join(body), encoding="utf-8")

    def write_rows(self, rows):
        (self.ledger / "history.json").write_text(
            json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    def run_cli(self, *args):
        return invoke_cli(self.workspace, list(args))


class HistoryFormatCliTests(_CliBase):

    def test_next_alias_over_the_cli(self):
        self.write_rows([row(nxt="ship it")])
        r = self.run_cli("history", "--format", "%next")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "ship it")

    def test_row_text_with_a_placeholder_is_not_corrupted_over_the_cli(self):
        self.write_rows([row(nxt="deploy %h")])
        r = self.run_cli("history", "--format", "%n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "deploy %h")

    def test_text_and_json_lines_faces_agree_for_the_alias(self):
        self.write_rows([row(nxt="ship it"), row(nxt="deploy %h")])
        text = self.run_cli("history", "--format", "%next")
        payload = json.loads(
            self.run_cli("history", "--format", "%next", "--json").stdout)
        self.assertEqual(text.stdout.strip().splitlines(),
                         payload["lines"])
        self.assertEqual(payload["lines"], ["ship it", "deploy %h"])

    def test_json_lines_face_preserves_a_planted_placeholder(self):
        self.write_rows([row(nxt="ship %next now")])
        payload = json.loads(
            self.run_cli("history", "--format", "%n", "--json").stdout)
        self.assertEqual(payload["lines"], ["ship %next now"])


if __name__ == "__main__":
    unittest.main()
