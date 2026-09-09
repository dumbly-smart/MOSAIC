"""Create a synthetic mixed-type tender and fully scanned bidder package."""

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

CRITERIA = (
    ("B1", "Blacklist status", "Requirement: Blacklist status must not be blacklisted.", 25),
    (
        "D1",
        "ISO certificate",
        "Requirement: ISO certificate document must be submitted.",
        20,
    ),
    (
        "S1",
        "Registration status",
        "Requirement: Registration status must be active.",
        20,
    ),
    (
        "X1",
        "Certificate expiry",
        "Requirement: Certificate expiry must be valid until 2027-06-30.",
        20,
    ),
    (
        "N1",
        "Relevant completed experience",
        "Requirement: Relevant completed experience must be at least 5 years.",
        15,
    ),
)

BIDDER_LINES = (
    "Current blacklist status: not blacklisted.",
    "ISO certificate document: attached.",
    "Current registration status: active.",
    "Certificate expiry: 2028-01-31.",
    "Relevant completed experience: 7 years.",
)


def build_typed(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    tender = output / "synthetic-typed-tender.pdf"
    bidder = output / "synthetic-typed-scanned-bidder.pdf"
    if tender.exists() or bidder.exists():
        raise ValueError("Typed fixture output already exists")
    width, height = A4
    canvas = Canvas(str(tender), pagesize=A4)
    canvas.setFillColor(HexColor("#123047"))
    canvas.rect(0, height - 90, width, 90, stroke=0, fill=1)
    canvas.setFillColor(HexColor("#FFFFFF"))
    canvas.setFont("Helvetica-Bold", 17)
    canvas.drawString(42, height - 54, "SYNTHETIC MIXED-TYPE TENDER")
    canvas.setFillColor(HexColor("#183B56"))
    canvas.setFont("Helvetica", 10)
    y = height - 120
    for line in ("Scored criteria count: 5", "Total scored weight: 100 points"):
        canvas.drawString(45, y, line)
        y -= 20
    for criterion_id, field, clause, weight in CRITERIA:
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(45, y, f"Criterion {criterion_id} - {field}")
        canvas.setFont("Helvetica", 9)
        canvas.drawString(55, y - 18, clause)
        canvas.drawString(55, y - 36, f"Weight: {weight} points")
        y -= 78
    canvas.setFont("Helvetica", 8)
    canvas.drawString(45, 35, "Synthetic fixture only - not an official tender")
    canvas.save()

    regular = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 31)
    bold = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 38)
    canvas = Canvas(str(bidder), pagesize=A4)
    for page, evidence in enumerate(BIDDER_LINES, 1):
        image = Image.new("RGB", (1400, 1980), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1400, 150), fill="#123047")
        draw.text((75, 48), "SYNTHETIC BIDDER EVIDENCE", fill="white", font=bold)
        draw.text((80, 235), f"Current declaration page {page} of 5", fill="#183B56", font=regular)
        draw.text((80, 410), evidence, fill="#102A3A", font=regular)
        draw.text(
            (80, 1740), "This page contains synthetic test data only.", fill="#5B6B75", font=regular
        )
        stream = io.BytesIO()
        image.save(stream, format="PNG", optimize=True)
        canvas.drawImage(ImageReader(stream), 0, 0, width, height)
        canvas.showPage()
    canvas.save()
    return {"tender_pdf": tender, "bidder_pdf": bidder}
