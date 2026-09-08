import json
import tempfile
import unittest
from pathlib import Path

import pymupdf

from services.api.app.verification.fabricate_external import build_external
from services.api.app.verification.fabricate_typed import build_typed


class ExternalFixtureTests(unittest.TestCase):
    def test_separate_tender_and_entirely_image_only_bidder_are_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "external"
            paths = build_external(output)
            with pymupdf.open(paths["tender_pdf"]) as tender:
                self.assertEqual(tender.page_count, 3)
                self.assertIn("Scored criteria count: 5", "".join(p.get_text() for p in tender))
            with pymupdf.open(paths["bidder_pdf"]) as bidder:
                self.assertEqual(bidder.page_count, 12)
                self.assertTrue(all(not page.get_text().strip() for page in bidder))
            expected = json.loads(paths["expected"].read_text(encoding="utf-8"))
        self.assertEqual(expected["expected_score"], 35)
        self.assertEqual(len(expected["tender_criteria"]), 5)
        self.assertEqual(len(expected["criteria"]), 5)

    def test_typed_fixture_has_one_tender_and_five_image_only_bidder_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = build_typed(Path(temporary))
            with pymupdf.open(paths["tender_pdf"]) as tender:
                self.assertEqual(tender.page_count, 1)
            with pymupdf.open(paths["bidder_pdf"]) as bidder:
                self.assertEqual(bidder.page_count, 5)
                self.assertTrue(all(not page.get_text().strip() for page in bidder))
