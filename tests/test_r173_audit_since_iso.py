# -*- coding: utf-8 -*-
"""Round 173 guards: ``audit --since`` / ``--until`` speak three shapes.

r161 gave the window flags a single meaning — bare seconds before
now (``3600``). r173 keeps that exact contract and adds two more
readings, borrowed from ``git log --since=2024-01-01`` (an absolute
date) and ``docker logs --since 30m`` / ``journalctl --since "2 hours
ago"`` (a relative span):

  * ``30s`` ``45m`` ``12h`` ``7d`` ``2w`` — a span
  * ``2026-09-01`` ``2026-09-01T10:30:00`` — an instant
  * ``3600`` — still seconds (r161 hosts are untouched)

The parser runs once in ``mode_audit`` so the negative check, the
``history_window`` block, and the JSON face all agree on one number.
An unreadable value (``garbage``) or a negative result (a future date)
is refused with exit 2 — the same contract r161 pinned for bare
negative seconds — so a typo is never silently read as a window that
matches nothing.

The window is *parsed* before the ledger is read, so an empty
workspace still resolves the three shapes and never creates a
``.mindseam`` directory.
"""

import datetime
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINDSEAM = ROOT / "mindseam" / "scripts" / "mindseam.py"

if str(ROOT / "mindseam" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "mindseam" / "scripts"))
import mindseam  # noqa: E402


def _invoke(args, cwd, env=None):
    run_env = os.environ.copy()
    run_env.pop("MINDSEAM_INTENSITY", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, str(MINDSEAM), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        env=run_env,
    )


def _write_history(workspace, rows):
    path = Path(workspace) / ".mindseam" / "history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")


def _local_epoch(text):
    """Mirror ``parse_window_value``: a naive date is read local."""
    return int(datetime.datetime.fromisoformat(text).timestamp())


def _utc_epoch(text):
    aware = datetime.datetime.fromisoformat(text)
    if aware.tzinfo is None:
        aware = aware.replace(tzinfo=timezone.utc)
    return int(aware.timestamp())


class AuditSinceIsoBase(unittest.TestCase):

    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        self._old_cwd = os.getcwd()
        os.chdir(self.workspace)
        self._now = int(time.time())

    def tearDown(self):
        os.chdir(self._old_cwd)
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _ledger(self, goal="audit demo", core=(), verified=(),
                open_=(), next_="c1 — one"):
        path = Path(self.workspace) / ".mindseam" / "WORKSPACE.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = ["# Mindseam Workspace Ledger", ""]
        text += ["## Goal", goal, ""]
        text += ["## Core"] + list(core) + [""]
        text += ["## Verified"] + list(verified) + [""]
        text += ["## Open"] + list(open_) + [""]
        text += ["## Next", next_, ""]
        path.write_text("\n".join(text), encoding="utf-8")


class BareSecondsPreservedTests(AuditSinceIsoBase):
    """r161 bare-seconds semantics must survive the grammar change."""

    def test_bare_seconds_unchanged_in_window_block(self):
        r = _invoke(["audit", "--since", "3600", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_window"]["since_seconds"], 3600,
                         payload)
        # since_cutoff == now - since_seconds, so it tracks now within
        # a second of the value the parser saw.
        self.assertAlmostEqual(
            payload["history_window"]["since_cutoff"],
            self._now - 3600, delta=2,
            msg=payload["history_window"])

    def test_bare_seconds_still_narrows_history(self):
        # Pin the r161 behaviour end-to-end: a tight bare-seconds
        # window keeps only recent rows.
        self._ledger()
        _write_history(self.workspace, [
            {"t": self._now - 10**6, "next": "", "verified": 0, "open": 0},
            {"t": self._now - 5, "next": "", "verified": 0, "open": 0},
            {"t": self._now - 1, "next": "", "verified": 0, "open": 0},
        ])
        r = _invoke(["audit", "--since", "60", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_window"]["since_seconds"], 60)
        # Both blank rows (-5, -1) fall in the 60s window; the
        # ancient row at -10**6 is excluded (rows_out == 2).
        self.assertEqual(payload["history_window"]["rows_out"], 2)
        self.assertEqual(payload["findings"][0]["evidence"]["blank_count"], 2,
                         payload)
        self.assertEqual(payload["findings"][0]["evidence"]["blank_indices"],
                         [1, 2], payload)


class SpanParsingTests(AuditSinceIsoBase):
    """Relative spans resolve to the right multiple of seconds."""

    def test_spans_resolve_to_seconds(self):
        cases = [
            ("30s", 30), ("45m", 2700), ("12h", 43200),
            ("7d", 604800), ("2w", 1209600),
        ]
        for token, expect in cases:
            with self.subTest(token=token):
                r = _invoke(["audit", "--since", token, "--json"],
                            cwd=self.workspace)
                self.assertEqual(r.returncode, 0, r.stderr)
                payload = json.loads(r.stdout)
                self.assertEqual(
                    payload["history_window"]["since_seconds"], expect,
                    payload["history_window"])

    def test_span_whitespace_is_trimmed(self):
        # The parser strips surrounding whitespace (borrowed from
        # argparse's own tolerance of " 3600 "). A host that shells
        # out with padding must not see a refusal.
        r = _invoke(["audit", "--since", " 1h ", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_window"]["since_seconds"], 3600,
                         payload)

    def test_span_narrows_history_like_seconds(self):
        # A span is just seconds in disguise; prove it narrows the
        # same way the bare form does.
        self._ledger()
        _write_history(self.workspace, [
            {"t": self._now - 10**6, "next": "", "verified": 0, "open": 0},
            {"t": self._now - 30, "next": "", "verified": 0, "open": 0},
            {"t": self._now - 1, "next": "a", "verified": 0, "open": 0},
        ])
        r = _invoke(["audit", "--since", "1m", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_window"]["since_seconds"], 60)
        self.assertEqual(payload["findings"][0]["evidence"]["blank_count"], 1,
                         payload)


class IsoDateParsingTests(AuditSinceIsoBase):
    """An absolute date is read the way ``git log --since=2024-01-01`` reads it."""

    def test_past_date_yields_positive_window(self):
        # 2026-01-01 is before the run; the window must be positive
        # and pin the cutoff to that date's local epoch.
        r = _invoke(["audit", "--since", "2026-01-01", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        w = payload["history_window"]
        self.assertIsInstance(w["since_seconds"], int)
        self.assertGreater(w["since_seconds"], 0, w)
        # since_cutoff == now - since_seconds == the date's local epoch.
        self.assertEqual(w["since_cutoff"], _local_epoch("2026-01-01"), w)

    def test_past_date_keeps_all_rows_in_window(self):
        # Every row is newer than 2026-01-01, so the whole history
        # survives the window.
        self._ledger()
        _write_history(self.workspace, [
            {"t": self._now - 10**6, "next": "", "verified": 0, "open": 0},
            {"t": self._now - 1, "next": "", "verified": 0, "open": 0},
        ])
        r = _invoke(["audit", "--since", "2026-01-01", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["history_window"]["rows_in"], 2)
        self.assertEqual(payload["history_window"]["rows_out"], 2)

    def test_date_with_time_component(self):
        r = _invoke(["audit", "--since", "2026-09-01T10:30:00", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        w = payload["history_window"]
        self.assertGreater(w["since_seconds"], 0, w)
        self.assertEqual(w["since_cutoff"],
                         _local_epoch("2026-09-01T10:30:00"), w)

    def test_trailing_z_is_utc_not_local(self):
        # The bare instant and the Z instant must NOT collapse to the
        # same cutoff: Z pins UTC, the bare form pins local time.
        bare = _invoke(["audit", "--since", "2026-09-01T10:30:00",
                        "--json"], cwd=self.workspace)
        zulu = _invoke(["audit", "--since", "2026-09-01T10:30:00Z",
                        "--json"], cwd=self.workspace)
        self.assertEqual(bare.returncode, 0, bare.stderr)
        self.assertEqual(zulu.returncode, 0, zulu.stderr)
        bare_cut = json.loads(bare.stdout)["history_window"]["since_cutoff"]
        zulu_cut = json.loads(zulu.stdout)["history_window"]["since_cutoff"]
        self.assertNotEqual(bare_cut, zulu_cut)
        # The two cutoffs differ by exactly the local-vs-UTC offset
        # for that instant (robust against any machine timezone).
        expected_diff = _local_epoch("2026-09-01T10:30:00") - \
            _utc_epoch("2026-09-01T10:30:00Z")
        self.assertAlmostEqual(bare_cut - zulu_cut, expected_diff, delta=2,
                               msg=(bare_cut, zulu_cut, expected_diff))


class RefusalTests(AuditSinceIsoBase):
    """The three-shape grammar refuses the same way r161 refused negatives."""

    def test_unreadable_value_refused_with_hint(self):
        r = _invoke(["audit", "--since", "garbage"], cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--since", r.stderr)
        # The refusal points at the accepted grammar so the caller can
        # self-correct instead of guessing.
        self.assertIn("accepted:", r.stderr)
        self.assertIn("ISO-8601", r.stderr)

    def test_empty_value_refused(self):
        r = _invoke(["audit", "--since", ""], cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--since", r.stderr)

    def test_future_date_refused_as_negative(self):
        # A date after now parses to a negative window, which the
        # r161 negative check must still refuse.
        r = _invoke(["audit", "--until", "2999-01-01"], cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--until", r.stderr)
        self.assertIn("non-negative", r.stderr)

    def test_far_future_date_refused_as_negative(self):
        # A date far in the future still goes negative and is refused;
        # the negative check is independent of how far the date is.
        r = _invoke(["audit", "--since", "2999-12-31"], cwd=self.workspace)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--since", r.stderr)
        self.assertIn("non-negative", r.stderr)


class WindowBlockConsistencyTests(AuditSinceIsoBase):
    """Both flags compose and the JSON face stays internally consistent."""

    def test_since_until_both_spans(self):
        r = _invoke(["audit", "--since", "2h", "--until", "30m", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        w = json.loads(r.stdout)["history_window"]
        self.assertEqual(w["since_seconds"], 7200)
        self.assertEqual(w["until_seconds"], 1800)
        # since_cutoff < until_cutoff because the lower bound is older.
        self.assertLess(w["since_cutoff"], w["until_cutoff"])

    def test_spans_compose_with_at(self):
        # --at still slices history; the window parsing is independent
        # of the --at resolution, so both flags can ride together.
        self._ledger()
        _write_history(self.workspace, [
            {"t": self._now - 1, "next": "a", "verified": 0, "open": 0},
        ])
        r = _invoke(["audit", "--since", "30m", "--at", "1", "--json"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        w = json.loads(r.stdout)["history_window"]
        self.assertEqual(w["since_seconds"], 1800)
        self.assertEqual(w["at_row"], 1)

    def test_empty_workspace_creates_no_dot_mindseam(self):
        # The window is parsed before any ledger read; an empty ws
        # must resolve the three shapes without materialising state.
        r = _invoke(["audit", "--since", "7d", "--until", "1h"],
                    cwd=self.workspace)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(
            (Path(self.workspace) / ".mindseam").exists(),
            "audit --since in an empty workspace must not create .mindseam")


class ParserUnitTests(unittest.TestCase):
    """``parse_window_value`` is the single source of truth the CLI uses."""

    def test_unit_bare_seconds(self):
        self.assertEqual(mindseam.parse_window_value(3600, 1_000_000),
                         (3600, None))

    def test_unit_spans(self):
        now = 1_000_000
        self.assertEqual(mindseam.parse_window_value("30s", now), (30, None))
        self.assertEqual(mindseam.parse_window_value("45m", now), (2700, None))
        self.assertEqual(mindseam.parse_window_value("12h", now),
                         (43200, None))
        self.assertEqual(mindseam.parse_window_value("7d", now),
                         (604800, None))
        self.assertEqual(mindseam.parse_window_value("2w", now),
                         (1209600, None))

    def test_unit_iso_date(self):
        now = int(time.time())
        secs, reason = mindseam.parse_window_value("2026-01-01", now)
        self.assertIsNone(reason)
        self.assertEqual(secs, now - _local_epoch("2026-01-01"))

    def test_unit_none_passthrough(self):
        self.assertEqual(mindseam.parse_window_value(None, 1_000_000),
                         (None, None))

    def test_unit_unreadable_reason(self):
        secs, reason = mindseam.parse_window_value("garbage", 1_000_000)
        self.assertIsNone(secs)
        self.assertIsNotNone(reason)
        self.assertIn("as a time", reason)


if __name__ == "__main__":
    unittest.main()
