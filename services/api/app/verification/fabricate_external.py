"""Create separate synthetic tender and fully scanned bidder PDFs for end-to-end tests."""

import hashlib
import io
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

TENDER = [
    (
        "C1",
        "Current bid security",
        "Requirement: Current bid security must be at least 25000 INR.",
        ">=",
        25000,
        "INR",
        25,
        1,
    ),
    (
        "C2",
        "Current annual turnover",
        "Requirement: Current annual turnover must be at least 1000000 INR.",
        ">=",
        1000000,
        "INR",
        25,
        1,
    ),
    (
        "C3",
        "Relevant completed experience",
        "Requirement: Relevant completed experience must be at least 5 years.",
        ">=",
        5,
        "years",
        20,
        2,
    ),
    (
        "C4",
        "Currently assigned engineers",
        "Requirement: Currently assigned engineers must be at least 10 people.",
        ">=",
        10,
        "people",
        15,
        2,
    ),
    (
        "C5",
        "Committed support response",
        "Requirement: Committed support response must be at most 24 hours.",
        "<=",
        24,
        "hours",
        15,
        3,
    ),
]

BIDDER_EVIDENCE = {
    2: ("C1", "Current bid security: 15000 INR.", 15000, "failed", 0),
    4: ("C2", "Current annual turnover: 970000 INR.", 970000, "failed", 0),
    6: ("C3", "Relevant completed experience: 7 years.", 7, "passed", 20),
    9: (
        "C4",
        "Currently assigned engineers: 12 people (provisional; roster unconfirmed).",
        12,
        "manual_review",
        0,
    ),
    12: ("C5", "Committed support response: 12 hours.", 12, "passed", 15),
}


def _draw_tender(path):
    width, height = A4
    canvas = Canvas(str(path), pagesize=A4)
    canvas.setTitle("MOSAIC Synthetic External Tender")
    for page in range(1, 4):
        canvas.setFillColor(HexColor("#123047"))
        canvas.rect(0, height - 95, width, 95, stroke=0, fill=1)
        canvas.setFillColor(HexColor("#FFFFFF"))
        canvas.setFont("Helvetica-Bold", 18)
        canvas.drawString(45, height - 55, "SYNTHETIC TENDER - ELIGIBILITY SCHEDULE")
        canvas.setFillColor(HexColor("#183B56"))
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(45, height - 125, f"Schedule page {page} of 3")
        y = height - 155
        if page == 1:
            for line in (
                "Tender reference: SYNTHETIC-EXTERNAL-001",
                "Scored criteria count: 5",
                "Total scored weight: 100 points",
            ):
                canvas.setFont("Helvetica", 11)
                canvas.drawString(45, y, line)
                y -= 22
            y -= 8
        for cid, field, clause, _operator, _threshold, _unit, weight, source_page in TENDER:
            if source_page != page:
                continue
            canvas.setFillColor(HexColor("#E8F1F5"))
            canvas.roundRect(40, y - 98, width - 80, 112, 7, stroke=0, fill=1)
            canvas.setFillColor(HexColor("#123047"))
            canvas.setFont("Helvetica-Bold", 12)
            canvas.drawString(55, y - 10, f"Criterion {cid} - {field}")
            canvas.setFont("Helvetica", 10)
            canvas.drawString(55, y - 39, clause)
            canvas.drawString(55, y - 67, f"Weight: {weight} points")
            y -= 140
        canvas.setFillColor(HexColor("#5B6B75"))
        canvas.setFont("Helvetica", 9)
        canvas.drawString(45, 45, "Synthetic research fixture only - not an official tender")
        canvas.showPage()
    canvas.save()


def _draw_scanned_bidder(path):
    rng = random.Random(20260908)
    width, height = A4
    canvas = Canvas(str(path), pagesize=A4)
    canvas.setTitle("MOSAIC Synthetic Fully Scanned Bidder Submission")
    regular = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
    bold = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 34)
    for page in range(1, 13):
        image = Image.new("RGB", (1400, 1980), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1400, 145), fill="#123047")
        draw.text((75, 48), "SYNTHETIC BIDDER SUBMISSION", fill="white", font=bold)
        lines = [f"Submission appendix {page:02d} - current filing FY 2025-26"]
        for row in range(1, 17):
            topic = rng.choice(("Inspection", "Training", "Inventory", "Maintenance"))
            lines.append(
                f"{topic} record {page * 100 + row}: {rng.randint(10, 99)} items reviewed."
            )
        historical = {
            3: "Historical example only: former bid security 40000 INR; not this bid.",
            5: "Prior-year turnover was 2000000 INR; superseded by current statement.",
            7: "Archived project profile: 12 years; not current bidder evidence.",
            10: "Former staffing plan listed 25 engineers; withdrawn.",
        }
        if page in historical:
            lines[8] = historical[page]
        if page in BIDDER_EVIDENCE:
            lines[10] = BIDDER_EVIDENCE[page][1]
        for row, line in enumerate(lines):
            draw.text((80, 200 + row * 88), line, fill="#182F40", font=regular)
        draw.text(
            (80, 1880),
            f"Synthetic fixture - image-only page {page} of 12",
            fill="#5B6B75",
            font=regular,
        )
        stream = io.BytesIO()
        image.save(stream, format="PNG", optimize=True)
        canvas.drawImage(ImageReader(stream), 0, 0, width, height)
        canvas.showPage()
    canvas.save()


def build_external(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    tender_pdf = output / "synthetic-external-tender.pdf"
    bidder_pdf = output / "synthetic-scanned-bidder.pdf"
    expected_path = output / "expected-external-e2e.json"
    if any(path.exists() for path in (tender_pdf, bidder_pdf, expected_path)):
        raise ValueError("External fixture output already exists; choose a new directory")
    _draw_tender(tender_pdf)
    _draw_scanned_bidder(bidder_pdf)
    tender_id = hashlib.sha256(tender_pdf.read_bytes()).hexdigest()
    version = "tender-pdf-" + tender_id[:16]
    expected = {
        "note": "Evaluation-only answer key. Never pass to tender extraction, retrieval, or Qwen.",
        "scoring_policy": "tender-evidence-quota-v2",
        "criteria_version": version,
        "expected_score": 35,
        "tender_criteria": [
            {
                "id": cid,
                "field": field,
                "clause": clause,
                "operator": operator,
                "threshold": threshold,
                "unit": unit,
                "weight": weight,
                "page": page,
            }
            for cid, field, clause, operator, threshold, unit, weight, page in TENDER
        ],
        "criteria": [
            {
                "criterion_id": cid,
                "quote": quote,
                "value": value,
                "page": page,
                "status": status,
                "earned_points": points,
            }
            for page, (cid, quote, value, status, points) in BIDDER_EVIDENCE.items()
        ],
        "bidder_page_count": 12,
        "all_bidder_pages_image_only": True,
    }
    expected_path.write_text(json.dumps(expected, indent=2), encoding="utf-8")
    return {"tender_pdf": tender_pdf, "bidder_pdf": bidder_pdf, "expected": expected_path}
