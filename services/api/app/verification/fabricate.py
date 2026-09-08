"""Deterministic synthetic 500-page corpus with separate evaluation-only answers."""

import io
import json
import random
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

EVIDENCE = {
    11: ("C1", "Current bid security: 15000 INR.", 15000, "failed", 0),
    107: ("C2", "Current annual turnover: 970000 INR.", 970000, "failed", 0),
    231: ("C3", "Relevant completed experience: 7 years.", 7, "passed", 20),
    389: (
        "C4",
        "Currently assigned engineers: 12 people (provisional; roster unconfirmed).",
        12,
        "manual_review",
        0,
    ),
    497: ("C5", "Committed support response: 12 hours.", 12, "passed", 15),
}


def build(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    pdf_path = output / "synthetic-bidder-500-pages.pdf"
    text_path = output / "synthetic-bidder.txt"
    if pdf_path.exists() or text_path.exists():
        raise ValueError("Output already exists; choose another output directory to preserve it.")
    rng = random.Random(20260906)
    width, height = A4
    canvas = Canvas(str(pdf_path), pagesize=A4)
    canvas.setTitle("MOSAIC - Synthetic 500-page bidder test package")
    all_lines, answers = [], []
    for page in range(1, 501):
        lines = [f"SYNTHETIC BIDDER | Appendix {page:03d} | Current submission FY 2025-26"]
        for row in range(1, 24):
            site = rng.choice(("North", "South", "East", "West", "Central"))
            topic = rng.choice(("Inventory", "Training", "Maintenance", "Transport", "Inspection"))
            lines.append(
                f"{topic} log: {site} site, batch {page * 29 + row}, {rng.randint(2, 99)} items reviewed."
            )
        if page % 19 == 0:
            lines[8] = "Historical example only: former bid security 40000 INR; not this bid."
        if page % 31 == 0:
            lines[9] = "Prior-year turnover was 2000000 INR; superseded by current statement."
        if page in EVIDENCE:
            cid, quote, value, status, points = EVIDENCE[page]
            lines[15] = quote
            answers.append(
                {
                    "criterion_id": cid,
                    "quote": quote,
                    "value": value,
                    "page": page,
                    "line": (page - 1) * 24 + 16,
                    "status": status,
                    "earned_points": points,
                }
            )
        # Five image-only pages (including two relevant clauses) exercise real OCR.
        scanned = page in (107, 150, 300, 389, 450)
        if scanned:
            from PIL import Image, ImageDraw, ImageFont

            image = Image.new("RGB", (1190, 1684), "white")
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
            for row, line in enumerate(lines):
                draw.text((90, 100 + row * 48), line, fill="#182f40", font=font)
            stream = io.BytesIO()
            image.save(stream, format="PNG")
            canvas.drawImage(ImageReader(stream), 0, 0, width, height)
        else:
            canvas.setFillColorRGB(0.09, 0.19, 0.25)
            canvas.setFont("Helvetica", 10)
            for row, line in enumerate(lines):
                canvas.drawString(45, height - 60 - row * 24, line)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(45, 30, f"MOSAIC synthetic test only | Page {page} of 500")
        canvas.showPage()
        all_lines.extend(lines)
    canvas.save()
    text_path.write_text("\n".join(all_lines) + "\n", encoding="utf-8")
    (output / "expected.json").write_text(
        json.dumps(
            {
                "note": "Evaluation-only answer key. Never pass to retrieval or Qwen.",
                "page_count": 500,
                "text_lines_per_page": 24,
                "expected_score": 35,
                "scoring_policy": "tender-evidence-quota-v2",
                "criteria_version": "synthetic-tender-v3",
                "criteria": answers,
                "scanned_pages": [107, 150, 300, 389, 450],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return pdf_path
