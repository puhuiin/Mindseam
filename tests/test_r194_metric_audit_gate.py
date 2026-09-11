# -*- coding: utf-8 -*-
"""Round 194 guards: the metric audit's gate fires on the right things.

``tools/metric_audit.py`` answers the question a reader of the metric
layer naturally asks — is each of these ~90 detectors alive, bounded,
distinct and responsive — but a report nobody runs is not a guard. r194
adds ``--check``, which turns the two invariants that hold for *every*
legal input into an exit code:

  * no metric raises on a boundary-sanitized row
  * no metric that documents a 0-100 or 0-1 scale leaves it

Liveness and redundancy are reported but deliberately not gated: they
depend on how well the synthetic corpus happens to exercise a detector,
and a gate that can flake is worse than no gate.

This round pins both directions. A gate that cannot fail is decoration,
so the failure path is exercised against a report with an injected crash
rather than being assumed.
"""

import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import metric_audit


class MetricAuditGateTests(unittest.TestCase):

    def test_the_gate_passes_on_the_shipped_controller(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = metric_audit.main(["--check", "--samples", "40"])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("PASS metric layer", out.getvalue())

    def test_the_gate_fails_on_a_crashing_metric(self):
        # A gate that cannot fail is decoration. Inject the failure.
        original = metric_audit.analyse

        def broken(module, sessions, corr_cut):
            report = original(module, sessions, corr_cut)
            report["crashes"]["injected_probe"] = "TypeError: injected"
            return report

        metric_audit.analyse = broken
        try:
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                code = metric_audit.main(["--check", "--samples", "20"])
        finally:
            metric_audit.analyse = original
        self.assertEqual(code, 1)
        self.assertIn("FAIL", err.getvalue())
        self.assertIn("injected_probe", err.getvalue())

    def test_the_gate_fails_on_an_out_of_range_metric(self):
        original = metric_audit.analyse

        def broken(module, sessions, corr_cut):
            report = original(module, sessions, corr_cut)
            report["out_of_range"].append(
                {"metric": "injected_probe", "declared": [0, 100],
                 "observed": [-5, 140]})
            return report

        metric_audit.analyse = broken
        try:
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(err):
                code = metric_audit.main(["--check", "--samples", "20"])
        finally:
            metric_audit.analyse = original
        self.assertEqual(code, 1)
        self.assertIn("declared range", err.getvalue())

    def test_the_report_face_still_works_and_stays_off_the_gate(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = metric_audit.main(["--samples", "30"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("Mindseam metric audit", text)
        self.assertIn("field sensitivity", text)

    def test_the_corpus_counts_rows_not_sessions(self):
        import json
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            metric_audit.main(["--samples", "30", "--json"])
        report = json.loads(out.getvalue())
        self.assertEqual(report["corpus"]["sessions"], 30)
        self.assertGreater(report["corpus"]["rows"], 30,
                           "rows must count history entries, not sessions")


if __name__ == "__main__":
    unittest.main()
