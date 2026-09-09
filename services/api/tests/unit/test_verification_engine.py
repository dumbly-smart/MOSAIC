"""Synthetic verification scenarios for the first vertical slice."""

import unittest
from dataclasses import replace

from services.api.app.domain import (
    ComparisonResult,
    ComparisonState,
    EvidenceResult,
    EvidenceStatus,
    ExtractedField,
    FindingStatus,
    Recommendation,
    RetrievalCandidate,
    RiskLevel,
    Severity,
    TenderRule,
    VerificationInput,
)
from services.api.app.verification import VerificationEngine


class VerificationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rule = TenderRule(
            id="GST-IDENTITY-01",
            rule_set_version="2026.1",
            requirement_id="REQ-GST-01",
            required_field="gst_registration_number",
            severity=Severity.HIGH,
            weight=100,
            portal_source="mock_gst_sandbox",
            portal_attribute="registration_status",
            portal_expected_value="active",
        )
        self.field = ExtractedField(
            id="FIELD-1",
            document_id="DOC-1",
            name="gst_registration_number",
            normalized_value="SYNTHETIC-GST-001",
            confidence=0.96,
            evidence_ref="DOC-1#page=1&region=gst-number",
            page_number=1,
            region="gst-number",
        )
        self.candidate = RetrievalCandidate(
            requirement_id="REQ-GST-01",
            bidder_evidence_ref=self.field.evidence_ref,
            similarity_score=0.91,
            rank=1,
        )
        self.comparison = ComparisonResult(
            requirement_id="REQ-GST-01",
            bidder_evidence_ref=self.field.evidence_ref,
            state=ComparisonState.MATCH,
            confidence=0.94,
            explanation="The submitted certificate contains the required synthetic identifier.",
            model_version="qwen3-vl-test-double",
            prompt_version="comparison-v1",
        )
        self.portal = EvidenceResult(
            source="mock_gst_sandbox",
            subject_identifier="SYNTHETIC-GST-001",
            attribute="registration_status",
            value="active",
            status=EvidenceStatus.VERIFIED,
            reference="mock://gst/SYNTHETIC-GST-001",
        )

    def request(self, **changes: object) -> VerificationInput:
        defaults: dict[str, object] = {
            "case_id": "CASE-1",
            "verification_run_id": "RUN-1",
            "rules": (self.rule,),
            "extracted_fields": (self.field,),
            "retrieval_candidates": (self.candidate,),
            "comparisons": (self.comparison,),
            "portal_evidence": (self.portal,),
        }
        defaults.update(changes)
        return VerificationInput(**defaults)  # type: ignore[arg-type]

    def test_verified_match_qualifies(self) -> None:
        outcome = VerificationEngine().evaluate(self.request())

        self.assertEqual(outcome.findings[0].status, FindingStatus.VERIFIED)
        self.assertEqual(outcome.score, 100)
        self.assertEqual(outcome.risk, RiskLevel.LOW)
        self.assertEqual(outcome.recommendation, Recommendation.QUALIFY)
        self.assertIn(self.field.evidence_ref, outcome.findings[0].evidence_refs)

    def test_missing_required_field_fails_closed(self) -> None:
        outcome = VerificationEngine().evaluate(
            self.request(extracted_fields=(), retrieval_candidates=(), comparisons=())
        )

        self.assertEqual(outcome.findings[0].status, FindingStatus.NEEDS_MANUAL_REVIEW)
        self.assertEqual(outcome.recommendation, Recommendation.MANUAL_REVIEW)

    def test_low_extraction_confidence_fails_closed(self) -> None:
        low_confidence = replace(self.field, confidence=0.40)
        outcome = VerificationEngine().evaluate(self.request(extracted_fields=(low_confidence,)))

        self.assertEqual(outcome.findings[0].status, FindingStatus.NEEDS_MANUAL_REVIEW)

    def test_no_reliable_pgvector_match_fails_closed(self) -> None:
        weak_candidate = replace(self.candidate, similarity_score=0.30)
        outcome = VerificationEngine().evaluate(
            self.request(retrieval_candidates=(weak_candidate,))
        )

        self.assertEqual(outcome.findings[0].status, FindingStatus.NEEDS_MANUAL_REVIEW)

    def test_qwen_mismatch_creates_inconsistent_finding(self) -> None:
        mismatch = replace(
            self.comparison,
            state=ComparisonState.MISMATCH,
            explanation="The submitted identifier does not match the tender requirement.",
        )
        outcome = VerificationEngine().evaluate(self.request(comparisons=(mismatch,)))

        self.assertEqual(outcome.findings[0].status, FindingStatus.INCONSISTENT)
        self.assertEqual(outcome.risk, RiskLevel.HIGH)
        self.assertEqual(
            outcome.recommendation,
            Recommendation.CONSIDER_DISQUALIFICATION,
        )

    def test_unavailable_portal_fails_closed(self) -> None:
        unavailable = replace(self.portal, status=EvidenceStatus.UNAVAILABLE, value=None)
        outcome = VerificationEngine().evaluate(self.request(portal_evidence=(unavailable,)))

        self.assertEqual(outcome.findings[0].status, FindingStatus.NEEDS_MANUAL_REVIEW)
        self.assertEqual(outcome.recommendation, Recommendation.MANUAL_REVIEW)

    def test_portal_evidence_for_another_identifier_is_not_reused(self) -> None:
        unrelated = replace(self.portal, subject_identifier="SYNTHETIC-GST-OTHER")
        outcome = VerificationEngine().evaluate(self.request(portal_evidence=(unrelated,)))

        self.assertEqual(outcome.findings[0].status, FindingStatus.NEEDS_MANUAL_REVIEW)

    def test_empty_rules_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            VerificationEngine().evaluate(self.request(rules=()))

    def test_duplicate_rules_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            VerificationEngine().evaluate(self.request(rules=(self.rule, self.rule)))

    def test_invalid_comparison_state_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            VerificationEngine().evaluate(
                self.request(comparisons=(replace(self.comparison, state="invented"),))
            )

    def test_nonfinite_confidence_is_rejected(self) -> None:
        for value in (float("nan"), float("inf"), -1, 2, "high", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                VerificationEngine().evaluate(
                    self.request(comparisons=(replace(self.comparison, confidence=value),))
                )

    def test_unregistered_evidence_reference_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            VerificationEngine().evaluate(
                self.request(
                    comparisons=(replace(self.comparison, bidder_evidence_ref="invented"),)
                )
            )

    def test_wrong_portal_attribute_requires_review(self) -> None:
        outcome = VerificationEngine().evaluate(
            self.request(portal_evidence=(replace(self.portal, attribute="company_name"),))
        )
        self.assertEqual(outcome.recommendation, Recommendation.MANUAL_REVIEW)

    def test_verified_inactive_registration_is_noncompliant(self) -> None:
        outcome = VerificationEngine().evaluate(
            self.request(portal_evidence=(replace(self.portal, value="inactive"),))
        )
        self.assertEqual(outcome.findings[0].status, FindingStatus.INCONSISTENT)
        self.assertEqual(outcome.score, 0)

    def test_conflicting_portal_results_require_review_in_either_order(self) -> None:
        other = replace(self.portal, value="inactive")
        for evidence in ((self.portal, other), (other, self.portal)):
            with self.subTest(evidence=evidence):
                outcome = VerificationEngine().evaluate(self.request(portal_evidence=evidence))
                self.assertEqual(outcome.recommendation, Recommendation.MANUAL_REVIEW)

    def test_conflicting_comparisons_require_review_in_either_order(self) -> None:
        other = replace(self.comparison, state=ComparisonState.MISMATCH)
        for comparisons in ((self.comparison, other), (other, self.comparison)):
            outcome = VerificationEngine().evaluate(self.request(comparisons=comparisons))
            self.assertEqual(outcome.recommendation, Recommendation.MANUAL_REVIEW)

    def test_conflicting_fields_require_review(self) -> None:
        other = replace(
            self.field,
            id="FIELD-2",
            normalized_value="SYNTHETIC-OTHER",
            evidence_ref="DOC-2#page=1",
        )
        outcome = VerificationEngine().evaluate(self.request(extracted_fields=(self.field, other)))
        self.assertEqual(outcome.recommendation, Recommendation.MANUAL_REVIEW)

    def test_missing_portal_value_requires_review(self) -> None:
        outcome = VerificationEngine().evaluate(
            self.request(portal_evidence=(replace(self.portal, value=None),))
        )
        self.assertEqual(outcome.recommendation, Recommendation.MANUAL_REVIEW)

    def test_invalid_rule_configuration_is_rejected(self) -> None:
        for changes in (
            {"weight": 0},
            {"minimum_comparison_confidence": 2},
            {"portal_attribute": None},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                VerificationEngine().evaluate(self.request(rules=(replace(self.rule, **changes),)))

    def test_critical_unresolved_rule_caps_weighted_score(self) -> None:
        critical = replace(
            self.rule,
            id="CRITICAL",
            required_field="missing_field",
            weight=1,
            severity=Severity.CRITICAL,
        )
        outcome = VerificationEngine().evaluate(self.request(rules=(self.rule, critical)))
        self.assertEqual(outcome.score, 40)
        self.assertEqual(outcome.risk, RiskLevel.CRITICAL)
        self.assertEqual(outcome.recommendation, Recommendation.MANUAL_REVIEW)


if __name__ == "__main__":
    unittest.main()
