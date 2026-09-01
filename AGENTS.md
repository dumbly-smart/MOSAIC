# MOSAIC Agent Guide

## Product boundary

MOSAIC is an officer-facing SIH demonstration for AI-assisted bidder compliance verification in Government e-Marketplace procurement. It accepts a bidder's PDF, image, DOCX, or XML document package and helps a Procurement Officer review statutory and tender-specific eligibility.

- The system is decision support only. A Procurement Officer makes and records the final qualification, disqualification, or clarification decision.
- Treat all bidder data as sensitive. Never add real PAN, GSTIN, Udyam, employee, bank, or identity data to fixtures, logs, screenshots, or commits.
- The MVP uses clearly labelled mock/sandbox portal adapters. Do not claim live integration with GeM, GSTN, Income Tax, MCA21, EPFO, ESIC, DigiLocker, or any other government system without documented authorization and an approved API contract.

## Intended stack

- `apps/web`: Next.js + TypeScript officer dashboard.
- `services/api`: Python FastAPI verification API.
- PostgreSQL for case data, extracted fields, findings, decisions, and append-only audit events.
- S3-compatible encrypted object storage for uploaded originals and derived artefacts.
- A background worker for document extraction and verification jobs.

Keep portal integration behind adapter interfaces; the verification engine must depend on normalized evidence, never a portal-specific response shape.

## Implementation rules

- Work test-first. Add or update tests for every behavior change.
- Version tender rules and preserve the rule version used in every finding.
- Findings must include status, severity, source evidence, and a human-readable explanation.
- AI-generated summaries may use only structured findings supplied by the verification engine; do not allow unsupported legal or compliance claims.
- Audit records are append-only. Officer decisions require a reason and actor identity.
- Fail closed to `needs_manual_review` for unavailable adapters, uncertain extraction, unsupported files, and missing evidence; never silently treat them as compliant.
- Use explicit type and size allowlists at file intake. Keep malware scanning behind an interface so the demo can use a no-op/test implementation.

## Required verification

- API: formatting/linting, unit tests for parsing, normalization, rules, scoring, and audit append behavior; integration tests for a full verification case.
- Web: type-check, lint, component tests for status/evidence display, and an end-to-end upload-to-decision flow.
- Include synthetic fixtures for: compliant bidder, missing mandatory document, identity mismatch, and blacklist/debarment hit.

## Git discipline

- Do not commit secrets, uploaded documents, runtime storage, generated build output, or `.superpowers/` artifacts.
- Keep commits small and describe the user-visible or architectural outcome.
- Before push, verify the current branch, working tree, and test output. Do not rewrite history or force-push unless explicitly requested.

