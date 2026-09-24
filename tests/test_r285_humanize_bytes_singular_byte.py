# -*- coding: utf-8 -*-
"""Round 285: the byte-count human faces pluralize the byte noun, so a
one-byte workspace or artefact reads "1 byte" instead of "1 bytes".

r281-r283 pluralized the ``history --domains`` / ``--dedup`` / ``--span``
headers and r284 closed a units-ladder dead zone; r285 stays in the
singular/plural family but on the file-size renderers. The byte count is
the one file-size quantity the human faces emit as a bare integer —
KB/MB/GB are ``%.1f`` floats, conventionally plural-neutral the way
``ls -lh`` writes "1.0K", so they never read a wrong singular. Three
human surfaces render the byte count and all three hardcoded
``"%d bytes"``:

  * ``_humanize_bytes``'s sub-1K branch (the ``info --memory`` size word),
  * the ``info --memory`` raw parenthetical ``(%d bytes)``, and
  * the ``info --mtime`` Files per-artefact line ``%d bytes``.

LIVE DEFECT: a ``.mindseam`` holding a single one-byte file made
``info --memory`` print ``size:      1 byte (1 bytes)`` — the humanized
word already fixed by the ladder but the raw parenthetical still plural —
and a one-byte ``skillbook.md`` made ``info --mtime`` print
``skillbook.md            1 bytes``.

The fix routes every raw byte render through one chokepoint,
``_bytes_noun(count)``, which pluralizes via the same
``"" if count == 1 else "s"`` idiom the r281-r283 headers use. "0 bytes"
(documented, empty workspace) and every count >= 2 stay byte-identical;
only exactly 1 becomes "1 byte". The ``--json`` faces expose the raw
integer ``bytes`` / ``size`` with no noun and are untouched.
"""

import json
import os
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

PLACEHOLDER_LEDGER = (
    "# L\n\n## Goal\ng\n\n## Core\n\n## Verified\n\n"
    "## Open\n\n## Next\nn\n"
)


class BytesNounTests(unittest.TestCase):
    """The r285 chokepoint: one raw-byte renderer that pluralizes."""

    def test_zero_is_plural(self):
        self.assertEqual(mindseam._bytes_noun(0), "0 bytes")

    def test_one_is_singular(self):
        self.assertEqual(mindseam._bytes_noun(1), "1 byte")

    def test_two_is_plural(self):
        self.assertEqual(mindseam._bytes_noun(2), "2 bytes")

    def test_large_count_is_raw_and_plural(self):
        # No scaling: the chokepoint renders the count verbatim, only the
        # noun is conditional. Unit scaling lives in _humanize_bytes.
        self.assertEqual(mindseam._bytes_noun(1000000), "1000000 bytes")

    def test_one_is_the_only_singular(self):
        singulars = [n for n in range(0, 2048)
                     if not mindseam._bytes_noun(n).endswith(" bytes")]
        self.assertEqual(singulars, [1])


class HumanizeBytesTests(unittest.TestCase):
    """The unit ladder still scales; only the sub-1K noun changed."""

    def test_zero_bytes(self):
        self.assertEqual(mindseam._humanize_bytes(0), "0 bytes")

    def test_one_byte_singular(self):
        self.assertEqual(mindseam._humanize_bytes(1), "1 byte")

    def test_two_bytes_plural(self):
        self.assertEqual(mindseam._humanize_bytes(2), "2 bytes")

    def test_sub_1k_upper_edge(self):
        self.assertEqual(mindseam._humanize_bytes(1023), "1023 bytes")

    def test_1024_scales_to_kb(self):
        self.assertEqual(mindseam._humanize_bytes(1024), "1.0 KB")

    def test_mb_unit_unchanged(self):
        self.assertEqual(mindseam._humanize_bytes(1024 * 1024), "1.0 MB")

    def test_gb_unit_unchanged(self):
        self.assertEqual(mindseam._humanize_bytes(1024 ** 3), "1.0 GB")

    def test_only_one_byte_differs_from_old_plural(self):
        # Every count except exactly 1 keeps its pre-r285 rendering, so the
        # change is a strict one-value delta on the byte rung.
        for n in [0, 2, 3, 500, 1023]:
            self.assertEqual(mindseam._humanize_bytes(n), "%d bytes" % n)
        self.assertEqual(mindseam._humanize_bytes(1), "1 byte")


class _WorkspaceBase(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r285_")
        self.mind = os.path.join(self.workspace, ".mindseam")
        os.makedirs(self.mind)

    def tearDown(self):
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _write_bytes(self, name, data):
        with open(os.path.join(self.mind, name), "wb") as fh:
            fh.write(data)


class InfoMemorySingularTests(_WorkspaceBase):
    """Live ``info --memory``: a one-byte workspace reads singular in
    both the humanized word and the raw parenthetical."""

    def _memory_text(self, total_bytes):
        # A single file so the os.walk sum equals exactly `total_bytes`.
        if total_bytes:
            self._write_bytes("blob.bin", b"x" * total_bytes)
        res = invoke_cli(self.workspace, ["info", "--memory"])
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def test_one_byte_text_both_nouns_singular(self):
        out = self._memory_text(1)
        self.assertIn("size:      1 byte (1 byte)", out)
        self.assertNotIn("1 bytes", out)

    def test_one_byte_json_human_is_singular(self):
        self._write_bytes("blob.bin", b"x")
        res = invoke_cli(self.workspace, ["info", "--memory", "--json"])
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["bytes"], 1)
        self.assertEqual(payload["human"], "1 byte")

    def test_zero_byte_workspace_stays_plural(self):
        # Empty .mindseam dir, no files — the documented "0 bytes".
        out = self._memory_text(0)
        self.assertIn("size:      0 bytes (0 bytes)", out)

    def test_two_byte_workspace_stays_plural(self):
        out = self._memory_text(2)
        self.assertIn("size:      2 bytes (2 bytes)", out)


class InfoMtimeSingularTests(_WorkspaceBase):
    """Live ``info --mtime`` Files section: a one-byte artefact reads
    "1 byte" while its multi-byte siblings stay plural."""

    def _mtime_text(self, skillbook_bytes):
        ledger = PLACEHOLDER_LEDGER.encode("utf-8")
        self._write_bytes("WORKSPACE.md", ledger)
        self._write_bytes("skillbook.md", b"s" * skillbook_bytes)
        res = invoke_cli(self.workspace, ["info", "--mtime"])
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout, len(ledger)

    def test_one_byte_artefact_is_singular(self):
        out, _ = self._mtime_text(1)
        self.assertIn("1 byte  mtime=", out)
        self.assertNotIn("1 bytes  mtime=", out)

    def test_multi_byte_artefact_stays_plural(self):
        out, ledger_len = self._mtime_text(5)
        self.assertIn("5 bytes  mtime=", out)
        # The multi-byte ledger keeps its plural noun.
        self.assertIn("%d bytes  mtime=" % ledger_len, out)


class CatalogTests(unittest.TestCase):
    """r285 is the highest catalog entry and the window advanced by one."""

    def _since_ints(self):
        return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]

    def test_entry_present(self):
        entry = next((e for e in mindseam._FEATURE_CATALOG
                      if e["id"] == "humanize-bytes-singular-byte"), None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r285")
        self.assertTrue(entry["default"])

    def test_r285_is_the_highest_round(self):
        self.assertEqual(max(self._since_ints()), 285)

    def test_catalog_grew_to_136(self):
        self.assertEqual(len(mindseam._FEATURE_CATALOG), 136)

    def test_recent_window_is_106(self):
        recent = [i for i in self._since_ints() if i >= 170]
        self.assertEqual(len(recent), 106)


if __name__ == "__main__":
    unittest.main()


