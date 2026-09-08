"""Run each document verification layer independently, with explicit provenance."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import socket
import time
from pathlib import Path

from services.api.app.verification.document_pipeline import (
    BgeM3,
    PgStore,
    baseline_evidence,
    chunks,
    qwen_compare,
    text_records,
)
from services.api.app.verification.embedding_retrieval import (
    LocalVectorIndex,
    build_chunks,
    criterion_query,
    evaluate_retrieval_report,
    make_embedder,
)
from services.api.app.verification.local_workflow import (
    finalize_report,
    resume_state,
    verify_locally,
)
from services.api.app.verification.pdf_extraction import extract_document, require_complete
from services.api.app.verification.tender_extraction import (
    TENDER_PROMPT_VERSION,
    evaluate_criteria_document,
    extract_criteria,
)
from services.api.app.verification.weighted import POLICY, assess, validate_criteria

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(ROOT / ".model-cache" / "huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def doctor():
    result = {"packages": {}, "services": {}}
    for package in (
        "docling",
        "rapidocr",
        "onnxruntime",
        "sentence-transformers",
        "psycopg",
        "pgvector",
    ):
        try:
            result["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][package] = "MISSING"
    for label, port in (("postgres_default", 5432), ("postgres_demo", 55432), ("ollama", 11434)):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                result["services"][label] = "listening (not yet authenticated/tested)"
        except OSError:
            result["services"][label] = "not reachable"
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    generate = sub.add_parser("generate")
    generate.add_argument("--output", default="artifacts/corpus")
    extract = sub.add_parser("extract")
    extract.add_argument("pdf")
    extract.add_argument("--start", type=int, default=1)
    extract.add_argument("--end", type=int, default=None)
    extract.add_argument("--batch-size", type=int, default=25)
    extract.add_argument("--resume", action="store_true")
    extract.add_argument("--force-ocr", action="store_true")
    extract.add_argument("--output", default="artifacts/extracted.json")
    embed = sub.add_parser("embed")
    embed.add_argument("--records", required=True)
    embed.add_argument("--output", default="artifacts/bge-m3-index")
    embed.add_argument("--batch-size", type=int, default=4)
    embed.add_argument("--provider", choices=("ollama", "sentence-transformers"), default="ollama")
    retrieve = sub.add_parser("retrieve")
    retrieve.add_argument("--index", required=True)
    retrieve.add_argument("--criteria", default=str(ROOT / "criteria.json"))
    retrieve.add_argument("--top-k", type=int, default=10)
    retrieve.add_argument("--output", default="artifacts/retrieval-report.json")
    retrieval_eval = sub.add_parser("evaluate-retrieval")
    retrieval_eval.add_argument("--report", required=True)
    retrieval_eval.add_argument("--expected", required=True)
    retrieval_eval.add_argument("--output", default="artifacts/retrieval-evaluation.json")
    local_verify = sub.add_parser("verify-local")
    local_verify.add_argument("--index", required=True)
    local_verify.add_argument("--criteria", default=str(ROOT / "criteria.json"))
    local_verify.add_argument("--pdf", help="Original PDF for Qwen visual comparison")
    local_verify.add_argument("--top-k", type=int, default=5)
    local_verify.add_argument("--output", default="artifacts/verify-local-v2-report.json")
    local_verify.add_argument("--resume", action="store_true")
    tender = sub.add_parser("extract-criteria")
    tender.add_argument("--records", required=True)
    tender.add_argument("--pdf", required=True)
    tender.add_argument("--output", default="artifacts/extracted-criteria.json")
    tender.add_argument("--resume", action="store_true")
    tender_eval = sub.add_parser("evaluate-criteria")
    tender_eval.add_argument("--criteria", required=True)
    tender_eval.add_argument("--expected", required=True)
    tender_eval.add_argument("--output", default="artifacts/criteria-evaluation.json")
    for command in ("baseline", "verify"):
        run = sub.add_parser(command)
        source = run.add_mutually_exclusive_group(required=True)
        source.add_argument("--text")
        source.add_argument("--records")
        run.add_argument("--criteria", default=str(ROOT / "criteria.json"))
        run.add_argument("--output", default=f"artifacts/{command}-v2-report.json")
        if command == "verify":
            run.add_argument("--pdf", help="Original PDF for Qwen visual comparison")
            run.add_argument("--top-k", type=int, default=5)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--report", required=True)
    evaluate.add_argument("--expected", required=True)
    args = parser.parse_args()
    if args.command == "doctor":
        doctor()
        return
    if args.command == "generate":
        from services.api.app.verification.fabricate import build

        print(build(Path(args.output)))
        return
    if args.command == "extract":
        report = extract_document(
            args.pdf,
            args.output,
            args.start,
            args.end,
            batch_size=args.batch_size,
            resume=args.resume,
            force_ocr=args.force_ocr,
            progress=lambda message: print(message, flush=True),
        )
        print(
            f"Extraction status: {report['status']} | {len(report['records'])} lines | {args.output}"
        )
        if report["status"] in ("incomplete", "needs_review"):
            raise SystemExit(2)
        return
    if args.command == "embed":
        extracted = load(args.records)
        require_complete(extracted)
        pieces = build_chunks(extracted["records"])
        embedder = make_embedder(args.provider)
        index = LocalVectorIndex.build(
            pieces,
            embedder,
            args.output,
            batch_size=args.batch_size,
            progress=lambda message: print(message, flush=True),
        )
        print(f"Index complete | {len(index.chunks)} chunks | {args.output}")
        return
    if args.command == "retrieve":
        index = LocalVectorIndex.load(args.index)
        criteria_doc = load(args.criteria)
        validate_criteria(criteria_doc["criteria"])
        embedder = make_embedder(index.metadata["provider"])
        if (
            index.metadata["provider"] != embedder.provider
            or index.metadata["model"] != embedder.name
            or index.metadata["dimension"] != embedder.dimension
        ):
            raise ValueError("Index and query embedder are incompatible")
        queries = [criterion_query(c) for c in criteria_doc["criteria"]]
        vectors = embedder.encode_queries(queries)
        results = []
        for criterion, vector in zip(criteria_doc["criteria"], vectors):
            hits = index.search(vector, top_k=args.top_k)
            results.append(
                {
                    "criterion_id": criterion["id"],
                    "query": criterion_query(criterion),
                    "hits": [
                        {
                            k: h[k]
                            for k in (
                                "rank",
                                "similarity",
                                "id",
                                "document_id",
                                "page",
                                "line_start",
                                "line_end",
                                "text",
                                "rows",
                            )
                        }
                        for h in hits
                    ],
                }
            )
        report = {
            "mode": "bge-m3-local-retrieval",
            "provider": embedder.provider,
            "model": embedder.name,
            "criteria_version": criteria_doc["version"],
            "index": index.metadata,
            "top_k": args.top_k,
            "results": results,
            "warning": "Similarity ranks candidates; it does not prove compliance or absence.",
        }
        save(args.output, report)
        print(f"Retrieved {args.top_k} candidates for {len(results)} criteria | {args.output}")
        return
    if args.command == "evaluate-retrieval":
        evaluation = evaluate_retrieval_report(load(args.report), load(args.expected))
        save(args.output, evaluation)
        print(
            f"Evidence recall: {evaluation['criteria_found']}/{evaluation['criteria_total']} "
            f"({evaluation['recall_at_k']:.0%}) | {args.output}"
        )
        if evaluation["recall_at_k"] != 1:
            raise SystemExit(1)
        return
    if args.command == "verify-local":
        output_exists = Path(args.output).exists()
        if output_exists and not args.resume:
            raise ValueError("Refusing to overwrite a verification report; choose a new output")
        index = LocalVectorIndex.load(args.index)
        criteria_doc = load(args.criteria)
        criteria = criteria_doc["criteria"]
        validate_criteria(criteria)
        if args.pdf:
            from services.api.app.verification.document_pipeline import document_id

            if {chunk["document_id"] for chunk in index.chunks} != {document_id(args.pdf)}:
                raise ValueError("PDF does not match the indexed source document")
        embedder = make_embedder(index.metadata["provider"])
        components = {
            "embedding_provider": embedder.provider,
            "embedding": embedder.name,
            "vector_store": "persisted local exact-cosine test index",
            "comparator": os.environ.get("MOSAIC_QWEN_MODEL", "qwen3-vl:4b-instruct"),
            "vision_enabled": bool(args.pdf),
            "vision_strategy": "native text with image fallback for scanned pages",
            "corpus_id": index.metadata["corpus_id"],
            "top_k": args.top_k,
        }
        template = {
            "mode": "verify-local",
            "scoring_policy": POLICY,
            "criteria_version": criteria_doc["version"],
            "score": 0,
            "results": [],
            "review_required": True,
            "recommendation": "manual_review",
            "components": components,
        }
        report = load(args.output) if output_exists else template
        pending, elapsed_before = resume_state(template, report, criteria, POLICY)
        if not pending:
            print(f"Verification report is already complete | {args.output}")
            return
        started = time.perf_counter()
        for row in verify_locally(
            pending,
            index,
            embedder,
            qwen_compare,
            pdf_path=args.pdf,
            top_k=args.top_k,
        ):
            report["results"].append(row)
            finalize_report(report)
            report["seconds"] = elapsed_before + time.perf_counter() - started
            save(args.output, report)
            print(
                f"{row['criterion_id']}: {row['status']} | "
                f"{row['earned_points']}/{row['quota']} points",
                flush=True,
            )
        finalize_report(report)
        report["seconds"] = elapsed_before + time.perf_counter() - started
        save(args.output, report)
        print(
            f"Local verification complete | Score: {report['score']}/100 | "
            f"Advisory: {report['recommendation']} | {args.output}"
        )
        return
    if args.command == "extract-criteria":
        if Path(args.output).exists() and not args.resume:
            raise ValueError("Refusing to overwrite extracted criteria; choose a new output")
        if Path(args.output).exists():
            existing = load(args.output)
            source = load(args.records)
            validate_criteria(existing.get("criteria"))
            metadata = existing.get("tender_document", {})
            if (
                metadata.get("document_id") != source.get("document_id")
                or metadata.get("extraction_model")
                != os.environ.get("MOSAIC_QWEN_MODEL", "qwen3-vl:4b-instruct")
                or metadata.get("prompt_version") != TENDER_PROMPT_VERSION
            ):
                raise ValueError("Saved criteria use a different tender, model, or prompt")
            print(f"Tender criteria are already complete | {args.output}")
            return
        criteria_document = extract_criteria(
            load(args.records),
            args.pdf,
            checkpoint=args.output + ".checkpoint.json",
            resume=args.resume,
            progress=lambda message: print(message, flush=True),
        )
        save(args.output, criteria_document)
        print(
            f"Tender criteria complete | {len(criteria_document['criteria'])} criteria | "
            f"{args.output}"
        )
        return
    if args.command == "evaluate-criteria":
        evaluation = evaluate_criteria_document(load(args.criteria), load(args.expected))
        save(args.output, evaluation)
        print(f"Tender criteria correct: {evaluation['all_correct']} | {args.output}")
        if not evaluation["all_correct"]:
            raise SystemExit(1)
        return
    if args.command == "evaluate":
        report, expected = load(args.report), load(args.expected)
        if report.get("scoring_policy") != expected.get("scoring_policy") or report.get(
            "criteria_version"
        ) != expected.get("criteria_version"):
            raise ValueError("Report and answer key policy/rule versions do not match")
        found = {r["criterion_id"]: r for r in report["results"]}
        matches = []
        for truth in expected["criteria"]:
            got = found.get(truth["criterion_id"], {})
            evidence = got.get("evidence") or {}
            matches.append(
                {
                    "criterion_id": truth["criterion_id"],
                    "status_correct": got.get("status") == truth["status"],
                    "value_correct": evidence.get("value") == truth["value"],
                    "quote_correct": evidence.get("source_quote") == truth["quote"],
                    "page_correct": evidence.get("page") == truth["page"],
                    "points_correct": got.get("earned_points") == truth["earned_points"],
                }
            )
        print(
            json.dumps(
                {
                    "mode": report["mode"],
                    "checks": matches,
                    "expected_score": expected["expected_score"],
                    "actual_score": report["score"],
                },
                indent=2,
            )
        )
        if report["score"] != expected["expected_score"] or not all(
            all(v for k, v in match.items() if k != "criterion_id") for match in matches
        ):
            raise SystemExit(1)
        return
    criteria_doc = load(args.criteria)
    if Path(args.output).exists() and load(args.output).get("scoring_policy") != POLICY:
        raise ValueError("Refusing to overwrite a historical report; choose a new output path")
    criteria = criteria_doc["criteria"]
    validate_criteria(criteria)
    if args.text:
        rows = text_records(args.text)
    else:
        extracted = load(args.records)
        require_complete(extracted)
        rows = extracted["records"]
    if not rows and args.command != "baseline":
        raise ValueError("No extracted evidence to process")
    if args.command == "verify" and args.pdf:
        from services.api.app.verification.document_pipeline import document_id

        if {row["document_id"] for row in rows} != {document_id(args.pdf)}:
            raise ValueError("PDF does not match extracted source document")
    started, results = time.perf_counter(), []
    report = {
        "mode": args.command,
        "scoring_policy": POLICY,
        "criteria_version": criteria_doc["version"],
        "score": 0,
        "results": results,
        "review_required": True,
        "recommendation": "manual_review",
    }
    if args.command == "baseline":
        report["components"] = {
            "extraction": "plain text" if args.text else "saved extraction",
            "retrieval": "literal-label baseline",
            "comparison": "regex baseline",
        }
        for criterion in criteria:
            try:
                row = assess(criterion, baseline_evidence(criterion, rows))
            except ValueError:
                row = assess(criterion, None, processing_error=True)
                row.update(
                    reason_code="evidence_unreliable",
                    reason="Multiple or malformed baseline values require review.",
                )
            results.append(row)
    else:
        dsn = os.environ.get("MOSAIC_DATABASE_URL")
        if not dsn:
            raise ValueError("Set MOSAIC_DATABASE_URL to the dedicated pgvector benchmark database")
        store = PgStore(dsn)
        try:
            embedder = BgeM3()
            pieces = chunks(rows)
            corpus_id = hashlib.sha256(json.dumps(pieces, sort_keys=True).encode()).hexdigest()
            store.index(
                corpus_id,
                embedder.name,
                pieces,
                embedder.encode_documents([c["text"] for c in pieces]),
            )
            queries = embedder.encode_queries([criterion_query(c) for c in criteria])
            report["components"] = {
                "embedding_provider": embedder.provider,
                "embedding": embedder.name,
                "vector_store": "PostgreSQL+pgvector",
                "comparator": os.environ.get("MOSAIC_QWEN_MODEL", "qwen3-vl:4b-instruct"),
                "vision_enabled": bool(args.pdf),
                "vision_strategy": "native text with image fallback for scanned pages",
                "corpus_id": corpus_id,
            }
            for criterion, query in zip(criteria, queries):
                candidates = store.search(corpus_id, embedder.name, query, args.top_k)
                try:
                    evidence, raw = qwen_compare(criterion, candidates, args.pdf)
                    row = assess(criterion, evidence)
                    row["model_response"] = raw
                except (ValueError, OSError, KeyError) as exc:
                    row = assess(criterion, None, processing_error=True)
                    row.update(
                        reason=type(exc).__name__
                        + ": model response unavailable or failed grounding validation",
                    )
                row["retrieval"] = [
                    {k: c[k] for k in ("id", "similarity", "page", "line_start", "line_end")}
                    for c in candidates
                ]
                results.append(row)
                save(args.output, report)
        finally:
            store.close()
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
        if any(r["status"] == "failed" for r in results)
        else "qualify"
    )
    report["seconds"] = time.perf_counter() - started
    save(args.output, report)
    print(
        f"Mode: {report['mode']} | Score: {report['score']}/100 | Advisory: {report['recommendation']}"
    )
    for row in results:
        evidence = row["evidence"] or {}
        print(f"\n{row['criterion_id']}: {row['clause']}")
        print(f"  {row['status']}: {row['earned_points']}/{row['quota']} points")
        print(f"  Reason: {row['reason_code']} | {row['reason']}")
        print(f"  Document value: {evidence.get('value')} {evidence.get('unit', '')}")
        print(f"  Line: {evidence.get('line')} | Page: {evidence.get('page')}")
        print(f"  Quote: {evidence.get('source_quote', 'No reliable source')}")
    print(f"\nSaved {args.output}")


if __name__ == "__main__":
    main()
