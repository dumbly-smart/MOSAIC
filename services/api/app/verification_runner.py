"""Run the complete local verification pipeline for documents stored in Supabase."""

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from .verification.document_pipeline import BgeM3, PgStore, chunks, qwen_compare
from .verification.local_workflow import finalize_report, verify_locally
from .verification.pdf_extraction import extract_document, require_complete
from .verification.tender_extraction import extract_criteria
from .verification.weighted import POLICY


class PgVectorIndex:
    def __init__(self, store, corpus_id, embedder):
        self.store = store
        self.corpus_id = corpus_id
        self.metadata = {
            "provider": embedder.provider,
            "model": embedder.name,
            "dimension": embedder.dimension,
        }
        self.model = embedder.name

    def search(self, query, top_k=5):
        return self.store.search(self.corpus_id, self.model, query, top_k)


class LocalVerificationRunner:
    """Synchronous worker body; FastAPI schedules it outside the request response."""

    def __init__(self, storage, database_url):
        self.storage = storage
        self.database_url = database_url

    def run(self, documents, *, force_ocr_bidder=False, top_k=5):
        tenders = [item for item in documents if item["kind"] == "tender"]
        bidders = [item for item in documents if item["kind"] == "bidder"]
        if len(tenders) != 1 or not bidders:
            raise ValueError("A run requires exactly one tender PDF and at least one bidder PDF")
        with tempfile.TemporaryDirectory(prefix="mosaic-verification-") as folder:
            workspace = Path(folder)
            tender_pdf = workspace / "tender.pdf"
            tender_pdf.write_bytes(self.storage.download(tenders[0]["object_path"]))
            bidder_sources = []
            for number, document in enumerate(bidders, 1):
                path = workspace / f"bidder-{number}.pdf"
                path.write_bytes(self.storage.download(document["object_path"]))
                bidder_sources.append(path)
            bidder_pdf = self._merge_bidders(bidder_sources, workspace / "bidder-package.pdf")

            tender_records = extract_document(
                tender_pdf, workspace / "tender-extraction.json", batch_size=10
            )
            require_complete(tender_records)
            criteria_document = extract_criteria(
                tender_records,
                tender_pdf,
                checkpoint=workspace / "criteria.checkpoint.json",
            )
            bidder_records = extract_document(
                bidder_pdf,
                workspace / "bidder-extraction.json",
                batch_size=10,
                force_ocr=force_ocr_bidder,
            )
            require_complete(bidder_records)
            pieces = chunks(bidder_records["records"])
            embedder = BgeM3()
            corpus_id = hashlib.sha256(
                json.dumps(pieces, sort_keys=True).encode("utf-8")
            ).hexdigest()
            store = PgStore(self.database_url)
            try:
                store.index(
                    corpus_id,
                    embedder.name,
                    pieces,
                    embedder.encode_documents([piece["text"] for piece in pieces]),
                )
                index = PgVectorIndex(store, corpus_id, embedder)
                report = self._verify(
                    criteria_document,
                    index,
                    embedder,
                    bidder_pdf,
                    top_k,
                    corpus_id,
                    started=time.perf_counter(),
                )
            finally:
                store.close()
            return criteria_document, report

    @staticmethod
    def _verify(criteria_document, index, embedder, bidder_pdf, top_k, corpus_id, *, started):
        report = {
            "mode": "supabase-fastapi-verification",
            "scoring_policy": POLICY,
            "criteria_version": criteria_document["version"],
            "score": 0,
            "results": [],
            "review_required": True,
            "recommendation": "manual_review",
            "components": {
                "extraction": "Docling+RapidOCR",
                "embedding_provider": embedder.provider,
                "embedding": embedder.name,
                "vector_store": "Supabase PostgreSQL+pgvector",
                "comparator": os.environ.get("MOSAIC_QWEN_MODEL", "qwen3-vl:4b-instruct"),
                "top_k": top_k,
                "corpus_id": corpus_id,
            },
        }
        report["results"].extend(
            verify_locally(
                criteria_document["criteria"],
                index,
                embedder,
                qwen_compare,
                pdf_path=bidder_pdf,
                top_k=top_k,
            )
        )
        finalize_report(report)
        report["seconds"] = time.perf_counter() - started
        return report

    @staticmethod
    def _merge_bidders(paths, output):
        if len(paths) == 1:
            return paths[0]
        writer = PdfWriter()
        for path in paths:
            reader = PdfReader(path)
            if reader.is_encrypted:
                raise ValueError("Password-protected bidder PDFs are not supported")
            for page in reader.pages:
                writer.add_page(page)
        with output.open("wb") as stream:
            writer.write(stream)
        return output
