import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


class BenchmarkV2Tests(unittest.TestCase):
    def run_baseline(self, text, output_content=None):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source, output = folder / "source.txt", folder / "result.json"
            source.write_text(text, encoding="utf-8")
            if output_content is not None:
                output.write_text(output_content, encoding="utf-8")
            run = subprocess.run(
                [
                    sys.executable,
                    "benchmark.py",
                    "baseline",
                    "--text",
                    str(source),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            return run, output.read_text() if output.exists() else None

    def test_missing_information_not_dropped_or_renormalized(self):
        run, raw = self.run_baseline("Relevant completed experience: 7 years.")
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(raw)
        self.assertEqual(report["score"], 20)
        self.assertEqual(len(report["results"]), 5)
        self.assertEqual(report["results"][0]["reason_code"], "missing_information")
        self.assertTrue(report["clarification_required"])
        self.assertEqual(len(report["unresolved_criteria"]), 4)

    def test_empty_document_is_unsure_zero(self):
        run, raw = self.run_baseline("")
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(raw)
        self.assertEqual(report["score"], 0)
        self.assertTrue(all(r["status"] == "unsure" for r in report["results"]))

    def test_conflicting_and_wrong_unit_evidence_is_not_missing(self):
        for text in (
            "Current bid security: 15000 INR.\nCurrent bid security: 40000 INR.",
            "Current bid security: 40000 USD.",
        ):
            run, raw = self.run_baseline(text)
            self.assertEqual(run.returncode, 0, run.stderr)
            first = json.loads(raw)["results"][0]
            self.assertEqual(first["status"], "manual_review")
            self.assertEqual(first["reason_code"], "evidence_unreliable")
            self.assertEqual(first["earned_points"], 0)

    def test_historical_report_is_not_overwritten(self):
        original = '{"scoring_policy":"quota-full-half-zero-v1","score":55}'
        run, raw = self.run_baseline("Relevant completed experience: 7 years.", original)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(raw, original)
