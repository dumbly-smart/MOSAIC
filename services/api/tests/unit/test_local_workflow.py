import unittest

import numpy as np

from services.api.app.verification.local_workflow import resume_state, verify_locally


class FakeEmbedder:
    provider = "test"
    name = "fake"
    dimension = 3

    def encode_queries(self, texts):
        return np.asarray([[1.0, 0.0, 0.0] for _ in texts], dtype=np.float32)


class FakeIndex:
    def __init__(self, candidate):
        self.metadata = {"provider": "test", "model": "fake", "dimension": 3}
        self.candidate = candidate

    def search(self, query, *, top_k):
        self.query = query
        self.top_k = top_k
        return [self.candidate]


class LocalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.criterion = {
            "id": "C1",
            "clause": "Current bid security must be at least INR 25000",
            "field": "Current bid security",
            "operator": ">=",
            "threshold": 25000,
            "unit": "INR",
            "weight": 100,
            "tender_id": "synthetic",
            "rule_version": "v1",
            "source": {"clause": "Synthetic clause", "reference": "synthetic:C1"},
        }
        self.source = {
            "document_id": "doc-a",
            "page": 11,
            "line": 256,
            "bbox": None,
            "text": "Current bid security: 15000 INR.",
        }
        self.candidate = {
            "id": "chunk-a",
            "document_id": "doc-a",
            "page": 11,
            "line_start": 256,
            "line_end": 256,
            "text": self.source["text"],
            "rows": [self.source],
            "rank": 1,
            "similarity": 0.8,
        }

    def test_retrieval_qwen_grounded_evidence_and_scoring_are_connected(self):
        evidence = {
            "value": 15000,
            "unit": "INR",
            "uncertain": False,
            "source_quote": self.source["text"],
            "line": 256,
            "page": 11,
            "bbox": None,
            "document_id": "doc-a",
            "chunk_id": "chunk-a",
        }
        rows = list(
            verify_locally(
                [self.criterion],
                FakeIndex(self.candidate),
                FakeEmbedder(),
                lambda criterion, candidates, pdf: (evidence, {"found": True}),
                top_k=1,
            )
        )
        result = rows[0]
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["evidence"]["page"], 11)
        self.assertEqual(result["retrieval"][0]["rank"], 1)
        self.assertEqual(result["model_response"], {"found": True})

    def test_model_failure_fails_closed_with_retrieval_preserved(self):
        def unavailable(*args):
            raise OSError("offline")

        result = next(
            verify_locally(
                [self.criterion],
                FakeIndex(self.candidate),
                FakeEmbedder(),
                unavailable,
                top_k=1,
            )
        )
        self.assertEqual(result["status"], "manual_review")
        self.assertEqual(result["earned_points"], 0)
        self.assertEqual(result["reason_code"], "processing_or_rule_error")
        self.assertEqual(result["retrieval"][0]["id"], "chunk-a")

    def test_incompatible_index_and_embedder_are_rejected(self):
        index = FakeIndex(self.candidate)
        index.metadata = dict(index.metadata, model="wrong")
        with self.assertRaises(ValueError):
            list(verify_locally([self.criterion], index, FakeEmbedder(), lambda *args: None))

    def test_resume_accepts_only_a_matching_criterion_prefix(self):
        second = dict(self.criterion, id="C2")
        template = {
            "mode": "verify-local",
            "scoring_policy": "policy",
            "criteria_version": "v1",
            "components": {"corpus_id": "abc"},
        }
        saved = dict(
            template,
            results=[{"criterion_id": "C1", "policy_version": "policy"}],
            seconds=12.5,
        )
        pending, elapsed = resume_state(template, saved, [self.criterion, second], "policy")
        self.assertEqual([criterion["id"] for criterion in pending], ["C2"])
        self.assertEqual(elapsed, 12.5)
        with self.assertRaises(ValueError):
            resume_state(template, dict(saved, components={"corpus_id": "wrong"}), [], "policy")
