"""Evaluate normalized AI, retrieval, and portal evidence against tender rules."""

from services.api.app.domain import (
    ComparisonState,
    EvidenceStatus,
    Finding,
    FindingStatus,
    Recommendation,
    RiskLevel,
    Severity,
    TenderRule,
    VerificationInput,
    VerificationOutcome,
)

from .validation import validate


class VerificationEngine:
    """Fail-closed rule evaluator with deterministic scoring and recommendations."""

    def evaluate(self, request: VerificationInput) -> VerificationOutcome:
        validate(request)
        findings = tuple(self._evaluate_rule(rule, request) for rule in request.rules)
        score = self._score(request.rules, findings)
        risk = self._risk(findings)
        recommendation = self._recommend(findings)
        return VerificationOutcome(findings, score, risk, recommendation)

    def _evaluate_rule(self, rule: TenderRule, request: VerificationInput) -> Finding:
        fields = [item for item in request.extracted_fields if item.name == rule.required_field]
        if len(fields) > 1:
            return self._finding(
                rule,
                request,
                FindingStatus.NEEDS_MANUAL_REVIEW,
                "Multiple field candidates require officer review.",
                tuple(item.evidence_ref for item in fields),
            )
        field = next(
            (item for item in request.extracted_fields if item.name == rule.required_field), None
        )
        if field is None:
            return self._finding(
                rule,
                request,
                FindingStatus.NEEDS_MANUAL_REVIEW,
                f"Required evidence '{rule.required_field}' was not found.",
            )

        if not 0 <= field.confidence <= 1 or field.confidence < rule.minimum_extraction_confidence:
            return self._finding(
                rule,
                request,
                FindingStatus.NEEDS_MANUAL_REVIEW,
                f"Extraction confidence for '{rule.required_field}' is below the required threshold.",
                (field.evidence_ref,),
            )

        candidates = [
            item
            for item in request.retrieval_candidates
            if item.requirement_id == rule.requirement_id
            and item.bidder_evidence_ref == field.evidence_ref
        ]
        candidate = max(candidates, key=lambda item: item.similarity_score, default=None)
        if (
            candidate is None
            or not 0 <= candidate.similarity_score <= 1
            or candidate.similarity_score < rule.minimum_retrieval_similarity
        ):
            return self._finding(
                rule,
                request,
                FindingStatus.NEEDS_MANUAL_REVIEW,
                "No reliable tender-requirement match was retrieved.",
                (field.evidence_ref,),
            )

        matching_comparisons = [
            item
            for item in request.comparisons
            if item.requirement_id == rule.requirement_id
            and item.bidder_evidence_ref == field.evidence_ref
        ]
        if len(matching_comparisons) > 1:
            return self._finding(
                rule,
                request,
                FindingStatus.NEEDS_MANUAL_REVIEW,
                "Multiple comparison results require officer review.",
                (field.evidence_ref, rule.requirement_id),
            )
        comparison = next(
            (
                item
                for item in request.comparisons
                if item.requirement_id == rule.requirement_id
                and item.bidder_evidence_ref == field.evidence_ref
            ),
            None,
        )
        if comparison is None or not comparison.explanation.strip():
            return self._finding(
                rule,
                request,
                FindingStatus.NEEDS_MANUAL_REVIEW,
                "The retrieved requirement has no grounded comparison result.",
                (field.evidence_ref, rule.requirement_id),
            )

        refs = (field.evidence_ref, rule.requirement_id)
        if (
            not 0 <= comparison.confidence <= 1
            or comparison.confidence < rule.minimum_comparison_confidence
            or comparison.state
            in {ComparisonState.UNCERTAIN, ComparisonState.NO_EVIDENCE, ComparisonState.PARTIAL}
        ):
            return self._finding(
                rule,
                request,
                FindingStatus.NEEDS_MANUAL_REVIEW,
                f"Qwen3-VL comparison requires officer review: {comparison.explanation}",
                refs,
            )

        if comparison.state in {ComparisonState.MISMATCH, ComparisonState.CONFLICTING}:
            return self._finding(
                rule,
                request,
                FindingStatus.INCONSISTENT,
                f"Document evidence conflicts with the tender requirement: {comparison.explanation}",
                refs,
            )

        if rule.portal_source is not None:
            matching_portals = [
                item
                for item in request.portal_evidence
                if item.source == rule.portal_source
                and item.subject_identifier == field.normalized_value
                and item.attribute == rule.portal_attribute
            ]
            if len(matching_portals) > 1:
                return self._finding(
                    rule,
                    request,
                    FindingStatus.NEEDS_MANUAL_REVIEW,
                    "Multiple portal records require officer review.",
                    refs + tuple(item.reference for item in matching_portals),
                )
            portal = next(
                (
                    item
                    for item in request.portal_evidence
                    if item.source == rule.portal_source
                    and item.subject_identifier == field.normalized_value
                    and item.attribute == rule.portal_attribute
                ),
                None,
            )
            if portal is None or portal.status in {
                EvidenceStatus.UNAVAILABLE,
                EvidenceStatus.NEEDS_MANUAL_REVIEW,
            }:
                return self._finding(
                    rule,
                    request,
                    FindingStatus.NEEDS_MANUAL_REVIEW,
                    f"Required {rule.portal_source} evidence for the extracted identifier is unavailable.",
                    refs,
                )
            refs += (portal.reference,)
            if portal.value is None or type(portal.value) is not type(rule.portal_expected_value):
                return self._finding(
                    rule,
                    request,
                    FindingStatus.NEEDS_MANUAL_REVIEW,
                    "Portal value is missing or has an unexpected type.",
                    refs,
                )
            if isinstance(portal.value, str) and not portal.value.strip():
                return self._finding(
                    rule, request, FindingStatus.NEEDS_MANUAL_REVIEW, "Portal value is empty.", refs
                )
            if portal.value != rule.portal_expected_value:
                return self._finding(
                    rule,
                    request,
                    FindingStatus.INCONSISTENT,
                    f"{rule.portal_attribute}: expected {rule.portal_expected_value!r}, "
                    f"received {portal.value!r} from {rule.portal_source}.",
                    refs,
                )
            if portal.status is EvidenceStatus.INCONSISTENT:
                return self._finding(
                    rule,
                    request,
                    FindingStatus.INCONSISTENT,
                    f"{rule.portal_source} evidence conflicts with the submitted document.",
                    refs,
                )

        return self._finding(
            rule,
            request,
            FindingStatus.VERIFIED,
            f"Verified '{rule.required_field}' against requirement {rule.requirement_id}.",
            refs,
        )

    @staticmethod
    def _finding(
        rule: TenderRule,
        request: VerificationInput,
        status: FindingStatus,
        explanation: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> Finding:
        return Finding(
            case_id=request.case_id,
            verification_run_id=request.verification_run_id,
            rule_id=rule.id,
            rule_set_version=rule.rule_set_version,
            status=status,
            severity=rule.severity,
            explanation=explanation,
            evidence_refs=evidence_refs,
        )

    @staticmethod
    def _score(rules: tuple[TenderRule, ...], findings: tuple[Finding, ...]) -> int:
        total_weight = sum(max(rule.weight, 0) for rule in rules)
        if total_weight == 0:
            return 0
        verified = {
            finding.rule_id for finding in findings if finding.status is FindingStatus.VERIFIED
        }
        earned = sum(max(rule.weight, 0) for rule in rules if rule.id in verified)
        score = round(earned * 100 / total_weight)
        if any(
            finding.severity is Severity.CRITICAL and finding.status is not FindingStatus.VERIFIED
            for finding in findings
        ):
            return min(score, 40)
        return score

    @staticmethod
    def _risk(findings: tuple[Finding, ...]) -> RiskLevel:
        unresolved = [item for item in findings if item.status is not FindingStatus.VERIFIED]
        if any(item.severity is Severity.CRITICAL for item in unresolved):
            return RiskLevel.CRITICAL
        if any(item.severity is Severity.HIGH for item in unresolved):
            return RiskLevel.HIGH
        if unresolved:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def _recommend(findings: tuple[Finding, ...]) -> Recommendation:
        inconsistent = [item for item in findings if item.status is FindingStatus.INCONSISTENT]
        if any(item.severity in {Severity.HIGH, Severity.CRITICAL} for item in inconsistent):
            return Recommendation.CONSIDER_DISQUALIFICATION
        if any(item.status is FindingStatus.NEEDS_MANUAL_REVIEW for item in findings):
            return Recommendation.MANUAL_REVIEW
        if inconsistent:
            return Recommendation.REQUEST_CLARIFICATION
        return Recommendation.QUALIFY
