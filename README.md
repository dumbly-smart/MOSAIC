# MOSAIC

**M**ulti-portal **O**fficer-led **S**tatutory **A**ssessment & **I**ntegrated **C**ompliance is an SIH demonstration for AI-assisted bidder compliance verification in Government e-Marketplace procurement.

MOSAIC helps a Procurement Officer review statutory and tender-specific eligibility from a bidder's document package. It is decision support only: an officer makes and records every qualification, disqualification, or clarification decision.

## Planned capabilities

- Accept PDF, PNG, JPG, DOCX, and XML bidder documents.
- Extract and normalize evidence from submitted documents.
- Check tender rules against normalized evidence and labelled mock/sandbox portal adapters.
- Surface explainable findings with status, severity, source evidence, and a human-readable explanation.
- Calculate a compliance score and grounded recommendation for officer review.
- Preserve versioned tender rules and an append-only audit history, including reasoned officer decisions.

## Architecture

The intended stack comprises a Next.js and TypeScript officer dashboard (`apps/web`), a Python FastAPI verification API (`services/api`), PostgreSQL, S3-compatible encrypted object storage, and a background extraction/verification worker.

Portal integrations remain behind adapter interfaces. The verification engine consumes normalized evidence rather than portal-specific response formats.

## Safety and demo boundary

- This project does not autonomously decide bidder qualification.
- Demo adapters are mock/sandbox implementations only. MOSAIC makes no claim of live integration with GeM, GSTN, Income Tax, MCA21, EPFO, ESIC, DigiLocker, or another government system.
- Treat all bidder information as sensitive. Do not add real identity, tax, registration, employee, bank, or uploaded-document data to the repository.
- Unavailable adapters, uncertain extraction, unsupported files, and missing evidence must fail closed to `needs_manual_review`.

## Project status

The `verification` branch contains a Python verification engine, a nine-scenario terminal demo, and layered synthetic document benchmarks. Docling/RapidOCR extraction is validated on the complete synthetic 500-page PDF. Ollama BGE-M3 embedded all 1,979 page-bounded chunks and achieved 5/5 ground-truth evidence recall at top-5; a persisted local test index and answer-key-isolated evaluator reproduce the result. A live mixed-type run also extracted and checked boolean, document-presence, categorical, ISO-date, and numeric rules against a five-page image-only bidder PDF, producing 100/100 with exact page evidence. A PostgreSQL+pgvector store and launcher path are implemented and contract-tested but have not been live-tested on this machine because Docker/PostgreSQL is unavailable. Portals, FastAPI, document upload, and the dashboard are not connected.

## Document benchmark

PDF extraction now detects the page count, checkpoints batches, and supports resume.
See [PDF extraction](docs/pdf-extraction.md). Partial, failed, and warning-bearing
extractions are blocked from automatic complete-document scoring.

The full 500-page synthetic PDF has now been extracted: all 12000 expected source
lines were found on their pages after whitespace normalization, including five scanned
pages. Runtime was about 7.5 minutes. Some lines are merged into larger text blocks;
this does not validate arbitrary-PDF accuracy or line-perfect highlighting.

Run `.\run.ps1 -Task benchmark` against the generated 500-page fixture's text counterpart. The v2 baseline scores 35/100 and prints each clause, extracted value, exact quote, line, status, and earned quota. This is a literal-text baseline, not a successful model integration test.

The v2 benchmark awards full quota for a pass and half only for an explicitly sourced fallback/review range. Missing information is unsure with zero points awaiting clarification; unreliable evidence or processing failure receives manual review with zero points. Review remains required for uncertainty and missing evidence. Quotas sum to 100; the legacy demo's score cap does not apply here.

See [layer-by-layer setup and testing](docs/verification-benchmark.md) for PDF extraction, database setup, and real model commands. The default `qwen3-vl:4b-instruct` model has now completed all five numeric criteria after BGE-M3 retrieval, using PDF images only for scanned candidate pages. Every status, value, exact quote, page, and point allocation matched the isolated synthetic answer key, producing the expected 35/100 advisory score. The verified baseline is available on the `verification` branch.

To test a separate tender PDF and bidder PDF without predefined `criteria.json`, use the
[custom PDF workflow](docs/custom-pdf-workflow.md). Qwen3-VL extracts quote-grounded typed
criteria from the tender, while Docling/RapidOCR, BGE-M3, Qwen3-VL and the deterministic scorer
process the bidder evidence. Numeric, boolean, document-presence, categorical and ISO-date
criteria are supported. The included numeric external test uses an entirely image-only 12-page
bidder PDF and passes both rule-extraction and final-report answer-key audits.

## Run locally in VS Code

Open the MOSAIC folder and use its PowerShell terminal:

```powershell
.\run.ps1
```

This runs all nine scenarios and prints findings, explanations, evidence references, scores, risks, and advisory recommendations. To select one scenario or run tests:

```powershell
.\run.ps1 -Scenario inactive-registration
.\run.ps1 -Task test
```

The launcher uses Python from PATH or the existing Codex bundled interpreter. If PowerShell blocks scripts, invoke Python directly using its full executable path. With Python on PATH:

```powershell
python demo.py --scenario all
python demo.py --scenario compliant --confidence 0.4
python demo.py --scenario compliant --json
python -m unittest discover -s services/api/tests -v
```

Scenarios: `compliant`, `missing-document`, `low-confidence`, `weak-match`, `identity-mismatch`, `portal-unavailable`, `inactive-registration`, `conflicting-evidence`, and `debarment-hit`.

Edit `scenario_input()` in `demo.py` to experiment with structured synthetic inputs. All scenarios invoke the actual verification engine; extraction, retrieval, and portal responses are fixtures.

Malformed inputs (including invalid enum states, references, scores, and rule configurations) raise `ValueError`. Missing or ambiguous evidence produces `needs_manual_review`. A verified portal lookup still has to satisfy the configured attribute and expected value. Multiple field, comparison, or matching portal candidates require review until evidence reconciliation is implemented.

The score measures verified rule weight; it is not a probability of compliance. Thresholds and the critical cap of 40 are demo policies, and model confidence is not calibrated. Scope/version isolation for persisted evidence, richer rules, model adapters, and officer decisions remain future work.

See the [design specification](docs/superpowers/specs/2026-09-01-mosaic-design.md) for the proposed workflows, data model, safety requirements, and test criteria.

## Development principles

- Use synthetic fixtures only, including compliant, missing-document, identity-mismatch, and blacklist/debarment cases.
- Version tender rules and store the rule version with each finding.
- Ground AI-generated summaries exclusively in structured findings from the verification engine.
- Keep audit events append-only; officer decisions require an actor identity and reason.
