# -*- coding: utf-8 -*-
"""Round 294 guards: canonical ASCII round tags only.

_parse_round is the gate on info --index-since / --index-until. Its
CANNOT message pins the contract as "a round tag like r156", and the
catalog since field is written r156 / r175 / r0. The old guard was
``re.match(r"^r(\\d+)$", value.strip())``:

* Python 3's ``\\d`` matches Unicode Nd, so a fullwidth tag
  ``r１７０`` matched and ``int()`` accepted the fullwidth digits.
* ``\\d+`` plus ``int()`` accepted a zero-padded tag ``r0156`` /
  ``r000156`` and collapsed it to 156.

Both spellings are now refused the way ``R170`` already was. r0,
r156 and r170 stay byte-identical.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))
if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam
from _controller_helper import invoke_cli


class RoundTagCanonicalTests(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()

    def test_canonical_tags_accepted(self):
        for tag in ("r0", "r1", "r156", "r170", "r294"):
            r = invoke_cli(self.workspace,
                           ["info", "--index", "--index-since", tag])
            self.assertEqual(r.returncode, 0, (tag, r.stderr))
            self.assertNotIn("CANNOT", r.stderr)

    def test_leading_zeros_refused(self):
        for tag in ("r00", "r000", "r0156", "r000156", "r0170"):
            r = invoke_cli(self.workspace,
                           ["info", "--index", "--index-since", tag])
            self.assertEqual(r.returncode, 2, (tag, r.stdout, r.stderr))
            self.assertIn("round tag", r.stderr)
            self.assertIn("r156", r.stderr)

    def test_fullwidth_digits_refused(self):
        # U+FF11 U+FF17 U+FF10 are Nd, so the old \\d matched them.
        for tag in ("r１７０", "r０", "r１"):
            r = invoke_cli(self.workspace,
                           ["info", "--index", "--index-since", tag])
            self.assertEqual(r.returncode, 2, (tag, r.stdout, r.stderr))
            self.assertIn("round tag", r.stderr)

    def test_uppercase_still_refused(self):
        r = invoke_cli(self.workspace,
                       ["info", "--index", "--index-since", "R170"])
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("round tag", r.stderr)

    def test_until_flag_same_contract(self):
        for tag in ("r00", "r0170", "r１７０", "R170"):
            r = invoke_cli(self.workspace,
                           ["info", "--index", "--index-until", tag])
            self.assertEqual(r.returncode, 2, (tag, r.stdout, r.stderr))
            self.assertIn("round tag", r.stderr)

    def test_r0_keeps_everything(self):
        # The r175 pin: r0 is the valid absurd tag.
        r = invoke_cli(self.workspace,
                       ["info", "--index", "--index-since", "r0"])
        self.assertEqual(r.returncode, 0, r.stderr)
        full = invoke_cli(self.workspace, ["info", "--index"])
        self.assertEqual(
            len([l for l in r.stdout.splitlines() if l]),
            len([l for l in full.stdout.splitlines() if l]))

    def test_canonical_and_padded_disagree_before_fix(self):
        # Document the live-before-fix lie: r0170 used to return the
        # same window as r170. Now it refuses, so the two spellings
        # cannot silently alias.
        canon = invoke_cli(self.workspace,
                           ["info", "--index", "--index-since", "r170"])
        self.assertEqual(canon.returncode, 0, canon.stderr)
        padded = invoke_cli(self.workspace,
                            ["info", "--index", "--index-since", "r0170"])
        self.assertEqual(padded.returncode, 2)
        self.assertNotEqual(canon.returncode, padded.returncode)

    def test_catalog_entry_present(self):
        ids = {e["id"] for e in mindseam._FEATURE_CATALOG}
        self.assertIn("round-tag-canonical", ids)
        entry = next(e for e in mindseam._FEATURE_CATALOG
                     if e["id"] == "round-tag-canonical")
        self.assertEqual(entry["since"], "r294")
        self.assertIn("leading zeros", entry["summary"])
        self.assertIn("fullwidth", entry["summary"])


if __name__ == "__main__":
    unittest.main()
