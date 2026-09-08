import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter

from services.api.app.verification_runner import LocalVerificationRunner, PgVectorIndex


class FakeStore:
    def search(self, corpus_id, model, query, top_k):
        return [(corpus_id, model, query, top_k)]


class VerificationRunnerTests(unittest.TestCase):
    def test_pgvector_index_preserves_embedding_scope(self):
        embedder = type(
            "Embedder",
            (),
            {"provider": "ollama", "name": "bge-m3:latest", "dimension": 1024},
        )()
        index = PgVectorIndex(FakeStore(), "corpus-1", embedder)
        self.assertEqual(index.metadata["dimension"], 1024)
        self.assertEqual(index.search([0.1], 3)[0][0:2], ("corpus-1", "bge-m3:latest"))

    def test_multiple_bidder_pdfs_are_merged_in_upload_order(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for number in (1, 2):
                path = Path(folder) / f"{number}.pdf"
                writer = PdfWriter()
                writer.add_blank_page(width=100 + number, height=200)
                with path.open("wb") as stream:
                    writer.write(stream)
                paths.append(path)
            output = Path(folder) / "merged.pdf"
            LocalVerificationRunner._merge_bidders(paths, output)
            merged = PdfReader(output)
            self.assertEqual(len(merged.pages), 2)
            self.assertEqual(float(merged.pages[0].mediabox.width), 101)
            self.assertEqual(float(merged.pages[1].mediabox.width), 102)

    def test_report_is_finalized_from_grounded_findings(self):
        criterion = {"id": "C1"}
        finding = {
            "criterion_id": "C1",
            "earned_points": 100,
            "review_required": False,
            "clarification_required": False,
            "status": "passed",
        }
        embedder = type(
            "Embedder",
            (),
            {"provider": "ollama", "name": "bge-m3:latest", "dimension": 1024},
        )()
        with patch(
            "services.api.app.verification_runner.verify_locally", return_value=iter([finding])
        ):
            report = LocalVerificationRunner._verify(
                {"version": "rules-v1", "criteria": [criterion]},
                object(),
                embedder,
                Path("bidder.pdf"),
                5,
                "corpus-1",
                started=0,
            )
        self.assertEqual(report["score"], 100)
        self.assertEqual(report["recommendation"], "qualify")
        self.assertEqual(report["components"]["vector_store"], "Supabase PostgreSQL+pgvector")


if __name__ == "__main__":
    unittest.main()
