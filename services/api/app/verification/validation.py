"""Validate trusted domain inputs before evaluating compliance.

Malformed inputs raise ValueError; missing or uncertain evidence remains a finding.
Model confidence is an uncalibrated input signal, never a probability guarantee.
"""

from math import isfinite

from services.api.app.domain import ComparisonState, EvidenceStatus, Severity, VerificationInput


def nonempty(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")


def probability(value: object, label: str) -> None:
    if type(value) not in (float, int) or not isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{label} must be a finite number between 0 and 1")


def validate(request: VerificationInput) -> None:
    nonempty(request.case_id, "case_id")
    nonempty(request.verification_run_id, "verification_run_id")
    if not request.rules:
        raise ValueError("At least one tender rule is required")
    ids = [rule.id for rule in request.rules]
    if len(set(ids)) != len(ids):
        raise ValueError("Rule IDs must be unique")
    if len({rule.rule_set_version for rule in request.rules}) != 1:
        raise ValueError("All rules must belong to the same rule-set version")
    for rule in request.rules:
        for key in ("id", "rule_set_version", "requirement_id", "required_field"):
            nonempty(getattr(rule, key), key)
        if not isinstance(rule.severity, Severity):
            raise ValueError("Invalid rule severity")  # noqa: TRY004 - stable validation API
        if type(rule.weight) is not int or rule.weight <= 0:
            raise ValueError("Rule weights must be positive integers")
        for key in (
            "minimum_extraction_confidence",
            "minimum_retrieval_similarity",
            "minimum_comparison_confidence",
        ):
            probability(getattr(rule, key), key)
        if rule.portal_source is not None:
            nonempty(rule.portal_source, "portal_source")
            nonempty(rule.portal_attribute, "portal_attribute")
            if type(rule.portal_expected_value) not in (str, bool, int, float):
                raise ValueError("Portal rules require a scalar expected value")
            if isinstance(rule.portal_expected_value, str):
                nonempty(rule.portal_expected_value, "portal_expected_value")
            if type(rule.portal_expected_value) is float and not isfinite(
                rule.portal_expected_value
            ):
                raise ValueError("Expected value must be finite")
        elif rule.portal_attribute is not None or rule.portal_expected_value is not None:
            raise ValueError("Portal conditions require a portal source")

    for field in request.extracted_fields:
        for key in ("id", "document_id", "name", "normalized_value", "evidence_ref"):
            nonempty(getattr(field, key), key)
        probability(field.confidence, "extraction confidence")
    if len({field.id for field in request.extracted_fields}) != len(request.extracted_fields):
        raise ValueError("Extracted field IDs must be unique")
    refs = {field.evidence_ref for field in request.extracted_fields}
    requirements = {rule.requirement_id for rule in request.rules}
    for item in (*request.retrieval_candidates, *request.comparisons):
        if item.requirement_id not in requirements:
            raise ValueError("Unknown requirement reference")
        if item.bidder_evidence_ref not in refs:
            raise ValueError("Unknown evidence reference")
    for candidate in request.retrieval_candidates:
        probability(candidate.similarity_score, "retrieval similarity")
        if type(candidate.rank) is not int or candidate.rank < 1:
            raise ValueError("Retrieval rank must be a positive integer")
    for comparison in request.comparisons:
        if not isinstance(comparison.state, ComparisonState):
            raise ValueError("Invalid comparison state")  # noqa: TRY004 - stable validation API
        probability(comparison.confidence, "comparison confidence")
        for key in ("explanation", "model_version", "prompt_version"):
            nonempty(getattr(comparison, key), key)
    for portal in request.portal_evidence:
        if not isinstance(portal.status, EvidenceStatus):
            raise ValueError("Invalid portal status")  # noqa: TRY004 - stable validation API
        for key in ("source", "subject_identifier", "attribute", "reference"):
            nonempty(getattr(portal, key), key)
