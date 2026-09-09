"""Local BGE-M3 -> Qwen -> deterministic-scoring workflow without PostgreSQL."""

from .embedding_retrieval import criterion_query
from .weighted import assess


def resume_state(template, report, criteria, policy):
    """Validate a checkpoint and return its pending criterion suffix and elapsed time."""
    results = report.get("results")
    if not isinstance(results, list) or any(not isinstance(row, dict) for row in results):
        raise ValueError("Saved report has invalid results")
    expected_ids = [criterion["id"] for criterion in criteria]
    completed_ids = [row.get("criterion_id") for row in results]
    if (
        any(
            report.get(key) != template[key]
            for key in ("mode", "scoring_policy", "criteria_version", "components")
        )
        or completed_ids != expected_ids[: len(completed_ids)]
        or any(row.get("policy_version") != policy for row in results)
    ):
        raise ValueError("Saved report is incompatible with this verification run")
    elapsed = report.get("seconds", 0)
    if type(elapsed) not in (int, float) or elapsed < 0:
        raise ValueError("Saved report has invalid elapsed time")
    return criteria[len(completed_ids) :], elapsed


def verify_locally(criteria, index, embedder, compare, *, pdf_path=None, top_k=5):
    """Yield one fail-closed scored finding per criterion."""
    metadata = index.metadata
    if (
        metadata.get("provider") != embedder.provider
        or metadata.get("model") != embedder.name
        or metadata.get("dimension") != embedder.dimension
    ):
        raise ValueError("Index and query embedder are incompatible")
    queries = embedder.encode_queries([criterion_query(criterion) for criterion in criteria])
    for criterion, query in zip(criteria, queries):
        candidates = index.search(query, top_k=top_k)
        try:
            evidence, raw = compare(criterion, candidates, pdf_path)
            row = assess(criterion, evidence)
            row["model_response"] = raw
        except (ValueError, OSError, KeyError) as exc:
            row = assess(criterion, None, processing_error=True)
            row.update(
                reason=type(exc).__name__
                + ": model response unavailable or failed grounding validation"
            )
        row["retrieval"] = [
            {
                key: candidate[key]
                for key in (
                    "id",
                    "rank",
                    "similarity",
                    "page",
                    "line_start",
                    "line_end",
                )
            }
            for candidate in candidates
        ]
        yield row


def finalize_report(report):
    """Finalize advisory totals without turning them into an officer decision."""
    results = report["results"]
    report["score"] = sum(row["earned_points"] for row in results)
    report["review_required"] = any(row["review_required"] for row in results)
    report["clarification_required"] = any(row["clarification_required"] for row in results)
    report["unresolved_criteria"] = [
        row["criterion_id"] for row in results if row["review_required"]
    ]
    report["recommendation"] = (
        "manual_review"
        if report["review_required"]
        else "request_clarification"
        if any(row["status"] == "failed" for row in results)
        else "qualify"
    )
    return report
