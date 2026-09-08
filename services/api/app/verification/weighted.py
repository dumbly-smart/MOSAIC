"""Tender-sourced v2 scoring. Missing evidence and model uncertainty earn no credit."""

from datetime import date
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
    for field in ("id", "clause", "field", "tender_id", "rule_version"):
        if not nonempty(c.get(field)):
            raise ValueError(f"Invalid criterion {field}")
    validate_source(c.get("source"))
    if not number(c.get("weight")) or not 0 < c["weight"] <= 100:
        raise ValueError("Invalid quota")
    value_type = c.get("value_type", "numeric")
    operator = c.get("operator")
    if value_type == "numeric" and not nonempty(c.get("unit")):
        raise ValueError("Numeric criteria require a unit")
    if value_type == "numeric" and operator == "range":
        validate_bounds(c.get("bounds"))
        if "threshold" in c:
            raise ValueError("Range criteria cannot also specify a threshold")
    elif value_type == "numeric" and operator in (">=", "<=", "=="):
        if not number(c.get("threshold")) or "bounds" in c:
            raise ValueError("A numeric threshold is required without range bounds")
    elif (
        value_type == "boolean"
        and operator == "=="
        and type(c.get("expected")) is bool
        or value_type == "document_presence"
        and operator == "=="
        and c.get("expected") is True
        or value_type == "categorical"
        and operator == "=="
        and nonempty(c.get("expected"))
    ):
        pass
    elif value_type == "categorical" and operator == "one_of":
        expected = c.get("expected")
        if (
            not isinstance(expected, list)
            or not expected
            or any(not nonempty(item) for item in expected)
            or len({item.casefold() for item in expected}) != len(expected)
        ):
            raise ValueError("Categorical one_of requires unique nonempty values")
    elif value_type == "date" and operator in (">=", "<=", "=="):
        try:
            date.fromisoformat(c.get("expected", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError("Date criteria require an ISO YYYY-MM-DD expected value") from exc
    else:
        raise ValueError("Unsupported value type or operator")
    if c.get("fallback") is not None:
        if value_type != "numeric":
            raise ValueError("Fallback ranges are supported only for numeric criteria")
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
            "value_type",
            "operator",
            "threshold",
            "bounds",
            "expected",
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
    value_type = c.get("value_type", "numeric")
    valid = (
        isinstance(evidence, dict)
        and type(evidence.get("uncertain")) is bool
        and nonempty(evidence.get("source_quote"))
        and nonempty(evidence.get("document_id"))
        and any(type(evidence.get(k)) is int and evidence[k] > 0 for k in ("line", "page"))
    )
    value = evidence.get("value") if isinstance(evidence, dict) else None
    if value_type == "numeric":
        valid = valid and number(value) and evidence.get("unit") == c["unit"]
    elif value_type in ("boolean", "document_presence"):
        valid = valid and type(value) is bool
    elif value_type == "categorical":
        valid = valid and nonempty(value)
    elif value_type == "date":
        try:
            value = date.fromisoformat(value)
        except (TypeError, ValueError):
            valid = False
    if not valid or evidence["uncertain"]:
        return dict(
            result,
            reason_code="evidence_unreliable",
            reason="Evidence is uncertain, conflicting, invalid, or lacks usable provenance.",
        )
    if value_type == "numeric":
        numeric_value = Decimal(str(evidence["value"]))
        if c["operator"] == "range":
            passed = in_range(numeric_value, c["bounds"])
        else:
            threshold = Decimal(str(c["threshold"]))
            passed = {
                ">=": numeric_value >= threshold,
                "<=": numeric_value <= threshold,
                "==": numeric_value == threshold,
            }[c["operator"]]
    elif value_type in ("boolean", "document_presence"):
        passed = evidence["value"] is c["expected"]
    elif value_type == "categorical":
        actual = evidence["value"].casefold()
        expected = c["expected"]
        passed = (
            actual == expected.casefold()
            if c["operator"] == "=="
            else actual in {item.casefold() for item in expected}
        )
    else:
        expected_date = date.fromisoformat(c["expected"])
        passed = {
            ">=": value >= expected_date,
            "<=": value <= expected_date,
            "==": value == expected_date,
        }[c["operator"]]
    if passed:
        return dict(
            result,
            status="passed",
            reason_code="requirement_met",
            earned_points=c["weight"],
            review_required=False,
            reason="Primary requirement met.",
        )
    if c.get("fallback") and in_range(numeric_value, c["fallback"]["bounds"]):
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
