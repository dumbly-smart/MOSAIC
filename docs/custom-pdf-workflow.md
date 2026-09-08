# Verify your own tender and bidder PDFs

This local prototype accepts two separate PDF paths:

1. A tender PDF containing explicitly scored numeric eligibility requirements.
2. A bidder PDF containing the bidder's evidence. It may contain native text, scanned
   non-selectable pages, or both.

Keep Ollama running with `bge-m3:latest` and `qwen3-vl:4b-instruct` installed. From the
MOSAIC folder, run:

```powershell
.\run-pdf-verification.ps1 `
  -TenderPdf "C:\path\to\your-tender.pdf" `
  -BidderPdf "C:\path\to\your-bidder.pdf" `
  -CaseName "my-test-01" `
  -ForceOcrBidder
```

`-ForceOcrBidder` is useful when the bidder PDF is known to be scanned. It is optional;
the normal Docling configuration already includes OCR fallback. Case names may contain
letters, numbers, hyphens and underscores. Each case is stored locally under
`artifacts/cases/<case-name>/`, which is excluded from Git.

If processing is interrupted, repeat the same command with `-Resume`. Existing incompatible
tender criteria, extraction settings, corpus hashes, model identities, top-k values or rule
versions are rejected rather than silently reused.

## Tender requirements

The current prototype supports numeric rules expressed as:

- minimum / at least (`>=`)
- maximum / at most (`<=`)
- exactly / equal to (`==`)
- explicit ranges (`range`)

Every scored rule must explicitly state its field, numeric threshold or bounds, unit and
weight. The tender must declare its scored-criterion count and a total scored weight of 100.
MOSAIC will not invent weights, tolerance bands or fallback ranges. A tender that omits these
details must be clarified or converted into an officer-approved structured rule set before
scoring.

## Outputs

The case directory contains:

- `tender-extraction.json`: Docling/RapidOCR tender text and provenance
- `criteria-from-tender.json`: Qwen-extracted, quote-grounded and versioned rules
- `bidder-extraction.json`: bidder OCR/native text with page and bounding-box provenance
- `bidder-bge-index/`: local BGE-M3 test index
- `retrieval-top-k.json`: ranked candidate evidence
- `verification-report.json`: Qwen-grounded evidence and deterministic scoring

The score is advisory. A procurement officer remains responsible for the final decision.
Do not place real sensitive bidder documents inside the repository or commit case artifacts.
