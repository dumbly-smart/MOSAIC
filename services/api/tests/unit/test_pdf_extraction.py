import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.api.app.verification.pdf_extraction import (
    DoclingBatch,
    extract_document,
    require_complete,
)


class PdfExtractionTests(unittest.TestCase):
    def test_table_text_and_ambiguous_provenance_are_preserved(self):
        bbox = SimpleNamespace(model_dump=lambda **kw: {"l": 1, "coord_origin": "BOTTOMLEFT"})
        prov = SimpleNamespace(page_no=1, bbox=bbox, model_dump=lambda **kw: {"page_no": 1})
        table = SimpleNamespace(
            label="table",
            prov=[prov],
            self_ref="table-1",
            export_to_markdown=lambda **kw: "| Amount | 100 INR |",
        )
        unlocated = SimpleNamespace(label="text", text="Unlocated evidence", prov=[])
        document = SimpleNamespace(iterate_items=lambda: [(table, 0), (unlocated, 0)])
        converter = DoclingBatch.__new__(DoclingBatch)
        converter.converter = SimpleNamespace(
            convert=lambda *a, **kw: SimpleNamespace(
                status=SimpleNamespace(value="success"), document=document
            )
        )
        result = converter("synthetic.pdf", 1, 1)
        self.assertEqual(result["records"][0]["kind"], "table")
        self.assertEqual(result["records"][0]["page"], 1)
        self.assertEqual(result["warnings"][0]["text"], "Unlocated evidence")
        self.assertEqual(result["warnings"][0]["pages"], [1])

    def metadata(self, pages=3, doc_id="synthetic"):
        return {"document_id": doc_id, "page_count": pages, "warnings": [], "size_bytes": 10}

    def converter(self, path, start, end):
        return {
            "records": [
                {"page": p, "text": f"Evidence page {p}", "bbox": {"l": 1}, "kind": "text"}
                for p in range(start, end + 1)
            ],
            "warnings": [],
        }

    def run_job(self, output, **kwargs):
        return extract_document(
            "synthetic.pdf",
            output,
            convert_batch=kwargs.pop("convert_batch", self.converter),
            **kwargs,
        )

    @patch("services.api.app.verification.pdf_extraction.inspect_pdf")
    def test_detects_all_pages_without_fixed_500_limit(self, inspect):
        inspect.return_value = self.metadata(503)
        with tempfile.TemporaryDirectory() as tmp:
            report = self.run_job(Path(tmp) / "result.json", batch_size=25)
        self.assertEqual(len(report["pages"]), 503)
        self.assertEqual(report["records"][-1]["page"], 503)
        self.assertEqual(report["status"], "complete")
        require_complete(report)

    @patch("services.api.app.verification.pdf_extraction.inspect_pdf")
    def test_resume_skips_completed_pages(self, inspect):
        inspect.return_value = self.metadata()
        calls = []

        def interrupted(path, start, end):
            calls.append(start)
            if start == 2:
                raise KeyboardInterrupt()
            return self.converter(path, start, end)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.json"
            with self.assertRaises(KeyboardInterrupt):
                self.run_job(output, batch_size=1, convert_batch=interrupted)
            self.assertEqual(json.loads(output.read_text())["pages"][0]["status"], "extracted")
            calls.clear()

            def retry(path, start, end):
                calls.append(start)
                return self.converter(path, start, end)

            report = self.run_job(output, batch_size=1, resume=True, convert_batch=retry)
        self.assertEqual(calls, [2, 3])
        self.assertEqual(report["status"], "complete")

    @patch("services.api.app.verification.pdf_extraction.inspect_pdf")
    def test_failed_batch_is_visible_and_retryable(self, inspect):
        inspect.return_value = self.metadata(2)

        def failing(path, start, end):
            raise RuntimeError("conversion failed")

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.json"
            report = self.run_job(output, convert_batch=failing)
            self.assertEqual(report["failed_pages"], [1, 2])
            with self.assertRaises(ValueError):
                require_complete(report)
            report = self.run_job(output, resume=True)
        self.assertEqual(report["status"], "complete")

    @patch("services.api.app.verification.pdf_extraction.inspect_pdf")
    def test_no_text_and_warnings_require_review(self, inspect):
        inspect.return_value = self.metadata(1)
        for result in (
            {"records": [], "warnings": []},
            {
                "records": [{"page": 1, "text": "Footer", "bbox": None}],
                "warnings": [{"pages": [1], "reason": "ambiguous provenance"}],
            },
        ):
            with tempfile.TemporaryDirectory() as tmp:
                report = self.run_job(
                    Path(tmp) / "result.json", convert_batch=lambda *args, result=result: result
                )
            self.assertEqual(report["status"], "needs_review")
            with self.assertRaises(ValueError):
                require_complete(report)

    @patch("services.api.app.verification.pdf_extraction.inspect_pdf")
    def test_partial_range_not_accepted_as_complete_document(self, inspect):
        inspect.return_value = self.metadata(3)
        with tempfile.TemporaryDirectory() as tmp:
            report = self.run_job(Path(tmp) / "result.json", start_page=2, end_page=2)
        self.assertEqual(report["status"], "partial")
        with self.assertRaises(ValueError):
            require_complete(report)

    @patch("services.api.app.verification.pdf_extraction.inspect_pdf")
    def test_resume_rejects_different_document_or_options(self, inspect):
        inspect.return_value = self.metadata()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.json"
            self.run_job(output)
            with self.assertRaises(ValueError):
                self.run_job(output)
            with self.assertRaises(ValueError):
                self.run_job(output, resume=True, force_ocr=True)
            inspect.return_value = self.metadata(doc_id="other")
            with self.assertRaises(ValueError):
                self.run_job(output, resume=True)

    @patch("services.api.app.verification.pdf_extraction.inspect_pdf")
    def test_invalid_page_range(self, inspect):
        inspect.return_value = self.metadata()
        for start, end in ((0, 2), (2, 1), (1, 4)):
            with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                self.run_job(Path(tmp) / "result.json", start_page=start, end_page=end)

    def test_legacy_extraction_not_silently_trusted(self):
        with self.assertRaises(ValueError):
            require_complete({"records": []})
