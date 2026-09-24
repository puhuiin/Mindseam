"""r286 — _humanize_bytes promotes a size that rounds up to 1024.0.

``_humanize_bytes`` scales a file size through a byte/KB/MB/GB ladder and
picks the rung by comparing the raw float to 1024. But the KB/MB/GB rungs
print ``%.1f`` (one decimal), and a size in the top sliver of a unit —
``size_kb`` in ``[1023.95, 1024)`` — rounds up to the *string* ``"1024.0"``.
So ``info --memory`` printed "1024.0 KB" for a size that ``ls -lh`` would
promote to "1.0 MB", and "1024.0 MB" for one that should read "1.0 GB".

Live before-fix (real subprocess, a ~1 MB single-file ``.mindseam``):
``info --memory`` printed ``size:      1024.0 KB`` and its ``--json`` face
carried ``"human": "1024.0 KB"``.

The fix chooses each rung by the value the reader actually sees:
``float("%.1f" % value) < 1024.0``. So the displayed number is always under
1024 of its unit, only the [1023.95, 1024) dead zone of each rung changes,
and every other size (including the r285 sub-1024 byte rung) is byte-identical.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))

import mindseam  # noqa: E402

from _controller_helper import invoke_cli  # noqa: E402


def _since_ints():
    return [int(e["since"].lstrip("r")) for e in mindseam._FEATURE_CATALOG]


# Sizes whose per-rung float lands inside the [1023.95, 1024) rounding
# dead zone, so the raw-float guard used to print "1024.0 <unit>".
KB_DEAD_ZONE = (1048525, 1048540, 1048560, 1048575)      # -> should be "1.0 MB"
MB_DEAD_ZONE = (1073741300, 1073741600, 1073741823)      # -> should be "1.0 GB"


class UnitPromotionTests(unittest.TestCase):
    def test_kb_dead_zone_promotes_to_one_mb(self):
        for n in KB_DEAD_ZONE:
            self.assertEqual(
                mindseam._humanize_bytes(n),
                "1.0 MB",
                "size %d should promote to 1.0 MB, not 1024.0 KB" % n,
            )

    def test_mb_dead_zone_promotes_to_one_gb(self):
        for n in MB_DEAD_ZONE:
            self.assertEqual(
                mindseam._humanize_bytes(n),
                "1.0 GB",
                "size %d should promote to 1.0 GB, not 1024.0 MB" % n,
            )

    def test_no_size_ever_renders_1024_point_0(self):
        # Sweep both boundaries; the buggy render was exactly "1024.0 KB"
        # / "1024.0 MB". None should survive.
        for n in range(1048400, 1048700):
            self.assertNotIn("1024.0", mindseam._humanize_bytes(n))
        for n in range(1073741000, 1073742000):
            self.assertNotIn("1024.0", mindseam._humanize_bytes(n))

    def test_normal_scaled_values_unchanged(self):
        # Values comfortably inside a rung are byte-identical to before.
        self.assertEqual(mindseam._humanize_bytes(1024), "1.0 KB")
        self.assertEqual(mindseam._humanize_bytes(1536), "1.5 KB")
        self.assertEqual(mindseam._humanize_bytes(1024 * 1024), "1.0 MB")
        self.assertEqual(mindseam._humanize_bytes(1024 ** 3), "1.0 GB")
        self.assertEqual(mindseam._humanize_bytes(1610612736), "1.5 GB")
        # 1023.0 MB rounds to itself, stays in the MB rung.
        self.assertEqual(mindseam._humanize_bytes(1072693248), "1023.0 MB")
        # 1023.4 KB is below the dead zone, stays in KB.
        self.assertEqual(mindseam._humanize_bytes(1048000), "1023.4 KB")

    def test_sub_1024_byte_rung_unchanged(self):
        # The r285 singular/plural invariant still holds — this round only
        # touched the KB/MB/GB float guards, not the raw-byte branch.
        self.assertEqual(mindseam._humanize_bytes(0), "0 bytes")
        self.assertEqual(mindseam._humanize_bytes(1), "1 byte")
        self.assertEqual(mindseam._humanize_bytes(2), "2 bytes")
        self.assertEqual(mindseam._humanize_bytes(1023), "1023 bytes")


class DisplayedValueStaysUnderUnitTests(unittest.TestCase):
    def test_numeric_prefix_of_scaled_render_is_below_1024(self):
        # The invariant the fix guarantees: whenever the render carries a
        # unit suffix, the number the reader sees is < 1024.0 of that unit.
        samples = list(range(1048400, 1048700))
        samples += list(range(1073741000, 1073742000))
        samples += [1024, 1536, 1024 * 1024, 1024 ** 3, 1610612736]
        for n in samples:
            out = mindseam._humanize_bytes(n)
            for unit in (" KB", " MB", " GB"):
                if out.endswith(unit):
                    value = float(out[: -len(unit)])
                    self.assertLess(
                        value, 1024.0,
                        "render %r for %d shows >= 1024 of its unit" % (out, n),
                    )


class _WorkspaceBase(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp(prefix="r286_")
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)
        self.ledger_dir = os.path.join(self.workspace, ".mindseam")
        os.makedirs(self.ledger_dir)

    def _write_bytes(self, name, data):
        with open(os.path.join(self.ledger_dir, name), "wb") as fh:
            fh.write(data)


class InfoMemoryPromotionTests(_WorkspaceBase):
    def test_text_face_promotes_to_one_mb(self):
        # A single ~1 MB blob lands the workspace total in the KB dead zone.
        self._write_bytes("blob.bin", b"x" * 1048540)
        res = invoke_cli(self.workspace, ["info", "--memory"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("size:      1.0 MB", res.stdout)
        self.assertNotIn("1024.0 KB", res.stdout)

    def test_json_face_promotes_to_one_mb(self):
        self._write_bytes("blob.bin", b"x" * 1048540)
        res = invoke_cli(self.workspace, ["info", "--memory", "--json"])
        self.assertEqual(res.returncode, 0)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["human"], "1.0 MB")
        self.assertEqual(payload["bytes"], 1048540)

    def test_ordinary_size_still_renders_its_unit(self):
        # A 1.5 KB workspace is untouched by the promotion fix.
        self._write_bytes("blob.bin", b"x" * 1536)
        res = invoke_cli(self.workspace, ["info", "--memory"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("size:      1.5 KB", res.stdout)


class CatalogTests(unittest.TestCase):
    def test_entry_present_since_r286_default_true(self):
        entry = next(
            (e for e in mindseam._FEATURE_CATALOG
             if e["id"] == "humanize-bytes-unit-promotion"),
            None,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["since"], "r286")
        self.assertTrue(entry["default"])

    def test_r286_is_the_highest_round(self):
        self.assertEqual(max(_since_ints()), 286)

    def test_catalog_grew_to_137(self):
        self.assertEqual(len(mindseam._FEATURE_CATALOG), 137)

    def test_recent_window_is_107(self):
        recent = [n for n in _since_ints() if n >= 170]
        self.assertEqual(len(recent), 107)


if __name__ == "__main__":
    unittest.main()
