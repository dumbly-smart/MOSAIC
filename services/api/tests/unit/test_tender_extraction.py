import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.api.app.verification.tender_extraction import (
    build_criteria_document,
    evaluate_criteria_document,
    ground_page_answer,
    parse_tender_answer,
    qwen_extract_tender_page,
)


class TenderExtractionTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"page": 1, "text": "Scored criteria count: 1"},
            {"page": 1, "text": "Total scored weight: 100 points"},
            {"page": 1, "text": "Criterion C1 - Current bid security"},
            {"page": 1, "text": "Requirement: Current bid security must be at least 25000 INR."},
            {"page": 1, "text": "Weight: 100 points"},
        ]
        self.answer = {
            "declared_criteria_count": 1,
            "count_quote": "Scored criteria count: 1",
            "declared_total_weight": 100,
            "total_weight_quote": "Total scored weight: 100 points",
            "criteria": [
                {
                    "id": "C1",
                    "field": "Current bid security",
                    "value_type": "numeric",
                    "operator": ">=",
                    "threshold": 25000,
                    "unit": "INR",
                    "weight": 100,
                    "clause_quote": (
                        "Requirement: Current bid security must be at least 25000 INR."
                    ),
                    "weight_quote": "Weight: 100 points",
                }
            ],
        }

    def test_page_answer_is_grounded_in_exact_clause_and_weight_lines(self):
        grounded = ground_page_answer(self.answer, self.rows, page=1)
        self.assertEqual(grounded["criteria"][0]["threshold"], 25000)
        self.assertEqual(grounded["criteria"][0]["source_page"], 1)

    def test_invented_clause_weight_value_unit_or_field_is_rejected(self):
        changes = (
            {"clause_quote": "invented"},
            {"weight_quote": "Weight: 90 points"},
            {"threshold": 30000},
            {"unit": "USD"},
            {"field": "Annual turnover"},
        )
        for change in changes:
            answer = json.loads(json.dumps(self.answer))
            answer["criteria"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                ground_page_answer(answer, self.rows, page=1)

    def test_invalid_json_envelope_is_rejected(self):
        for raw in ("[]", "not json", '{"criteria":"wrong"}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_tender_answer({"message": {"content": raw}})

    def test_unquoted_page_subtotals_are_discarded_not_accepted(self):
        answer = json.loads(json.dumps(self.answer))
        answer.update(
            declared_criteria_count=1,
            count_quote=None,
            declared_total_weight=100,
            total_weight_quote=None,
        )
        grounded = ground_page_answer(answer, self.rows, page=1)
        self.assertIsNone(grounded["declared_criteria_count"])
        self.assertIsNone(grounded["declared_total_weight"])

    def test_criteria_document_derives_version_and_checks_declared_totals(self):
        pages = [ground_page_answer(self.answer, self.rows, page=1)]
        document = build_criteria_document(pages, document_id="a" * 64)
        self.assertEqual(document["version"], "tender-pdf-" + "a" * 16)
        self.assertEqual(document["criteria"][0]["tender_id"], "PDF-" + "a" * 12)
        self.assertEqual(document["criteria"][0]["source"]["page"], 1)
        broken = json.loads(json.dumps(pages))
        broken[0]["declared_criteria_count"] = 2
        with self.assertRaises(ValueError):
            build_criteria_document(broken, document_id="a" * 64)

    def test_duplicate_criteria_are_rejected(self):
        page = ground_page_answer(self.answer, self.rows, page=1)
        duplicate = json.loads(json.dumps(page))
        duplicate["declared_criteria_count"] = None
        duplicate["count_quote"] = None
        duplicate["declared_total_weight"] = None
        duplicate["total_weight_quote"] = None
        with self.assertRaises(ValueError):
            build_criteria_document([page, duplicate], document_id="a" * 64)

    def test_qwen_receives_page_image_and_untrusted_extracted_text(self):
        import pymupdf

        with tempfile.TemporaryDirectory() as temporary:
            pdf_path = Path(temporary) / "tender.pdf"
            pdf = pymupdf.open()
            pdf.new_page().insert_text((72, 72), "Tender")
            pdf.save(pdf_path)
            pdf.close()
            wire = json.dumps({"message": {"content": json.dumps(self.answer)}}).encode()
            with patch("urllib.request.urlopen", return_value=io.BytesIO(wire)) as request:
                parsed = qwen_extract_tender_page(self.rows, pdf_path, 1)
        payload = json.loads(request.call_args.args[0].data)
        self.assertEqual(len(payload["messages"][0]["images"]), 1)
        self.assertIn("untrusted", payload["messages"][0]["content"])
        self.assertEqual(parsed, self.answer)

    def test_criteria_evaluation_checks_source_page_and_rule_fields(self):
        actual = build_criteria_document(
            [ground_page_answer(self.answer, self.rows, page=1)], document_id="a" * 64
        )
        expected = {
            "criteria_version": actual["version"],
            "tender_criteria": [
                {
                    "id": "C1",
                    "field": "Current bid security",
                    "clause": self.answer["criteria"][0]["clause_quote"],
                    "operator": ">=",
                    "threshold": 25000,
                    "unit": "INR",
                    "weight": 100,
                    "page": 1,
                }
            ],
        }
        result = evaluate_criteria_document(actual, expected)
        self.assertTrue(result["all_correct"])
        actual["criteria"][0]["source"]["page"] = 2
        self.assertFalse(evaluate_criteria_document(actual, expected)["all_correct"])

    def test_boolean_presence_categorical_and_date_clauses_are_grounded(self):
        rows = [
            {"page": 1, "text": "Scored criteria count: 4"},
            {"page": 1, "text": "Total scored weight: 100 points"},
            {"page": 1, "text": "Criterion B1 - Blacklist status"},
            {"page": 1, "text": "Requirement: Blacklist status must not be blacklisted."},
            {"page": 1, "text": "Weight B1: 25 points"},
            {"page": 1, "text": "Criterion D1 - ISO certificate"},
            {"page": 1, "text": "Requirement: Bidder must submit ISO certificate document."},
            {"page": 1, "text": "Weight D1: 25 points"},
            {"page": 1, "text": "Criterion S1 - Registration status"},
            {"page": 1, "text": "Requirement: Registration status must be active."},
            {"page": 1, "text": "Weight S1: 25 points"},
            {"page": 1, "text": "Criterion X1 - Certificate expiry"},
            {"page": 1, "text": "Requirement: Certificate expiry must be valid until 2027-06-30."},
            {"page": 1, "text": "Weight X1: 25 points"},
        ]
        answer = {
            "declared_criteria_count": 4,
            "count_quote": rows[0]["text"],
            "declared_total_weight": 100,
            "total_weight_quote": rows[1]["text"],
            "criteria": [
                {
                    "id": "B1",
                    "field": "Blacklist status",
                    "value_type": "boolean",
                    "operator": "==",
                    "expected": False,
                    "weight": 25,
                    "clause_quote": rows[3]["text"],
                    "weight_quote": rows[4]["text"],
                },
                {
                    "id": "D1",
                    "field": "ISO certificate",
                    "value_type": "document_presence",
                    "operator": "==",
                    "expected": True,
                    "weight": 25,
                    "clause_quote": rows[6]["text"],
                    "weight_quote": rows[7]["text"],
                },
                {
                    "id": "S1",
                    "field": "Registration status",
                    "value_type": "categorical",
                    "operator": "==",
                    "expected": "active",
                    "weight": 25,
                    "clause_quote": rows[9]["text"],
                    "weight_quote": rows[10]["text"],
                },
                {
                    "id": "X1",
                    "field": "Certificate expiry",
                    "value_type": "date",
                    "operator": ">=",
                    "expected": "2027-06-30",
                    "weight": 25,
                    "clause_quote": rows[12]["text"],
                    "weight_quote": rows[13]["text"],
                },
            ],
        }
        document = build_criteria_document(
            [ground_page_answer(answer, rows, page=1)], document_id="b" * 64
        )
        self.assertEqual(
            [criterion["value_type"] for criterion in document["criteria"]],
            ["boolean", "document_presence", "categorical", "date"],
        )
