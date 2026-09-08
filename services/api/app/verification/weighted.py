"""Tender-sourced v2 scoring. Missing evidence and model uncertainty earn no credit."""

from decimal import Decimal
from math import isfinite

POLICY = "tender-evidence-quota-v2"


def number(value):
    return type(value) in (int, float) and isfinite(value)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_source(source):
    if not isinstance(source, dict) or not all(
        nonempty(source.get(k)) for k in ("clause", "reference")
    ):
        raise ValueError("A source clause and reference are required")


def validate_bounds(bounds):
    if not isinstance(bounds, dict) or not all(number(bounds.get(k)) for k in ("lower", "upper")):
        raise ValueError("Finite lower and upper bounds are required")
    if not all(type(bounds.get(k)) is bool for k in ("lower_inclusive", "upper_inclusive")):
        raise ValueError("Explicit endpoint inclusivity is required")
    if bounds["lower"] > bounds["upper"] or (
        bounds["lower"] == bounds["upper"]
        and not (bounds["lower_inclusive"] and bounds["upper_inclusive"])
    ):
        raise ValueError("Range is reversed or empty")


def validate_rule(c):
    if not isinstance(c, dict):
        raise ValueError("Criterion must be an object")  # noqa: TRY004
    if "tolerance_percent" in c:
        raise ValueError("Legacy tolerance is unsupported; supply a sourced fallback range")
    for field in ("id", "clause", "field", "unit", "tender_id", "rule_version"):
        if not nonempty(c.get(field)):
            raise ValueError(f"Invalid criterion {field}")
    validate_source(c.get("source"))
    if not number(c.get("weight")) or not 0 < c["weight"] <= 100:
        raise ValueError("Invalid quota")
    if c.get("operator") == "range":
        validate_bounds(c.get("bounds"))
        if "threshold" in c:
            raise ValueError("Range criteria cannot also specify a threshold")
    elif c.get("operator") in (">=", "<=", "=="):
        if not number(c.get("threshold")) or "bounds" in c:
            raise ValueError("A numeric threshold is required without range bounds")
    else:
        raise ValueError("Unsupported operator")
    if c.get("fallback") is not None:
        f = c["fallback"]
        if not isinstance(f, dict):
            raise ValueError("Fallback must be an object")
        validate_bounds(f.get("bounds"))
        validate_source(f.get("source"))


def validate_criteria(criteria):
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("Criteria must be a nonempty list")
    for c in criteria:
        validate_rule(c)
    if len({c["id"] for c in criteria}) != len(criteria):
        raise ValueError("Criteria IDs must be unique")
    if sum(Decimal(str(c["weight"])) for c in criteria) != 100:
        raise ValueError("Criterion quotas must sum to exactly 100")


def in_range(value, bounds):
    lower, upper = Decimal(str(bounds["lower"])), Decimal(str(bounds["upper"]))
    return (value >= lower if bounds["lower_inclusive"] else value > lower) and (
        value <= upper if bounds["upper_inclusive"] else value < upper
    )


def assess(c, evidence, *, processing_error=False):
    c = c if isinstance(c, dict) else {}
    result = {
        key: c.get(key)
        for key in (
            "clause",
            "operator",
            "threshold",
            "bounds",
            "unit",
            "tender_id",
            "rule_version",
            "source",
            "fallback",
        )
    }
    result.update(
        policy_version=POLICY,
        criterion_id=c.get("id"),
        quota=c.get("weight"),
        evidence=evidence,
        status="manual_review",
        earned_points=0,
        review_required=True,
        clarification_required=False,
        reason_code="processing_or_rule_error",
        reason="Criterion or processing needs review.",
    )
    try:
        validate_rule(c)
    except ValueError as exc:
        return dict(result, reason=str(exc))
    if processing_error:
        return dict(result, reason="Processing was unavailable, incomplete, or invalid.")
    if evidence is None:
        return dict(
            result,
            status="unsure",
            reason_code="missing_information",
            clarification_required=True,
            reason="Required information was not found; awaiting clarification.",
        )
    valid = (
        isinstance(evidence, dict)
        and number(evidence.get("value"))
        and (
            evidence.get("unit") == c["unit"]
            and type(evidence.get("uncertain")) is bool
            and nonempty(evidence.get("source_quote"))
            and nonempty(evidence.get("document_id"))
            and any(type(evidence.get(k)) is int and evidence[k] > 0 for k in ("line", "page"))
        )
    )
    if not valid or evidence["uncertain"]:
        return dict(
            result,
            reason_code="evidence_unreliable",
            reason="Evidence is uncertain, conflicting, invalid, or lacks usable provenance.",
        )
    value = Decimal(str(evidence["value"]))
    if c["operator"] == "range":
        passed = in_range(value, c["bounds"])
    else:
        threshold = Decimal(str(c["threshold"]))
        passed = {">=": value >= threshold, "<=": value <= threshold, "==": value == threshold}[
            c["operator"]
        ]
    if passed:
        return dict(
            result,
            status="passed",
            reason_code="requirement_met",
            earned_points=c["weight"],
            review_required=False,
            reason="Primary requirement met.",
        )
    if c.get("fallback") and in_range(value, c["fallback"]["bounds"]):
        return dict(
            result,
            status="unsure",
            reason_code="explicit_fallback_range",
            earned_points=float(Decimal(str(c["weight"])) / 2),
            reason="Within an explicitly sourced fallback/review range; half credit pending review.",
        )
    return dict(
        result,
        status="failed",
        reason_code="requirement_not_met",
        review_required=False,
        reason="Requirement not met; no applicable fallback range.",
    )
