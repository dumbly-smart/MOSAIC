# MOSAIC Implementation Progress

Last updated: 2026-09-08

This file is the shared implementation ledger for humans and coding agents. Update it in the same commit as meaningful progress. Record only verified repository state—plans and intentions are not completed work.

## Status legend

- `[ ]` Not started
- `[~]` In progress; include the active branch or blocker in Notes
- `[x]` Completed and verified; include the verification evidence in Notes
- `[!]` Blocked; state the concrete dependency or decision required

## Current state

MOSAIC now has a local, framework-independent Python verification core and a tested
external-PDF workflow. It extracts grounded typed criteria from a tender PDF, processes native
or fully scanned bidder PDFs, retrieves evidence with BGE-M3 through a local index or pgvector,
compares it with Qwen3-VL, and scores it deterministically. FastAPI, object storage, portal
adapters, and the web application have not yet been connected.

## Documentation baseline

| Status | Deliverable | Notes |
|---|---|---|
| `[x]` | Product overview | `README.md` defines purpose, boundaries, intended stack, and current state. |
| `[x]` | Agent implementation rules | `AGENTS.md` defines mandatory safety, testing, architecture, and Git constraints. |
| `[x]` | Product design specification | `docs/superpowers/specs/2026-09-01-mosaic-design.md` defines scope, workflows, data model, and acceptance criteria. |
| `[x]` | Implementation architecture | `architecture.md` defines service boundaries, contracts, data flow, failure semantics, and delivery order. |
| `[x]` | Progress ledger | This file establishes milestones and evidence conventions. |

## Delivery milestones

### Phase 1 — Repository and local development

- [ ] Scaffold `apps/web` with Next.js and TypeScript.
- [~] Scaffold `services/api` with FastAPI and typed settings. The Python package exists; FastAPI and settings remain.
- [ ] Add PostgreSQL, S3-compatible storage, and queue services for local development.
- [~] Add repeatable setup, formatting, linting, type-checking, and test commands. Test and
  benchmark launchers exist; the future web/API scaffolds still need their checks.
- [x] Add ignore rules for secrets, uploads, runtime storage, generated PDF/report output,
  build output, model caches, virtual environments, and `.superpowers/` artifacts.
- [ ] Document environment variables with safe placeholder values.

Exit evidence: a clean checkout can start all services and run the initial API and web verification commands without real credentials or bidder data.

### Phase 2 — Domain contracts and synthetic fixtures

- [~] Define case lifecycle, normalized evidence, findings, decisions, and audit event types. Verification inputs, evidence, findings, and outcomes exist; lifecycle, decisions, and audit types remain.
- [~] Define versioned tender rule and rule-set representations. A versioned rule contract exists; published rule-set aggregation remains.
- [ ] Add database migrations for the core data model.
- [x] Create synthetic compliant-bidder structured fixtures in `demo.py` (no uploaded documents).
- [x] Create synthetic missing-mandatory-document structured fixtures in `demo.py`.
- [x] Create synthetic identity-mismatch structured fixtures in `demo.py`.
- [x] Create synthetic blacklist/debarment-hit structured fixtures in `demo.py`.

Exit evidence: schema/type tests and migrations pass, and fixture validation proves no real identifiers or uploaded documents are present.

### Phase 3 — Secure intake and extraction

- [ ] Enforce file extension, MIME, signature, and size allowlists.
- [ ] Add checksum creation and encrypted object-storage persistence.
- [ ] Define malware-scanner interface and labelled demo/test implementation.
- [x] Implement PDF native text extraction with OCR fallback. Complete-document and fully
  image-only PDF runs are covered by unit tests and synthetic end-to-end evidence.
- [ ] Implement image OCR, DOCX paragraph/table parsing, and hardened XML parsing.
- [x] Store confidence and exact source page/bounding-box provenance for extracted fields.
- [x] Fail closed to `needs_manual_review` for unsupported, unreadable, incomplete, or
  uncertain local-prototype input.

Exit evidence: parser and intake unit tests pass for valid, malformed, oversized, unsupported, and low-confidence samples.

### Phase 4 — Verification adapters

- [ ] Define the normalized adapter port and error taxonomy.
- [ ] Implement deterministic, clearly labelled mock/sandbox adapters.
- [ ] Add bounded timeout and retry behavior.
- [ ] Map unavailable, malformed, or uncertain responses to manual review.
- [ ] Add adapter contract tests for every implementation.

Exit evidence: every adapter passes the shared contract suite and no code or UI text claims live government integration.

### Phase 5 — Rules, scoring, recommendation, and audit

- [ ] Publish immutable, versioned tender rule sets.
- [~] Evaluate applicability and produce evidence-linked findings. The first required-field verification path exists; rule applicability and additional condition types remain.
- [~] Implement deterministic scoring, risk bands, and critical caps. Weighted scoring and a multi-rule critical-cap regression test exist; configurable policies remain.
- [ ] Constrain generated recommendations to structured findings and cited finding IDs.
- [ ] Implement append-only, hash-linked audit events.
- [ ] Require actor identity and reason for every officer decision.

Exit evidence: unit and integration tests cover rule versions, missing evidence, discrepancies, score caps, recommendation grounding, and append-only behavior.

### Phase 6 — Officer dashboard

- [ ] Build case list and case creation/upload flow.
- [ ] Show file-level and case-level processing state.
- [ ] Display finding status, severity, explanation, rule version, and source evidence.
- [ ] Visually separate recommendations from final officer decisions.
- [ ] Implement qualify, disqualify, and clarification actions with required reasons.
- [ ] Add accessible loading, empty, failure, and manual-review states.

Exit evidence: web type-check, lint, and component suites pass for all evidence and decision states.

### Phase 7 — Integration, end-to-end, and demo readiness

- [ ] Run each synthetic fixture through the complete asynchronous pipeline.
- [ ] Add end-to-end upload-to-decision coverage.
- [ ] Verify unavailable adapters and missing evidence cannot yield compliant success.
- [ ] Verify authorization and protected evidence-download behavior.
- [ ] Add local demo reset/seed instructions using synthetic data only.
- [ ] Document operational limits and all mock/sandbox integrations in the UI and README.

Exit evidence: the full API, web, integration, and end-to-end verification suite passes from a clean checkout.

## Verification commands

The first executable verification command is:

```powershell
python -m unittest discover -s services/api/tests -v
```

The remaining Phase 1 tooling must add exact commands for:

```text
API format
API lint
API unit and integration tests
Web type-check
Web lint
Web component tests
End-to-end tests
Local stack startup and health check
```

Do not mark an implementation item complete without running its relevant command and recording the result below.

## Verification log

| Date | Scope | Command or check | Result |
|---|---|---|---|
| 2026-09-03 | Documentation baseline | Required-file, internal-link target, placeholder, safety-language, and `git diff --check` validation | Passed |
| 2026-09-04 | Verification core | `python -m unittest discover -s services/api/tests -v` | Passed: 7 tests |
| 2026-09-06 | Validation and demo | `.\run.ps1 -Task test` | Passed: 23 tests, including CLI checks and nine scenario outcomes |
| 2026-09-06 | Terminal demonstration | `.\run.ps1` | All nine scenarios printed findings, evidence, scores, risks, and recommendations |
| 2026-09-07 | Embedding regression suite | `python -m unittest discover -s services/api/tests -q` plus changed-file Ruff checks | Passed: 70 tests; lint passed |
| 2026-09-07 | Full BGE-M3 retrieval | Ollama CPU embedding of the complete 500-page extraction, two top-5 searches, and isolated answer-key evaluation | Passed: 1,979/1,979 chunks; 5/5 recall; repeat reports byte-identical |
| 2026-09-08 | Full local BGE-to-Qwen workflow | `benchmark.py verify-local` with top-5 retrieval and adaptive PDF vision, followed by isolated answer-key evaluation | Passed: all five statuses, values, quotes, pages, and quotas; 35/100 in 410.18 seconds |
| 2026-09-08 | Full regression suite | `python -m unittest discover -s services/api/tests -q` plus changed-file Ruff checks | Passed: 76 tests; lint passed; completed-report resume verified |
| 2026-09-08 | External tender-to-bidder PDF workflow | Tender extraction, `extract-criteria`, forced-OCR bidder extraction, BGE-M3 retrieval, `verify-local`, isolated evaluators, and resumable launcher | Passed: five tender criteria grounded; 12/12 image-only bidder pages and 216 OCR lines; 5/5 evidence recall at rank 1; exact final outcome 35/100 |
| 2026-09-08 | Verification branch pre-push checks | `python -m unittest discover -s services/api/tests -q`, Ruff lint/format checks, PowerShell parser, and `git diff --check` | Passed: 85 tests; lint, format, script syntax, and whitespace checks passed |
| 2026-09-08 | Typed rules and pgvector integration | Typed grounding/scoring tests, pgvector SQL contract tests, synthetic PDF structure/render checks, full unit suite, Ruff | Passed: numeric, boolean, document-presence, categorical and date evaluation; pgvector schema/upsert/scoped-cosine contract; 96 tests; lint and format passed |

## Decisions

| Date | Decision | Reason |
|---|---|---|
| 2026-09-01 | Keep officer authority over all final outcomes | MOSAIC is decision support, not an autonomous procurement authority. |
| 2026-09-01 | Put portals behind normalized adapter interfaces | The engine remains independent of provider response formats and can fail closed. |
| 2026-09-01 | Use synthetic data and labelled mock/sandbox adapters for the MVP | Protects bidder data and avoids unsupported claims of government integration. |
| 2026-09-03 | Treat this file as the implementation status ledger | Agents and humans need one concise, evidence-based view of completed and remaining work. |

## Active work and blockers

- The original external-PDF proof is complete for the prototype's numeric rule scope. A separate
  three-page tender PDF produced five quote-grounded criteria with the expected field,
  operator, threshold, unit, weight, and page. A separate 12-page image-only bidder PDF
  produced 216 OCR lines with no failed or review pages. BGE-M3 retrieved all five expected
  evidence records at rank 1. Qwen3-VL plus deterministic scoring matched every expected
  status, value, quote, page, and point allocation: C1 failed 0/25, C2 failed 0/25,
  C3 passed 20/20, C4 manual review 0/15, and C5 passed 15/15, for 35/100.
  `run-pdf-verification.ps1` accepts arbitrary local tender and bidder PDF paths and its
  completed-stage resume path was integration-tested. Typed support was added afterward as
  described below; the 35/100 live result remains the numeric regression baseline.

- Typed rule support now covers numeric, boolean, required-document presence, categorical and
  ISO-date criteria. Exact source quotes, typed values and provenance are required before
  deterministic scoring. PostgreSQL+pgvector persistence is available through `PgStore` and
  `run-pdf-verification.ps1 -UsePgVector`; it creates a 1024-dimensional vector table, HNSW
  cosine index, idempotent scoped upserts and corpus/model-filtered searches. The database
  contract is unit-tested. Live pgvector execution is not claimed because Docker/PostgreSQL is
  not installed on this machine. A mixed-type tender and five-page image-only bidder fixture
  were generated and visually verified; Docling extracted all 17 tender lines, but live Qwen
  execution is pending because this process cannot launch Ollama and its service was offline.

- Full local verification is complete: persisted BGE-M3 top-5 retrieval feeds ranked text
  into Ollama `qwen3-vl:4b-instruct`; candidate page images are added only when the original
  PDF page has no native text. Qwen responses must cite an exact supplied chunk, quote,
  numeric value, and literal unit. Contradictory `found=false` responses are rejected.
  The five-criterion run completed in 410.18 seconds and matched the isolated answer key for
  status, value, exact quote, page, and points: C1 failed 0/25, C2 failed 0/25, C3 passed
  20/20, C4 manual review 0/15, and C5 passed 15/15. Advisory total: 35/100; C4 remains
  unresolved for officer review. Report: `artifacts/verify-local-bge-qwen-v2-adaptive.json`.

- BGE-M3 embedding/retrieval implementation is complete and live-tested. It includes
  page-bounded deterministic chunks, explicit query/document encoding, Ollama `bge-m3:latest`
  and Sentence Transformers `BAAI/bge-m3` providers, normalized 1024-dimensional vector
  validation, an atomic persisted exact-cosine test index, provider/model/corpus isolation,
  and a synthetic answer-key-isolated recall evaluator. All 70 unit/CLI tests pass and
  changed-file Ruff checks pass. Ollama embedded all 1,979 chunks from all 500 pages on CPU;
  the saved matrix is 1,979 x 1,024, finite, uniquely keyed, and normalized within 1.2e-7.
  Top-5 retrieval found all five ground-truth quotes on their correct pages: C1, C2, C3,
  and C5 ranked first; C4 ranked second. Two fresh saved-index query runs were byte-identical.
  BGE-M3 is forced to CPU because the local Ollama GPU runner crashed on normal-length chunks;
  CPU inference passed and leaves the 4 GB GPU available for Qwen3-VL. pgvector itself is
  intentionally not claimed as tested because that service belongs to the backend team.

- Full PDF extraction validated locally: all 500 pages (including five scanned pages)
  completed using resumable 25-page Docling/RapidOCR batches in 448.85 seconds.
  No failed/review pages. All 12000 source lines were found using whitespace-normalized
  containment on the correct page; all five key quotes were found on their expected pages.
  Output has 11845 records because Docling merged some lines; bounding boxes are item-level,
  not guaranteed individual-line highlights. OCR-text baseline yields 35/100, without Qwen.
- General PDF extraction now detects actual page count, checks intake limits, records
  per-page failures/warnings, retains ambiguous text in warnings, and supports --resume.
  Completed-run resume was verified to leave the saved result byte-for-byte unchanged.
  Partial/legacy/incomplete extractions are blocked from complete-document scoring.
  59 unit/CLI tests pass; changed-file lint passes. Arbitrary layouts/languages/handwriting
  remain subject to OCR limitations; this synthetic test is not universal accuracy proof.
  Results: outputs/extraction-full/ (relative to the workspace root).

- Evaluation-policy step 2 complete: benchmark scorer implements tender-evidence-quota-v2.
  synthetic-tender-v3 removes the invented tolerance and records synthetic clause sources.
  Missing -> unsure/zero/clarification; sourced fallback -> unsure/half; unreliable evidence
  and processing errors -> manual_review/zero. Normal allowed ranges earn full points.
  Updated baseline is 35/100; all five findings match the v2 answer key. 50 tests pass.
  Outputs are stored under outputs/benchmark-v2; historical v1 reports were not overwritten.
  Legacy portal demo unchanged. Live Qwen testing under v2 is the next step.

- Evaluation-policy step 1 complete: `docs/evaluation-contract-v2.md` records missing
  information as unsure/zero/awaiting clarification, half credit only for sourced
  fallback ranges, and zero-point manual review for unreliable evidence or failures.
  The invented 5% tolerance is withdrawn from v2. Scorer/fixture changes and revised
  expected scores are explicitly pending step 2; existing 55/100 reports are v1 only.

- Active work: local-only verification-layer implementation; no commit or push requested yet.
- Blockers: none for the framework-independent core. Local Python is not on `PATH`; Codex's bundled Python was used for verification.
- Completed locally: domain input validation, portal attribute/value conditions, ambiguity handling, and a runnable synthetic terminal demo.
- Added locally: weighted full/half/zero benchmark, 500-page synthetic PDF and matching text, provenance checks, Docling/RapidOCR extraction, BGE-M3/pgvector retrieval, and Ollama Qwen3-VL adapter code. Text baseline produces 55/100; 39 unit/CLI tests pass, including mocked Ollama response and failure handling. PDF page count confirmed and sample pages visually inspected. This does not establish live adapter accuracy.
- Runtime checks: benchmark dependencies installed and `pip check` passed. Docling/RapidOCR extracted 24 lines from scanned page 107 in 160.45 seconds including first-use setup; the turnover value 970000 INR and page/bounding-box provenance were recovered correctly. Ollama confirms qwen3-vl:4b is installed. The initial live text request timed out at 240 seconds; bounded output and disabled extra reasoning are now configured and covered by tests.
- Pending integration: PostgreSQL/pgvector is not running. The local BGE-M3/Qwen workflow is live-tested; PDF.js highlighting and API/dashboard integration remain future work.
- Live Qwen retry: the bounded non-thinking request returned a response, but its content failed JSON parsing. Neither live Qwen attempt is a passing extraction test. At the check, GPU memory usage was 3414/4096 MiB and Ollama reported only 113634181 bytes of model VRAM allocation. Investigate available GPU memory and structured-output behavior before the 500-page run. All 39 tests and changed-file lint/format checks pass.

## Update checklist

Latest local Qwen diagnostic: with the game closed, GPU baseline usage fell to 303 MiB.
On Ollama 0.30.10, qwen3-vl:4b returned empty final content at output limits of 256,
512, and 1024 tokens, including strict-schema and no-format probes. The last two
responses contained reasoning output despite think=false. No live Qwen extraction
has passed. Added explicit empty/truncated/envelope validation; 42 tests pass.
Subsequent Instruct test PASSED: qwen3-vl:4b-instruct processed all saved OCR chunks
from manually selected page 107 in 39.23 seconds. It returned grounded 970000 INR,
the exact quote, and the correct chunk ID. Deterministic scoring returned
within_tolerance, 12.5/25 points, review_required=true, with page/bbox provenance.
Report: ../../outputs/benchmark-v1/qwen-page107-report.json. The default now uses
the Instruct tag. This is one live saved-OCR-text test, not vector retrieval or
direct image analysis, and does not establish full-document accuracy.

When changing this file:

1. Update the date and only the milestones affected by the change.
2. Link or name the tests and verification commands actually run.
3. Add architectural decisions only when they constrain future implementation.
4. Record blockers as concrete missing inputs, access, or decisions.
5. Keep sensitive bidder data, secrets, uploaded files, and unverifiable claims out of the ledger.
