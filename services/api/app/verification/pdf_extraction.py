"""Bounded, resumable Docling/RapidOCR extraction with explicit page coverage."""

import hashlib
import importlib.metadata
import json
import os
import time
from pathlib import Path

EXTRACTOR_VERSION = "docling-rapidocr-pages-v2"


def inspect_pdf(path, max_mb=100, max_pages=5000):
    import pymupdf

    path = Path(path)
    if path.suffix.lower() != ".pdf" or not path.is_file():
        raise ValueError("Supply an existing .pdf file")
    size = path.stat().st_size
    if not 0 < size <= max_mb * 1024 * 1024:
        raise ValueError(f"PDF exceeds the {max_mb} MB intake limit or is empty")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        if not stream.read(1024).lstrip().startswith(b"%PDF-"):
            raise ValueError("File does not have a PDF header")
        stream.seek(0)
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    try:
        with pymupdf.open(path) as pdf:
            if pdf.needs_pass:
                raise ValueError("Password-protected PDF: supply an authorized unlocked copy")
            if not 0 < pdf.page_count <= max_pages:
                raise ValueError(f"PDF must contain 1 to {max_pages} pages")
            return {
                "document_id": digest.hexdigest(),
                "page_count": pdf.page_count,
                "size_bytes": size,
                "warnings": ["PDF required structural repair"] if pdf.is_repaired else [],
            }
    except RuntimeError as exc:
        raise ValueError("PDF is damaged or cannot be opened") from exc


def atomic_save(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class DoclingBatch:
    def __init__(self, force_ocr=False):
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import OcrMode, PdfPipelineOptions, RapidOcrOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        options = PdfPipelineOptions()
        options.do_ocr = True
        options.do_table_structure = True
        options.document_timeout = 600
        options.ocr_options = RapidOcrOptions(
            backend="onnxruntime", mode=OcrMode.FULL_PAGE if force_ocr else OcrMode.DEFAULT
        )
        self.converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        )

    def __call__(self, path, start, end):
        result = self.converter.convert(Path(path), page_range=(start, end))
        if result.status.value != "success":
            raise RuntimeError(f"Docling conversion status: {result.status.value}")
        rows, warnings = [], []
        for item, _ in result.document.iterate_items():
            kind = getattr(item, "label", "text")
            kind = getattr(kind, "value", str(kind))
            text = getattr(item, "text", None)
            if kind == "table":
                text = item.export_to_markdown(doc=result.document)
            if not text:
                continue
            provenance = getattr(item, "prov", [])
            if len(provenance) != 1 or not start <= provenance[0].page_no <= end:
                warnings.append(
                    {
                        "pages": [p.page_no for p in provenance if start <= p.page_no <= end]
                        or list(range(start, end + 1)),
                        "reason": "Item has missing, multiple, or out-of-range provenance",
                        "kind": kind,
                        "text": text,
                        "provenance": [p.model_dump(mode="json") for p in provenance],
                    }
                )
                continue
            prov = provenance[0]
            for line in text.splitlines():
                if line.strip():
                    rows.append(
                        {
                            "page": prov.page_no,
                            "text": line,
                            "kind": kind,
                            "bbox": prov.bbox.model_dump(mode="json"),
                            "location_precision": "item_bbox",
                            "item_reference": str(getattr(item, "self_ref", "")),
                        }
                    )
        return {"records": rows, "warnings": warnings}


def refresh(report):
    rows = []
    for page in report["pages"]:
        for row in page["records"]:
            rows.append(
                dict(
                    row,
                    line=len(rows) + 1,
                    document_id=report["document_id"],
                    method="docling_rapidocr",
                )
            )
    report["records"] = rows
    report["failed_pages"] = [p["page"] for p in report["pages"] if p["status"] == "failed"]
    report["pending_pages"] = [p["page"] for p in report["pages"] if p["status"] == "pending"]
    report["review_pages"] = [p["page"] for p in report["pages"] if p["status"] == "needs_review"]
    report["processed_pages"] = sum(
        p["status"] in ("extracted", "needs_review") for p in report["pages"]
    )
    whole = report["page_range"] == [1, report["page_count"]]
    if report["failed_pages"] or report["pending_pages"]:
        report["status"] = "incomplete"
    elif report["review_pages"] or report["document_warnings"]:
        report["status"] = "needs_review"
    else:
        report["status"] = "complete" if whole else "partial"
    report["complete_document"] = report["status"] == "complete"


def require_complete(report):
    if report.get("extractor_version") != EXTRACTOR_VERSION or not report.get("complete_document"):
        raise ValueError(
            "Extraction is incomplete, partial, legacy, or needs review; do not score it as a complete document"
        )
    if report.get("page_range") != [1, report.get("page_count")] or len(
        report.get("pages", [])
    ) != report.get("page_count"):
        raise ValueError("Extraction page coverage is inconsistent")
    if [p.get("page") for p in report["pages"]] != list(range(1, report["page_count"] + 1)):
        raise ValueError("Extraction contains missing, duplicate, or misordered page identifiers")
    if any(
        p.get("status") != "extracted" or not p.get("records") or p.get("warnings")
        for p in report["pages"]
    ):
        raise ValueError("Not every page was successfully extracted")
    if report.get("document_warnings") or report.get("status") != "complete":
        raise ValueError("Extraction has unresolved document warnings")


def extract_document(
    path,
    output,
    start_page=1,
    end_page=None,
    batch_size=25,
    resume=False,
    force_ocr=False,
    convert_batch=None,
    progress=None,
):
    if type(batch_size) is not int or not 1 <= batch_size <= 100:
        raise ValueError("Batch size must be between 1 and 100")
    metadata = inspect_pdf(path)
    end_page = metadata["page_count"] if end_page is None else end_page
    if not 1 <= start_page <= end_page <= metadata["page_count"]:
        raise ValueError("Page range is outside this PDF")
    versions = {}
    for package in ("docling", "rapidocr", "onnxruntime"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "unavailable"
    configuration = {
        "extractor_version": EXTRACTOR_VERSION,
        "force_ocr": force_ocr,
        "page_range": [start_page, end_page],
        "packages": versions,
    }
    output = Path(output)
    if output.resolve() == Path(path).resolve():
        raise ValueError("Output must not overwrite the source PDF")
    if output.exists():
        if not resume:
            raise ValueError("Output exists; use --resume or choose a new output")
        report = json.loads(output.read_text(encoding="utf-8"))
        if (
            report.get("document_id") != metadata["document_id"]
            or report.get("configuration") != configuration
        ):
            raise ValueError(
                "Resume source or extraction configuration changed; choose a new output"
            )
    else:
        report = {
            "extractor_version": EXTRACTOR_VERSION,
            "extractor": "docling+rapidocr",
            "source_pdf": str(Path(path).resolve()),
            "document_id": metadata["document_id"],
            "page_count": metadata["page_count"],
            "page_range": [start_page, end_page],
            "configuration": configuration,
            "document_warnings": metadata["warnings"],
            "seconds": 0,
            "pages": [
                {"page": p, "status": "pending", "records": [], "warnings": []}
                for p in range(start_page, end_page + 1)
            ],
        }
    refresh(report)
    atomic_save(output, report)
    todo = [p["page"] for p in report["pages"] if p["status"] in ("pending", "failed")]
    converter = convert_batch
    while todo:
        group = [todo.pop(0)]
        while todo and len(group) < batch_size and todo[0] == group[-1] + 1:
            group.append(todo.pop(0))
        began = time.perf_counter()
        pages = [report["pages"][p - start_page] for p in group]
        try:
            if converter is None:
                converter = DoclingBatch(force_ocr)
            data = converter(path, group[0], group[-1])
            if any(row["page"] not in group for row in data["records"]):
                raise ValueError("Converter returned a page outside its requested batch")
            for page in pages:
                page["records"] = [r for r in data["records"] if r["page"] == page["page"]]
                page["warnings"] = [w for w in data["warnings"] if page["page"] in w["pages"]]
                if not page["records"]:
                    page["warnings"].append(
                        {"reason": "No text recovered; blank or unreadable page needs review"}
                    )
                page["status"] = "needs_review" if page["warnings"] else "extracted"
                page.pop("error", None)
        except Exception as exc:  # noqa: BLE001 - isolate and record failed batches, never mark successful
            for page in pages:
                page.update(status="failed", records=[], warnings=[], error=type(exc).__name__)
        finally:
            report["seconds"] += time.perf_counter() - began
            refresh(report)
            atomic_save(output, report)
        if progress:
            progress(
                f"Pages {group[0]}-{group[-1]} saved | processed {report['processed_pages']}/{len(report['pages'])} | failed {len(report['failed_pages'])} | review {len(report['review_pages'])}"
            )
    return report
