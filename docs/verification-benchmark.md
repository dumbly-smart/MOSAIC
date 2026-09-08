# Layered verification benchmark

This benchmark implements the requested fixed quota scoring and traceable numeric findings.
It is local-only. All bidder data and requirements are synthetic.

## Evaluation policy update

The current scorer implements [evaluation contract v2](evaluation-contract-v2.md).
New reports use tender-evidence-quota-v2 and synthetic-tender-v3. Old 55/100 reports
under outputs/benchmark-v1 remain historical. New results are stored separately in
outputs/benchmark-v2. The document itself has not changed.

## Implemented scoring contract (v2)

`criteria.json` holds editable clauses, units, comparison operators, thresholds, quotas,
and optional sourced fallback ranges. Quotas must total 100. Supported numeric operators
are `>=`, `<=`, `==`, and `range`. Range endpoints must explicitly specify inclusivity.
Each criterion is always evaluated, even if retrieval finds nothing.

- Passed: 100% of that criterion's quota.
- Explicitly sourced fallback/review range: unsure, 50%, flagged for review.
- Missing information: unsure, 0%, awaiting clarification.
- Uncertain, provisional, conflicting, or invalid evidence: manual review, 0%.
- Failed: 0 points.
- Unavailable models, malformed or ungrounded results: manual review, 0%.

This is `tender-evidence-quota-v2`, distinct from the unchanged original `demo.py` legacy policy.
There is no aggregate score cap in this benchmark: the total is the sum of earned quotas.
Half credit does not establish compliance, and no numerical total records an officer decision.
Numeric comparisons use decimal arithmetic, not a model's verdict. Values must use the
same units as the criterion; implicit currency or magnitude conversions are not accepted yet.

## Layers

1. Generate 500 pages and 12,000 text lines, with five image-only pages. The separate
   `expected.json` is only an answer key for evaluation, never an inference input.
2. Docling parses PDFs and uses RapidOCR through ONNX Runtime. Save text, page numbers,
   and bounding boxes. The API can process a small page range before attempting all 500 pages.
3. BGE-M3 encodes extracted bidder chunks. For local prototype testing, Ollama serves
   `bge-m3:latest`; a Sentence Transformers `BAAI/bge-m3` provider remains available.
   Both produce validated, L2-normalized 1024-dimensional dense vectors. Each index records
   its provider, exact model tag, corpus hash, dimensions, and chunk count. Each criterion
   is encoded as a requirement-first query and searches only its bidder corpus.
   The Ollama embedding adapter defaults to CPU (`MOSAIC_EMBEDDING_NUM_GPU=0`) so BGE-M3
   does not compete with Qwen3-VL for the prototype machine's 4 GB GPU. The setting is
   written into index metadata. A different nonnegative value is an explicit local override.
4. Ollama Qwen3-VL extracts a relevant value and exact quote from retrieved candidates.
   When `--pdf` is supplied, images accompany the ranked text only for retrieved pages
   without native PDF text. This adaptive vision fallback covers scanned pages without
   slowing or distracting every native-text comparison.
5. Validate chunk IDs, verbatim quotes, numbers, units, and source locations. A cited
   number's presence is necessary but does not prove the model chose the right semantic fact.
6. Deterministic scoring produces clause, source quote, value, line, page, bbox, status,
   quota, earned points, and whether officer review is required.

No fallback silently impersonates Qwen, Docling, BGE-M3, or pgvector. `baseline` is clearly
labelled literal-label retrieval with regular-expression extraction and tests scoring only.

## Commands (from the MOSAIC folder)

See [general PDF extraction and resume](pdf-extraction.md) for arbitrary input paths,
page coverage, safety limits, checkpoints, warnings, and incomplete-document blocking.

Use the isolated Python environment:

```powershell
.\.venv\Scripts\python.exe benchmark.py doctor
.\.venv\Scripts\python.exe benchmark.py generate --output artifacts/corpus
.\.venv\Scripts\python.exe benchmark.py baseline --text artifacts/corpus/synthetic-bidder.txt
```

The pre-generated corpus for this local session is at `../../outputs/benchmark-v1/`:

```powershell
.\.venv\Scripts\python.exe benchmark.py baseline --text ../../outputs/benchmark-v1/synthetic-bidder.txt
.\.venv\Scripts\python.exe benchmark.py extract ../../outputs/benchmark-v1/synthetic-bidder-500-pages.pdf --start 107 --end 107 --output artifacts/page107-v2.json
.\.venv\Scripts\python.exe benchmark.py extract ../../outputs/benchmark-v1/synthetic-bidder-500-pages.pdf --output artifacts/extracted.json
```

Extraction can download Docling model weights on first use. Downloads are cached locally
under `.model-cache/huggingface`. First-time model downloads are additional to Python packages.

Start Ollama, pull the official BGE-M3 model, then build and test a local exact-cosine index:

```powershell
ollama pull bge-m3
.\.venv\Scripts\python.exe benchmark.py embed --provider ollama --records ../../outputs/extraction-full/synthetic-500-extracted.json --output artifacts/bge-m3-500-index --batch-size 8
.\.venv\Scripts\python.exe benchmark.py retrieve --index artifacts/bge-m3-500-index --top-k 10 --output artifacts/bge-m3-500-retrieval.json
.\.venv\Scripts\python.exe benchmark.py evaluate-retrieval --report artifacts/bge-m3-500-retrieval.json --expected ../../outputs/benchmark-v2/expected.json --output artifacts/bge-m3-500-evaluation.json
```

The saved local index is a reproducible pre-pgvector test harness, not the production store.
It uses exact cosine ranking and refuses corrupt files, corpus hash mismatches, provider/model
mismatches, invalid dimensions, non-finite values, zero vectors, and unnormalized queries.
Inputs longer than the model context fail instead of being silently truncated. Similarity
only ranks candidates: there is deliberately no similarity threshold that declares a bidder
compliant or proves information absent. The synthetic answer key is used only after retrieval
to measure recall; it is never sent to BGE-M3 or Qwen.

Install missing packages with:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-benchmark.txt
```

For PostgreSQL, install/start Docker Desktop or supply an existing dedicated database with
pgvector. The provided Compose configuration binds only to localhost on port 55432:

```powershell
$env:MOSAIC_DB_PASSWORD = 'choose-your-local-demo-password'
docker compose up -d postgres
$env:MOSAIC_DATABASE_URL = 'postgresql://mosaic:choose-your-local-demo-password@127.0.0.1:55432/mosaic_benchmark'
```

Use a URL-encoded password in the database URL if it contains special characters. Do not
commit credentials. The tool creates a benchmark table and upserts chunks only in that
database. It uses exact cosine search for this small corpus and filters by a content-derived
corpus ID and model. No arbitrary similarity threshold is treated as proof of compliance.

For local Qwen, start Ollama and download the small vision model:

```powershell
ollama pull qwen3-vl:4b-instruct
```

The selected model is `qwen3-vl:4b-instruct` (about 3.3 GB download). Runtime memory is additional
to model download size; on a 4 GB GPU, test a single page first and expect possible CPU
offload. If needed, explicitly switch to `qwen3-vl:2b` with `MOSAIC_QWEN_MODEL`.

The local adapter defaults to `http://127.0.0.1:11434`. Change `MOSAIC_OLLAMA_URL` or
`MOSAIC_QWEN_MODEL` only to a service/model you intend to use. The model stays loaded for
five minutes across criterion calls by default; `MOSAIC_QWEN_KEEP_ALIVE` can override this.

Full local verification using the persisted BGE-M3 index, adaptive Qwen vision, grounded
value extraction, and deterministic scoring requires no database:

```powershell
.\.venv\Scripts\python.exe benchmark.py verify-local --index artifacts/bge-m3-500-index --pdf ../../outputs/benchmark-v1/synthetic-bidder-500-pages.pdf --top-k 5 --output artifacts/verify-local-bge-qwen-v2.json
.\.venv\Scripts\python.exe benchmark.py evaluate --report artifacts/verify-local-bge-qwen-v2.json --expected ../../outputs/benchmark-v2/expected.json
.\.venv\Scripts\python.exe -m unittest discover -s services/api/tests -v
```

`verify-local` reloads the saved local exact-cosine index. The separate `verify` command is
the future PostgreSQL/pgvector path and requires that service. Neither silently substitutes
a baseline. Model errors produce manual-review findings with `processing_or_rule_error` and
zero credit. Setup/index/embedding errors stop the run instead of reporting success. Reports
are saved after every criterion and existing reports are never overwritten. After an
interruption, repeat the identical command with `--resume`; incompatible rule, model, corpus,
top-k, or completed-criterion state is rejected. The current CLI is a local benchmark,
not a server.

## Provenance and limits

Text line numbers refer to the original `.txt` file. PDF line numbers refer to the normalized
extraction output, not a PDF-native concept of a line. Page numbers are one-based. Docling
bounding boxes retain their coordinate origin; a future PDF.js viewer must convert these
through its page viewport, scale, and rotation. Multi-page or unlocated text is retained
in warning records instead of assigned a false page citation. Such warnings block complete
document scoring until reviewed. Exact quote validation can reject OCR spelling variations.

The fixture is an initial stress/smoke test: mostly regular pages, five inserted evidence
sentences, historical distractors, and five raster pages. It is not a realistic accuracy
benchmark for every certificate, language, table, or poor scan. The answer key enables
separate checks of retrieved location, extracted value, criterion status, and score.

To run the same stages with a separate tender PDF and bidder PDF, without a predefined
`criteria.json`, follow [Verify your own tender and bidder PDFs](custom-pdf-workflow.md).

Current ground truth total: 35/100 (0 + 0 + 20 + 0 + 15). The answer is not hardcoded into
the scorer. PDF.js highlighting, real portal validation, authentication, database migrations,
and final officer decisions remain outside this benchmark.

## Official references

- Docling RapidOCR configuration: https://docling-project.github.io/docling/_generated/examples/rapidocr_with_custom_models/
- Ollama BGE-M3 model: https://ollama.com/library/bge-m3
- Ollama embeddings API: https://docs.ollama.com/api/embed
- BGE-M3 Sentence Transformers model: https://huggingface.co/BAAI/bge-m3
- pgvector: https://github.com/pgvector/pgvector
- Ollama Qwen3-VL 4B Instruct: https://ollama.com/library/qwen3-vl:4b-instruct
- Ollama chat API: https://docs.ollama.com/api/chat
