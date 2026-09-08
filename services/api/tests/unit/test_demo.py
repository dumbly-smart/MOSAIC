"""Check all demo outcomes through the actual engine and CLI."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from demo import SCENARIOS, scenario_input
from services.api.app.verification import VerificationEngine


class DemoTests(unittest.TestCase):
    def test_scenario_outcomes(self):
        expected = {
            "compliant": "qualify",
            "missing-document": "manual_review",
            "low-confidence": "manual_review",
            "weak-match": "manual_review",
            "identity-mismatch": "consider_disqualification",
            "portal-unavailable": "manual_review",
            "inactive-registration": "consider_disqualification",
            "conflicting-evidence": "manual_review",
            "debarment-hit": "consider_disqualification",
        }
        for name in SCENARIOS:
            with self.subTest(name=name):
                result = VerificationEngine().evaluate(scenario_input(name))
                self.assertEqual(result.recommendation, expected[name])

    def test_json_cli_and_confidence_override(self):
        root = Path(__file__).resolve().parents[4]
        result = subprocess.run(
            [sys.executable, "demo.py", "--json", "--confidence", "0.4"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(result.stdout)[0]["recommendation"], "manual_review")

    def test_invalid_cli_confidence_is_rejected(self):
        root = Path(__file__).resolve().parents[4]
        result = subprocess.run(
            [sys.executable, "demo.py", "--confidence", "2"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
