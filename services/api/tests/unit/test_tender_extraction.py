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
        for line, row in enumerate(self.rows, 1):
            row["line"] = line
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

    def test_numeric_clause_accepts_currency_before_threshold(self):
        self.rows[3]["text"] = "Requirement: Current bid security must be at least INR 25000."
        answer = json.loads(json.dumps(self.answer))
        answer["criteria"][0]["clause_quote"] = self.rows[3]["text"]
        answer["criteria"][0].pop("threshold")
        answer["criteria"][0].pop("unit")
        grounded = ground_page_answer(answer, self.rows, page=1)
        self.assertEqual(grounded["criteria"][0]["threshold"], 25000)
        self.assertEqual(grounded["criteria"][0]["unit"], "INR")

    def test_numeric_operator_accidentally_returned_as_value_type_is_normalized(self):
        answer = json.loads(json.dumps(self.answer))
        answer["criteria"][0]["value_type"] = ">="
        grounded = ground_page_answer(answer, self.rows, page=1)
        self.assertEqual(grounded["criteria"][0]["value_type"], "numeric")

    def test_unscored_document_mapping_rows_are_not_scored_criteria(self):
        rows = [
            {"page": 1, "line": 1, "text": "4. Documents Required from Bidders"},
            {"page": 1, "line": 2, "text": "| Bank Guarantee | C1 | PDF |"},
        ]
        answer = {
            "criteria": [
                {
                    "id": "C1",
                    "field": "Bank Guarantee",
                    "value_type": "document_presence",
                    "operator": "==",
                    "weight": None,
                    "clause_line": 2,
                    "weight_line": None,
                }
            ]
        }
        grounded = ground_page_answer(answer, rows, page=1)
        self.assertEqual(grounded["criteria"], [])

    def test_model_can_cite_supplied_line_ids_without_reproducing_quotes(self):
        answer = json.loads(json.dumps(self.answer))
        answer.update(count_line=1, total_weight_line=2)
        answer.pop("count_quote")
        answer.pop("total_weight_quote")
        answer["criteria"][0].update(clause_line=4, weight_line=5)
        answer["criteria"][0].pop("clause_quote")
        answer["criteria"][0].pop("weight_quote")
        grounded = ground_page_answer(answer, self.rows, page=1)
        self.assertEqual(grounded["criteria"][0]["clause"], self.rows[3]["text"])

    def test_criterion_count_can_be_grounded_by_clause_id_range(self):
        self.rows[0]["text"] = "Clause identifiers (C1-C5) correspond to the published rule set."
        answer = json.loads(json.dumps(self.answer))
        answer.update(
            declared_criteria_count=5,
            count_line=1,
        )
        answer.pop("count_quote")
        grounded = ground_page_answer(answer, self.rows, page=1)
        self.assertEqual(grounded["declared_criteria_count"], 5)

    def test_criterion_count_uses_grounded_range_over_model_value(self):
        self.rows[0]["text"] = "Clause identifiers (C1-C4) correspond to the published rule set."
        answer = json.loads(json.dumps(self.answer))
        answer.update(
            declared_criteria_count=5,
            count_line=1,
        )
        answer.pop("count_quote")
        grounded = ground_page_answer(answer, self.rows, page=1)
        self.assertEqual(grounded["declared_criteria_count"], 4)

    def test_bad_page_subtotals_recover_from_exact_document_declarations(self):
        rows = [
            {"page": 1, "line": 1, "text": "3. Eligibility Criteria"},
            {
                "page": 1,
                "line": 2,
                "text": "Clause identifiers (C1-C5) correspond to the published rule set.",
            },
            {"page": 1, "line": 3, "text": "Weights sum to 100 points."},
        ]
        answer = {
            "criteria": [],
            "declared_criteria_count": 2,
            "count_line": 1,
            "declared_total_weight": 50,
            "total_weight_line": 1,
        }
        grounded = ground_page_answer(answer, rows, page=1)
        self.assertEqual(grounded["declared_criteria_count"], 5)
        self.assertEqual(grounded["count_quote"], rows[1]["text"])
        self.assertEqual(grounded["declared_total_weight"], 100)
        self.assertEqual(grounded["total_weight_quote"], rows[2]["text"])

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

    def test_exact_document_declarations_are_recovered_when_model_omits_them(self):
        answer = json.loads(json.dumps(self.answer))
        answer.update(
            declared_criteria_count=1,
            count_quote=None,
            declared_total_weight=100,
            total_weight_quote=None,
        )
        grounded = ground_page_answer(answer, self.rows, page=1)
        self.assertEqual(grounded["declared_criteria_count"], 1)
        self.assertEqual(grounded["declared_total_weight"], 100)

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
