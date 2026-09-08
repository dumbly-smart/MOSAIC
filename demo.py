"""Run synthetic evidence through the real local verification engine.

Usage: python demo.py --scenario all
There are no model calls, database connections, or external portal requests.
"""

import argparse
import json
from dataclasses import asdict, replace

from services.api.app.domain import (
    ComparisonResult,
    ComparisonState,
    EvidenceResult,
    EvidenceStatus,
    ExtractedField,
    RetrievalCandidate,
    Severity,
    TenderRule,
    VerificationInput,
)
from services.api.app.verification import VerificationEngine

SCENARIOS = (
    "compliant",
    "missing-document",
    "low-confidence",
    "weak-match",
    "identity-mismatch",
    "portal-unavailable",
    "inactive-registration",
    "conflicting-evidence",
    "debarment-hit",
)


def scenario_input(name: str) -> VerificationInput:
    """Create a fresh synthetic request; never read actual bidder documents."""
    if name not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {name}")
    field = ExtractedField(
        "FIELD-DEMO",
        "DOC-DEMO",
        "gst_registration_number",
        "SYNTHETIC-GST-001",
        0.96,
        "DOC-DEMO#page=1",
        page_number=1,
        extraction_method="synthetic_fixture",
    )
    rule = TenderRule(
        "GST-ACTIVE-01",
        "demo-v1",
        "REQ-GST",
        field.name,
        Severity.HIGH,
        100,
        portal_source="mock_gst_sandbox",
        portal_attribute="registration_status",
        portal_expected_value="active",
    )
    candidate = RetrievalCandidate(rule.requirement_id, field.evidence_ref, 0.91, 1)
    comparison = ComparisonResult(
        rule.requirement_id,
        field.evidence_ref,
        ComparisonState.MATCH,
        0.94,
        "Synthetic certificate supplies the required identifier.",
        "qwen3-vl-test-double",
        "comparison-demo-v1",
    )
    portal = EvidenceResult(
        "mock_gst_sandbox",
        field.normalized_value,
        "registration_status",
        "active",
        EvidenceStatus.VERIFIED,
        "mock://gst/synthetic-001",
    )
    request = VerificationInput(
        "CASE-DEMO", f"RUN-{name}", (rule,), (field,), (candidate,), (comparison,), (portal,)
    )
    if name == "missing-document":
        return replace(
            request,
            extracted_fields=(),
            retrieval_candidates=(),
            comparisons=(),
            portal_evidence=(),
        )
    if name == "low-confidence":
        return replace(request, extracted_fields=(replace(field, confidence=0.4),))
    if name == "weak-match":
        return replace(request, retrieval_candidates=(replace(candidate, similarity_score=0.3),))
    if name == "identity-mismatch":
        return replace(
            request, portal_evidence=(replace(portal, status=EvidenceStatus.INCONSISTENT),)
        )
    if name == "portal-unavailable":
        return replace(
            request,
            portal_evidence=(replace(portal, status=EvidenceStatus.UNAVAILABLE, value=None),),
        )
    if name == "inactive-registration":
        return replace(request, portal_evidence=(replace(portal, value="inactive"),))
    if name == "conflicting-evidence":
        return replace(
            request,
            comparisons=(
                comparison,
                replace(
                    comparison,
                    state=ComparisonState.MISMATCH,
                    explanation="Another comparison disagrees.",
                ),
            ),
        )
    if name == "debarment-hit":
        return replace(
            request,
            rules=(
                replace(
                    rule,
                    id="DEBARMENT-01",
                    severity=Severity.CRITICAL,
                    portal_source="mock_debarment_sandbox",
                    portal_attribute="debarred",
                    portal_expected_value=False,
                ),
            ),
            portal_evidence=(
                replace(
                    portal,
                    source="mock_debarment_sandbox",
                    attribute="debarred",
                    value=True,
                    reference="mock://debarment/synthetic-001",
                ),
            ),
        )
    return request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=(*SCENARIOS, "all"), default="compliant")
    parser.add_argument("--json", action="store_true", help="Print results as JSON")
    parser.add_argument("--confidence", type=float, help="Override extraction confidence (0 to 1)")
    args = parser.parse_args()
    results = []
    for name in SCENARIOS if args.scenario == "all" else (args.scenario,):
        request = scenario_input(name)
        if args.confidence is not None:
            if not 0 <= args.confidence <= 1:
                parser.error("--confidence must be between 0 and 1")
            request = replace(
                request,
                extracted_fields=tuple(
                    replace(field, confidence=args.confidence) for field in request.extracted_fields
                ),
            )
        outcome = VerificationEngine().evaluate(request)
        results.append({"scenario": name, "synthetic": True, **asdict(outcome)})
    if args.json:
        print(json.dumps(results, indent=2))
        return
    print("MOSAIC LOCAL DEMO | Synthetic evidence; simulated Qwen/retrieval/portal results")
    print("Recommendations are advisory. An officer makes the final decision.")
    for result in results:
        print(f"\n--- {result['scenario']} ---")
        print(f"Score: {result['score']}/100 | Risk: {result['risk']}")
        print(f"Recommendation: {result['recommendation']}")
        for finding in result["findings"]:
            print(f"[{finding['status']}] {finding['rule_id']} ({finding['rule_set_version']})")
            print(f"  {finding['explanation']}")
            print("  Evidence: " + (", ".join(finding["evidence_refs"]) or "No evidence available"))


if __name__ == "__main__":
    main()
