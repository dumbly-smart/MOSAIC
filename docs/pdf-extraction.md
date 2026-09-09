# General PDF extraction

The extractor accepts a PDF path; no bidder labels, answer key, fixed page count, or
synthetic-document wording is used to extract content. Docling performs layout/table
analysis and native text extraction, with RapidOCR through ONNX Runtime for scanned
content. This is extraction, not document authenticity checking or tender evaluation.

## Run and resume

From the MOSAIC folder:

```powershell
.\.venv\Scripts\python.exe benchmark.py extract "C:\path\your-document.pdf" --output artifacts/your-document.json
```

The actual page count is detected. The default covers every page, in batches of 25.
The PDF must have a PDF header, be at most 100 MB and contain 1-5000 pages. These
explicit intake limits are safety limits, not claims about accuracy. Password-protected
PDFs require an authorized unlocked copy. Damaged files either fail intake or receive
a structural-repair warning that blocks automatic verification.

Interrupt with Ctrl+C if necessary. Rerun the same command with --resume:

```powershell
.\.venv\Scripts\python.exe benchmark.py extract "C:\path\your-document.pdf" --output artifacts/your-document.json --resume
```

Each completed batch is atomically checkpointed. Resume skips extracted/reviewed pages
and retries pending/failed pages. A changed source hash, OCR mode, package version, or
requested page range requires a new output. Do not run two processes against the same
output. The in-flight batch may be repeated after interruption; saved batches are retained.

For a failed batch, retry with --resume --batch-size 1 to isolate problematic pages.
Docling has a 600-second conversion timeout per batch. This is a library-level timeout,
not a hard operating-system timeout for a stuck native library. There are no endless
automatic retries. Failed page numbers and error categories are recorded.

## Options

- --start N --end M: inspect a selected range. Omitting --end uses the last page.
- --batch-size N: 1-100 pages per checkpoint; smaller batches improve fault isolation.
- --force-ocr: force full-page OCR for problematic text layers. Use a NEW output path;
  this changes extraction configuration and is not an automatic repair guarantee.

## Results and limits

The JSON includes source SHA-256, actual page count, requested range, configuration,
package versions, per-page statuses, warnings, records, and processing time. Each record
retains its one-based page, item kind, text, bounding box and coordinate origin. Tables
are exported as Markdown; their locations are table/item boxes, not precise cell boxes.
Line numbers are normalized extraction lines, not stable PDF-native line numbers.

- complete: every page processed and produced text, without detected warnings.
- partial: a selected range succeeded, but it is not the complete document.
- needs_review: no text on one or more pages, ambiguous provenance, or a repaired PDF.
- incomplete: failed or pending pages remain.

Blank pages are deliberately flagged for review, because empty output cannot prove a
page was intentionally blank. Multi-page/unlocated text is retained in warning records
with its available provenance; it is not assigned a false page citation. Handwriting,
poor scans, unusual fonts, languages, overlapping text, multi-column reading order,
and complex tables may still be misread. A complete status is NOT an accuracy certificate.
Inspect representative pages and compare against known evidence when available.

baseline/verify --records requires a complete, current extraction. Legacy or partial
JSON cannot silently become a full-document evaluation. The one-page smoke-test files
from earlier sessions remain historical debugging inputs, not complete extractions.
Malware scanning and isolated intake execution are not implemented in this local CLI;
do not expose it as a public upload service without those protections.

The ZIP previously prepared for a teammate is an older snapshot and does not update
automatically when this local code changes.
