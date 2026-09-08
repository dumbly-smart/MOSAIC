import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import numpy as np

from services.api.app.verification.embedding_retrieval import (
    LocalVectorIndex,
    OllamaBgeM3Embedder,
    build_chunks,
    corpus_id,
    criterion_query,
    evaluate_retrieval_report,
    validate_vectors,
)


class FakeEmbedder:
    name = "fake-3d"
    provider = "test"
    dimension = 3

    def encode_documents(self, texts):
        return np.asarray(
            [[1, 0, 0] if "security" in text else [0, 1, 0] for text in texts], dtype=np.float32
        )

    def encode_queries(self, texts):
        return np.asarray(
            [[1, 0, 0] if "security" in text else [0, 1, 0] for text in texts], dtype=np.float32
        )


class EmbeddingRetrievalTests(unittest.TestCase):
    def test_criterion_query_is_requirement_first(self):
        query = criterion_query(
            {"id": "C1", "field": "Bid security", "clause": "At least 25000 INR", "unit": "INR"}
        )
        self.assertIn("Bid security", query)
        self.assertIn("At least 25000 INR", query)
        with self.assertRaises(ValueError):
            criterion_query({"id": "C1"})

    def rows(self):
        return [
            {
                "document_id": "doc-a",
                "line": 1,
                "page": 1,
                "bbox": None,
                "text": "General bidder profile.",
                "method": "ocr",
            },
            {
                "document_id": "doc-a",
                "line": 2,
                "page": 1,
                "bbox": {"l": 1},
                "text": "Current bid security: 15000 INR.",
                "method": "ocr",
            },
            {
                "document_id": "doc-a",
                "line": 3,
                "page": 2,
                "bbox": None,
                "text": "Relevant completed experience: 7 years.",
                "method": "ocr",
            },
        ]

    def test_chunks_are_deterministic_scoped_and_do_not_cross_pages(self):
        first = build_chunks(self.rows(), max_chars=80, max_records=2, overlap_records=1)
        second = build_chunks(self.rows(), max_chars=80, max_records=2, overlap_records=1)
        self.assertEqual(first, second)
        self.assertTrue(all(c["document_id"] == "doc-a" for c in first))
        self.assertTrue(all(len({r["page"] for r in c["rows"]}) == 1 for c in first))
        self.assertEqual(len({c["id"] for c in first}), len(first))

    def test_oversized_record_is_split_without_losing_provenance_or_text(self):
        row = self.rows()[1] | {"text": "word " * 100}
        result = build_chunks([row], max_chars=60, max_records=2, overlap_records=0)
        self.assertGreater(len(result), 1)
        self.assertTrue(all(c["page"] == 1 and c["rows"][0]["line"] == 2 for c in result))
        rebuilt = " ".join(c["text"] for c in result).split()
        self.assertEqual(rebuilt, row["text"].split())

    def test_invalid_or_mixed_records_are_rejected(self):
        cases = (
            [],
            [self.rows()[0] | {"document_id": ""}],
            [self.rows()[0], self.rows()[1] | {"document_id": "doc-b"}],
            [self.rows()[0] | {"page": 0}],
            [self.rows()[0] | {"text": ""}],
        )
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                build_chunks(rows)

    def test_vector_validation_checks_shape_finiteness_and_normalization(self):
        validate_vectors(np.asarray([[1, 0, 0], [0, 1, 0]], dtype=np.float32), 2, 3)
        for vectors in (
            np.asarray([[1, 0]], dtype=np.float32),
            np.asarray([[float("nan"), 0, 0]], dtype=np.float32),
            np.asarray([[2, 0, 0]], dtype=np.float32),
        ):
            with self.subTest(vectors=vectors), self.assertRaises(ValueError):
                validate_vectors(vectors, 1, 3)

    def test_local_index_roundtrip_and_cosine_ranking(self):
        chunks = build_chunks(self.rows(), max_chars=80, max_records=2, overlap_records=0)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "index"
            LocalVectorIndex.build(chunks, FakeEmbedder(), target, batch_size=2)
            loaded = LocalVectorIndex.load(target, expected_corpus_id=corpus_id(chunks))
            result = loaded.search(FakeEmbedder().encode_queries(["security"])[0], top_k=2)
        self.assertIn("Current bid security", result[0]["text"])
        self.assertGreaterEqual(result[0]["similarity"], result[1]["similarity"])
        self.assertEqual(result[0]["rank"], 1)
        self.assertIn("rows", result[0])
        self.assertEqual(loaded.metadata["provider"], "test")

    @patch("services.api.app.verification.embedding_retrieval.urllib.request.urlopen")
    def test_ollama_adapter_uses_embed_endpoint_and_normalizes(self, urlopen):
        urlopen.return_value.__enter__.return_value = BytesIO(
            json.dumps({"model": "bge-m3:latest", "embeddings": [[3.0, 4.0, 0.0]]}).encode()
        )
        embedder = OllamaBgeM3Embedder(dimension=3)
        vector = embedder.encode_queries(["bid security"])
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/embed")
        self.assertEqual(payload["model"], "bge-m3:latest")
        self.assertFalse(payload["truncate"])
        self.assertEqual(payload["options"], {"num_gpu": 0})
        np.testing.assert_allclose(vector, [[0.6, 0.8, 0.0]])

    @patch("services.api.app.verification.embedding_retrieval.urllib.request.urlopen")
    def test_ollama_adapter_rejects_bad_count_dimension_or_zero_vector(self, urlopen):
        for response in (
            {"model": "bge-m3:latest", "embeddings": []},
            {"model": "bge-m3:latest", "embeddings": [[1.0, 2.0]]},
            {"model": "bge-m3:latest", "embeddings": [[0.0, 0.0, 0.0]]},
            {"model": "another-model", "embeddings": [[1.0, 0.0, 0.0]]},
        ):
            urlopen.return_value.__enter__.return_value = BytesIO(json.dumps(response).encode())
            with self.subTest(response=response), self.assertRaises(ValueError):
                OllamaBgeM3Embedder(dimension=3).encode_documents(["evidence"])

    def test_index_load_rejects_wrong_corpus_and_corruption(self):
        chunks = build_chunks(self.rows())
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "index"
            LocalVectorIndex.build(chunks, FakeEmbedder(), target)
            with self.assertRaises(ValueError):
                LocalVectorIndex.load(target, expected_corpus_id="wrong")
            (target / "vectors.npy").write_bytes(b"broken")
            with self.assertRaises(ValueError):
                LocalVectorIndex.load(target)

    def test_query_dimension_and_top_k_are_validated(self):
        chunks = build_chunks(self.rows())
        with tempfile.TemporaryDirectory() as tmp:
            index = LocalVectorIndex.build(chunks, FakeEmbedder(), Path(tmp) / "index")
            for query, k in ((np.ones(2), 1), (np.ones(3), 0), (np.ones(3), 1000)):
                with self.subTest(k=k), self.assertRaises(ValueError):
                    index.search(query, top_k=k)

    def test_retrieval_evaluation_reports_rank_and_recall(self):
        report = {
            "results": [
                {"criterion_id": "C1", "hits": [{"rank": 1, "page": 11, "text": "wanted"}]},
                {"criterion_id": "C2", "hits": [{"rank": 1, "page": 8, "text": "noise"}]},
            ]
        }
        expected = {
            "criteria": [
                {"criterion_id": "C1", "page": 11, "quote": "wanted"},
                {"criterion_id": "C2", "page": 9, "quote": "missing"},
            ]
        }
        result = evaluate_retrieval_report(report, expected)
        self.assertEqual(result["criteria_found"], 1)
        self.assertEqual(result["recall_at_k"], 0.5)
        self.assertEqual(result["checks"][0]["rank"], 1)
        self.assertIsNone(result["checks"][1]["rank"])
