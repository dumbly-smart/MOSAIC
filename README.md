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

The repository currently contains the product design and implementation guidance; the application has not yet been scaffolded.

See the [design specification](docs/superpowers/specs/2026-09-01-mosaic-design.md) for the proposed workflows, data model, safety requirements, and test criteria.

## Development principles

- Use synthetic fixtures only, including compliant, missing-document, identity-mismatch, and blacklist/debarment cases.
- Version tender rules and store the rule version with each finding.
- Ground AI-generated summaries exclusively in structured findings from the verification engine.
- Keep audit events append-only; officer decisions require an actor identity and reason.
