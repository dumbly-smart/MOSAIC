import unittest

from services.api.app.verification.weighted import assess, validate_criteria


class WeightedTests(unittest.TestCase):
    def rule(self, **changes):
        rule = {
            "id": "C1",
            "clause": "Amount >= 25000 INR",
            "field": "Amount",
            "operator": ">=",
            "threshold": 25000,
            "unit": "INR",
            "weight": 100,
            "tender_id": "synthetic",
            "rule_version": "v3",
            "source": {"clause": "Amount >= 25000 INR", "reference": "synthetic:C1"},
        }
        rule.update(changes)
        return rule

    def bounds(self, lower=24000, upper=25000):
        return {"lower": lower, "upper": upper, "lower_inclusive": True, "upper_inclusive": False}

    def fallback(self):
        return {
            "bounds": self.bounds(),
            "source": {"clause": "Review [24000,25000)", "reference": "synthetic:review"},
        }

    def evidence(self, value=25000, uncertain=False):
        return {
            "value": value,
            "unit": "INR",
            "uncertain": uncertain,
            "source_quote": f"Amount: {value} INR",
            "document_id": "synthetic",
            "line": 256,
            "page": 11,
            "bbox": None,
        }

    def test_no_invented_tolerance(self):
        for value, status in ((25000, "passed"), (24999, "failed"), (15000, "failed")):
            result = assess(self.rule(), self.evidence(value))
            self.assertEqual(result["status"], status)
            self.assertEqual(result["earned_points"], 100 if status == "passed" else 0)

    def test_fallback_boundaries_and_primary_precedence(self):
        rule = self.rule(fallback=self.fallback())
        for value, status, points in (
            (23999, "failed", 0),
            (24000, "unsure", 50),
            (24999, "unsure", 50),
            (25000, "passed", 100),
        ):
            result = assess(rule, self.evidence(value))
            self.assertEqual((result["status"], result["earned_points"]), (status, points))
        self.assertEqual(
            assess(rule, self.evidence(24500))["reason_code"], "explicit_fallback_range"
        )

    def test_missing_is_unsure_zero_awaiting_clarification(self):
        result = assess(self.rule(), None)
        self.assertEqual(
            (result["status"], result["reason_code"], result["earned_points"]),
            ("unsure", "missing_information", 0),
        )
        self.assertTrue(result["clarification_required"])
        self.assertIsNone(result["evidence"])

    def test_uncertainty_never_earns_half(self):
        for value in (24500, 26000):
            result = assess(self.rule(fallback=self.fallback()), self.evidence(value, True))
            self.assertEqual((result["status"], result["earned_points"]), ("manual_review", 0))

    def test_processing_failure_is_not_missing(self):
        result = assess(self.rule(), None, processing_error=True)
        self.assertEqual(result["status"], "manual_review")
        self.assertEqual(result["reason_code"], "processing_or_rule_error")
        self.assertFalse(result["clarification_required"])

    def test_primary_range_is_full_pass(self):
        rule = self.rule(operator="range", bounds=self.bounds(10, 15))
        rule.pop("threshold")
        for value, points in ((9, 0), (10, 100), (12, 100), (15, 0)):
            self.assertEqual(assess(rule, self.evidence(value))["earned_points"], points)

    def test_maximum_and_equality(self):
        for op, value, points in (
            ("<=", 24, 100),
            ("<=", 24.01, 0),
            ("==", 24, 100),
            ("==", 23.99, 0),
        ):
            self.assertEqual(
                assess(self.rule(operator=op, threshold=24), self.evidence(value))["earned_points"],
                points,
            )

    def test_invalid_rules_rejected_and_fail_closed(self):
        for change in (
            {"source": {}},
            {"tolerance_percent": 5},
            {"fallback": {"bounds": self.bounds()}},
            {"fallback": {"bounds": self.bounds(26, 25), "source": self.rule()["source"]}},
            {"rule_version": ""},
            {"weight": float("nan")},
        ):
            rule = self.rule(**change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_criteria([rule])
            self.assertEqual(
                assess(rule, self.evidence())["reason_code"], "processing_or_rule_error"
            )

    def test_quotas_and_duplicate_ids(self):
        validate_criteria([self.rule()])
        for criteria in ([self.rule(weight=80)], [self.rule(weight=50), self.rule(weight=50)]):
            with self.assertRaises(ValueError):
                validate_criteria(criteria)

    def test_invalid_evidence_zero_review(self):
        for change in (
            {"value": float("nan")},
            {"value": True},
            {"unit": "USD"},
            {"source_quote": ""},
            {"uncertain": "false"},
            {"line": None, "page": None},
        ):
            evidence = self.evidence()
            evidence.update(change)
            result = assess(self.rule(), evidence)
            self.assertEqual((result["status"], result["earned_points"]), ("manual_review", 0))

    def test_provenance(self):
        result = assess(self.rule(), self.evidence())
        self.assertEqual(result["policy_version"], "tender-evidence-quota-v2")
        self.assertEqual(result["rule_version"], "v3")
        self.assertEqual(result["source"]["reference"], "synthetic:C1")
        self.assertEqual(result["evidence"]["line"], 256)

    def typed_rule(self, value_type, operator, expected):
        rule = self.rule(value_type=value_type, operator=operator, expected=expected)
        rule.pop("threshold")
        rule.pop("unit")
        return rule

    def typed_evidence(self, value):
        evidence = self.evidence()
        evidence["value"] = value
        evidence.pop("unit")
        evidence["source_quote"] = f"Grounded declaration: {value}"
        return evidence

    def test_boolean_document_categorical_and_date_rules(self):
        cases = (
            (self.typed_rule("boolean", "==", False), False, True),
            (self.typed_rule("boolean", "==", False), True, False),
            (self.typed_rule("document_presence", "==", True), True, True),
            (self.typed_rule("categorical", "==", "active"), "ACTIVE", True),
            (self.typed_rule("categorical", "one_of", ["gold", "silver"]), "silver", True),
            (self.typed_rule("date", ">=", "2026-01-01"), "2026-06-01", True),
            (self.typed_rule("date", "<=", "2026-12-31"), "2027-01-01", False),
        )
        for rule, value, passed in cases:
            with self.subTest(rule=rule, value=value):
                result = assess(rule, self.typed_evidence(value))
                self.assertEqual(result["status"], "passed" if passed else "failed")
                self.assertEqual(result["earned_points"], 100 if passed else 0)

    def test_invalid_typed_rules_and_evidence_fail_closed(self):
        invalid_rules = (
            self.typed_rule("boolean", "==", "false"),
            self.typed_rule("document_presence", "==", False),
            self.typed_rule("categorical", "one_of", []),
            self.typed_rule("date", ">=", "01/01/2026"),
            self.typed_rule("invented", "==", True),
        )
        for rule in invalid_rules:
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                validate_criteria([rule])
        result = assess(self.typed_rule("boolean", "==", False), self.typed_evidence("false"))
        self.assertEqual((result["status"], result["earned_points"]), ("manual_review", 0))
