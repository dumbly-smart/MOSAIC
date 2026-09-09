"""Immutable inputs and outputs used by the verification layer."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ComparisonState(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    PARTIAL = "partial"
    CONFLICTING = "conflicting"
    UNCERTAIN = "uncertain"
    NO_EVIDENCE = "no_evidence"


class EvidenceStatus(StrEnum):
    VERIFIED = "verified"
    INCONSISTENT = "inconsistent"
    UNAVAILABLE = "unavailable"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"


class FindingStatus(StrEnum):
    VERIFIED = "verified"
    MISSING = "missing"
    INCONSISTENT = "inconsistent"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"


class Severity(StrEnum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Recommendation(StrEnum):
    QUALIFY = "qualify"
    REQUEST_CLARIFICATION = "request_clarification"
    MANUAL_REVIEW = "manual_review"
    CONSIDER_DISQUALIFICATION = "consider_disqualification"


@dataclass(frozen=True, slots=True)
class ExtractedField:
    id: str
    document_id: str
    name: str
    normalized_value: str
    confidence: float
    evidence_ref: str
    page_number: int | None = None
    region: str | None = None
    extraction_method: str = "qwen3_vl"


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    requirement_id: str
    bidder_evidence_ref: str
    similarity_score: float
    rank: int


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    requirement_id: str
    bidder_evidence_ref: str
    state: ComparisonState
    confidence: float
    explanation: str
    model_version: str
    prompt_version: str


@dataclass(frozen=True, slots=True)
class EvidenceResult:
    source: str
    subject_identifier: str
    attribute: str
    value: Any
    status: EvidenceStatus
    reference: str


@dataclass(frozen=True, slots=True)
class TenderRule:
    id: str
    rule_set_version: str
    requirement_id: str
    required_field: str
    severity: Severity
    weight: int
    portal_source: str | None = None
    portal_attribute: str | None = None
    portal_expected_value: str | bool | int | float | None = None
    minimum_extraction_confidence: float = 0.80
    minimum_retrieval_similarity: float = 0.75
    minimum_comparison_confidence: float = 0.80


@dataclass(frozen=True, slots=True)
class VerificationInput:
    case_id: str
    verification_run_id: str
    rules: tuple[TenderRule, ...]
    extracted_fields: tuple[ExtractedField, ...]
    retrieval_candidates: tuple[RetrievalCandidate, ...]
    comparisons: tuple[ComparisonResult, ...]
    portal_evidence: tuple[EvidenceResult, ...] = ()


@dataclass(frozen=True, slots=True)
class Finding:
    case_id: str
    verification_run_id: str
    rule_id: str
    rule_set_version: str
    status: FindingStatus
    severity: Severity
    explanation: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    findings: tuple[Finding, ...]
    score: int
    risk: RiskLevel
    recommendation: Recommendation
