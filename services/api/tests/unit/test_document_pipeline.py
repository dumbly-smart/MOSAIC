import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.api.app.verification.document_pipeline import (
    baseline_evidence,
    chunks,
    ground_response,
    parse_model_answer,
    qwen_compare,
)


class DocumentPipelineTests(unittest.TestCase):
    def test_truncated_model_answer_is_rejected_even_if_json_is_valid(self):
        with self.assertRaisesRegex(ValueError, "output limit"):
            parse_model_answer({"done_reason": "length", "message": {"content": '{"found":false}'}})

    def test_empty_final_answer_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "no final JSON"):
            parse_model_answer({"message": {"content": "", "thinking": "not evidence"}})

    def test_malformed_model_envelope_is_rejected(self):
        for answer in ([], {"message": None}, {"message": {"content": None}}):
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                parse_model_answer(answer)

    def setUp(self):
        self.row = {
            "document_id": "doc-a",
            "line": 256,
            "page": 11,
            "bbox": None,
            "text": "Current bid security: 15000 INR.",
        }
        self.candidate = chunks([self.row])[0]
        self.response = {
            "found": True,
            "chunk_id": self.candidate["id"],
            "quote": self.row["text"],
            "value": 15000,
            "unit": "INR",
            "uncertain": False,
        }

    def test_exact_citation_preserves_location(self):
        evidence = ground_response(self.response, [self.candidate])
        self.assertEqual(evidence["line"], 256)
        self.assertEqual(evidence["page"], 11)
        self.assertEqual(evidence["document_id"], "doc-a")

    def test_hallucinated_quote_value_unit_or_chunk_rejected(self):
        for change in (
            {"quote": "invented"},
            {"value": 25000},
            {"unit": "USD"},
            {"chunk_id": "invented"},
            {"uncertain": "false"},
            {"value": True},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                ground_response(dict(self.response, **change), [self.candidate])

    def test_no_found_evidence_is_not_invented(self):
        self.assertIsNone(ground_response({"found": False}, [self.candidate]))

    def test_typed_values_are_grounded_in_exact_quotes(self):
        cases = (
            ({"value_type": "boolean"}, False, "Bidder is not blacklisted."),
            ({"value_type": "document_presence"}, True, "ISO certificate is attached."),
            ({"value_type": "categorical"}, "active", "Registration status: active."),
            ({"value_type": "date"}, "2027-06-30", "Valid until 2027-06-30."),
        )
        for criterion, value, quote in cases:
            candidate = chunks([dict(self.row, text=quote)])[0]
            response = {
                "found": True,
                "chunk_id": candidate["id"],
                "quote": quote,
                "value": value,
                "uncertain": False,
            }
            with self.subTest(criterion=criterion):
                evidence = ground_response(response, [candidate], criterion)
                self.assertEqual(evidence["value"], value)

    def test_typed_value_not_supported_by_quote_is_rejected(self):
        candidate = chunks([dict(self.row, text="Registration status: inactive.")])[0]
        response = {
            "found": True,
            "chunk_id": candidate["id"],
            "quote": candidate["text"],
            "value": "active",
            "uncertain": False,
        }
        with self.assertRaises(ValueError):
            ground_response(response, [candidate], {"value_type": "categorical"})

    def test_found_false_with_claimed_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "found=false"):
            ground_response(
                {"found": False, "quote": self.row["text"], "value": 15000},
                [self.candidate],
            )

    def test_ollama_request_and_grounding_without_live_model(self):
        wire = json.dumps({"message": {"content": json.dumps(self.response)}}).encode()
        with patch("urllib.request.urlopen", return_value=io.BytesIO(wire)) as request:
            evidence, raw = qwen_compare({"clause": "Security >= 25000 INR"}, [self.candidate])
        payload = json.loads(request.call_args.args[0].data)
        self.assertEqual(payload["format"], "json")
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"]["num_predict"], 512)
        self.assertIn("Rank 1", payload["messages"][0]["content"])
        self.assertEqual(evidence["line"], 256)
        self.assertEqual(raw, self.response)

    def test_pdf_images_are_attached_only_for_pages_without_native_text(self):
        import pymupdf

        with tempfile.TemporaryDirectory() as temporary:
            pdf_path = Path(temporary) / "mixed.pdf"
            pdf = pymupdf.open()
            pdf.new_page().insert_text((72, 72), "Native text")
            pdf.new_page()
            pdf.save(pdf_path)
            pdf.close()
            native = dict(self.candidate, page=1, rank=1)
            scanned = dict(self.candidate, id="scan", page=2, rank=2)
            wire = json.dumps({"message": {"content": '{"found":false}'}}).encode()
            with patch("urllib.request.urlopen", return_value=io.BytesIO(wire)) as request:
                qwen_compare({"clause": "Missing"}, [native, scanned], pdf_path)
        payload = json.loads(request.call_args.args[0].data)
        self.assertEqual(len(payload["messages"][0]["images"]), 1)

    def test_ollama_unavailable_does_not_fabricate_evidence(self):
        with (
            patch("urllib.request.urlopen", side_effect=OSError("offline")),
            self.assertRaises(OSError),
        ):
            qwen_compare({"clause": "Security >= 25000 INR"}, [self.candidate])

    def test_ollama_nonobject_reply_rejected(self):
        wire = json.dumps({"message": {"content": "[]"}}).encode()
        with (
            patch("urllib.request.urlopen", return_value=io.BytesIO(wire)),
            self.assertRaises(ValueError),
        ):
            qwen_compare({"clause": "Security >= 25000 INR"}, [self.candidate])

    def test_chunks_do_not_cross_pages(self):
        records = chunks([self.row, dict(self.row, line=257, page=12)])
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["page"], 12)

    def test_baseline_conflict_is_not_silently_selected(self):
        rule = {"field": "Current bid security", "unit": "INR"}
        with self.assertRaises(ValueError):
            baseline_evidence(
                rule, [self.row, dict(self.row, text="Current bid security: 40000 INR.")]
            )

    def test_cli_reads_document_lines_and_scores_not_answer_key(self):
        root = Path(__file__).resolve().parents[4]
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "bidder.txt").write_text(
                "Current bid security: 15000 INR.\nCurrent annual turnover: 970000 INR.\nRelevant completed experience: 7 years.\nCurrently assigned engineers: 12 people (provisional).\nCommitted support response: 12 hours.",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    "benchmark.py",
                    "baseline",
                    "--text",
                    str(folder / "bidder.txt"),
                    "--output",
                    str(folder / "result.json"),
                ],
                cwd=root,
                check=True,
                capture_output=True,
            )
            report = json.loads((folder / "result.json").read_text())
            self.assertEqual(report["score"], 35)
            self.assertEqual(report["scoring_policy"], "tender-evidence-quota-v2")
            self.assertEqual(report["results"][1]["status"], "failed")
            self.assertEqual(report["results"][3]["status"], "manual_review")
            self.assertTrue(report["review_required"])
            self.assertEqual(report["results"][0]["evidence"]["line"], 1)
