# Verify your own tender and bidder PDFs

This local prototype accepts two separate PDF paths:

1. A tender PDF containing explicitly scored eligibility requirements.
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

The current prototype supports:

- numeric minimum, maximum, equality, and explicit ranges
- boolean requirements such as `must not be blacklisted`
- required-document presence
- categorical equality or an explicit list of allowed values
- ISO `YYYY-MM-DD` date minimum, maximum, and equality

Every scored rule must explicitly state its field, requirement and weight. Numeric criteria
also require a threshold or bounds and unit. Dates must use an unambiguous ISO date. The tender
must declare its scored-criterion count and a total scored weight of 100. MOSAIC will not invent
weights, tolerance bands, dates, allowed categories, or fallback ranges. A tender that omits
these details must be clarified or converted into an officer-approved structured rule set.

## PostgreSQL and pgvector

The default command uses the persisted local cosine index. To exercise PostgreSQL+pgvector,
start the provided Compose service and set a local password:

```powershell
$env:MOSAIC_DB_PASSWORD = 'choose-a-local-demo-password'
docker compose up -d postgres
$env:MOSAIC_DATABASE_URL = 'postgresql://mosaic:choose-a-local-demo-password@127.0.0.1:55432/mosaic_benchmark'
```

Then add `-UsePgVector` to the normal command. You may instead pass the DSN using
`-DatabaseUrl`. The pgvector path creates the extension, a 1024-dimensional chunk table and an
HNSW cosine index; upserts are isolated by corpus hash and embedding-model name.

## Outputs

The case directory contains:

- `tender-extraction.json`: Docling/RapidOCR tender text and provenance
- `criteria-from-tender.json`: Qwen-extracted, quote-grounded and versioned rules
- `bidder-extraction.json`: bidder OCR/native text with page and bounding-box provenance
- `bidder-bge-index/`: local BGE-M3 test index (default path only)
- `retrieval-top-k.json`: ranked candidate evidence (default path only)
- `verification-report.json`: Qwen-grounded evidence and deterministic scoring

The score is advisory. A procurement officer remains responsible for the final decision.
Do not place real sensitive bidder documents inside the repository or commit case artifacts.
