# MOSAIC Architecture

This document is the implementation map for humans and coding agents. It turns the product constraints in [AGENTS.md](AGENTS.md) and the detailed [design specification](docs/superpowers/specs/2026-09-01-mosaic-design.md) into concrete service boundaries and invariants. If documents disagree, `AGENTS.md` is authoritative for safety and product boundaries.

## System purpose and boundary

MOSAIC is an officer-facing decision-support demonstration for bidder compliance review in Government e-Marketplace procurement. It ingests a bidder document package, extracts and normalizes evidence, evaluates versioned tender rules against document and mock portal evidence, and presents explainable findings. Only a Procurement Officer can record a final qualification, disqualification, or clarification decision.

The MVP must not use real bidder data or claim live access to government portals. Every external portal implementation is a clearly labelled deterministic mock or sandbox adapter until an authorized API contract exists.

## Logical architecture

```text
                       authenticated HTTPS
+------------------+   upload/review/decision   +---------------------+
| Officer dashboard| --------------------------> | Verification API    |
| Next.js + TS     | <-------------------------- | FastAPI             |
+------------------+   state/findings/evidence   +----------+----------+
                                                           |
                  +----------------------------------------+-------------------+
                  |                                        |                   |
                  v                                        v                   v
          +---------------+                         +---------------+   +--------------+
          | PostgreSQL    |                         | Object storage|   | Job queue    |
          | case metadata |                         | encrypted docs|   +------+-------+
          | findings/audit|                         | + derivatives |          |
          +---------------+                         +---------------+          v
                                                                         +----+-------+
                                                                         | Worker     |
                                                                         | extraction |
                                                                         | validation |
                                                                         | rules      |
                                                                         +----+-------+
                                                                              |
                                      +-------------------+-------------------+
                                      |                   |                   |
                                      v                   v                   v
                              format parsers       adapter ports       rule engine
                                                   mock/sandbox only   + scoring
                                                                              |
                                                                              v
                                                                  grounded recommendation
```

## Repository layout

The initial scaffold should converge on this layout without mixing domain logic into framework entry points:

```text
apps/
  web/                     Next.js officer dashboard
services/
  api/
    app/
      api/                 HTTP routes and request/response schemas
      domain/              framework-independent entities and policies
      extraction/          format readers and normalization
      adapters/            portal ports and mock/sandbox implementations
      rules/               versioned evaluation and scoring
      audit/               append-only event creation
      infrastructure/      database, storage, queue, scanner implementations
    tests/
      unit/
      integration/
workers/                   background worker entry point, if kept separately
fixtures/synthetic/        generated demo packages; never real bidder data
infra/                     local Compose and deployment configuration
docs/                      detailed designs and operational notes
```

The exact Python package layout may be adjusted during scaffolding, but dependencies must point inward: HTTP, persistence, queues, object storage, and portal clients depend on domain interfaces; domain rules never depend on a portal-specific response or web framework.

## Component responsibilities

### Officer dashboard (`apps/web`)

- Create and browse verification cases.
- Upload allowed bidder documents and show per-file processing state.
- Present findings with status, severity, explanation, rule version, and linked source evidence.
- Clearly distinguish system recommendations from officer decisions.
- Require an actor identity and reason before submitting qualify, disqualify, or clarification decisions.
- Never infer compliance from a missing response, loading state, or unavailable source.

The dashboard consumes API contracts only. It does not calculate findings, scores, or recommendations.

### Verification API (`services/api`)

- Authenticate and authorize officer actions.
- Validate file type and size before accepting content.
- Create cases, documents, jobs, and append-only audit events.
- Return stable case, progress, finding, evidence, and decision representations.
- Issue short-lived, scoped links for authorized evidence access.
- Reject decision requests without a reason and actor identity.

Keep route handlers thin. Business invariants belong in domain services and are tested without starting FastAPI.

### Background worker

- Scan accepted files through a malware-scanner interface.
- Extract content with format-specific parsers.
- Normalize identifiers and retain confidence plus source location.
- Obtain normalized evidence through adapter interfaces.
- Evaluate the case with the tender rule-set version captured for that run.
- Persist findings, score, risk, recommendation, and audit events.

Jobs are idempotent by case/run identity. Retries must not duplicate findings or mutate prior audit events.

### Extraction pipeline

Supported intake types are PDF, PNG, JPG/JPEG, DOCX, and XML. Use explicit MIME, extension, signature, and size checks rather than trusting a filename. PDF extraction tries native text before OCR fallback; images use OCR; DOCX processing reads paragraphs and tables; XML parsing disables external entities and network access.

Every extracted field carries its normalized value, confidence, source document, page/region or equivalent location, and extraction method. Unreadable content, unsupported files, or confidence below the configured threshold produces `needs_manual_review` rather than a compliant result.

### Portal adapter boundary

The rule engine consumes a normalized evidence contract, never a portal response:

```text
EvidenceResult
  source                 stable adapter identifier
  subject_identifier     normalized identifier used for lookup
  attribute              normalized evidence key
  value                  typed normalized value, when available
  status                 verified | inconsistent | unavailable | needs_manual_review
  retrieved_at           timestamp
  reference              human-readable source reference
  raw_evidence_location  protected object reference, when retained
```

Each adapter implements a shared port and maps its native response into `EvidenceResult`. Demo implementations must be named and displayed as mock/sandbox sources. Adapter timeouts, invalid responses, and exhausted retries resolve to `unavailable` and manual review; they never produce implicit verification.

### Rules, scoring, and recommendations

Tender rules are immutable once published. A new edit creates a new rule-set version. Each verification run and finding stores the exact rule-set version used.

A finding contains at least:

```text
Finding
  id, case_id, rule_id, rule_set_version
  status                 verified | missing | inconsistent | not_applicable |
                         unavailable | needs_manual_review
  severity               informational | low | medium | high | critical
  explanation            plain-language, officer-facing rationale
  evidence_refs[]        links to normalized evidence and document locations
  created_at
```

Scoring is deterministic and fully derived from versioned rules and findings. Critical unresolved conditions apply documented caps. `not_applicable` does not reduce a score, while unavailable or uncertain evidence cannot be treated as verified.

The recommendation writer receives only structured rules, findings, score, and risk. It may produce `qualify`, `request_clarification`, `manual_review`, or `consider_disqualification`, citing finding identifiers. It cannot read raw bidder documents or create a final decision.

### Persistence and audit

PostgreSQL stores tenders, rule sets, cases, document metadata, extracted fields, evidence, findings, officer decisions, and audit events. Encrypted S3-compatible storage holds originals and derived artifacts; database records store opaque object keys, not public URLs.

Audit events are insert-only and include event ID, case ID, actor/service, action, timestamp, correlation ID, immutable payload, and payload hash. Corrections append a new event. Officer decisions are also immutable records; a later change creates a new decision and audit event rather than updating history.

## End-to-end data flow

1. The officer creates a case and selects a published tender rule-set version.
2. The API validates each file, records metadata and checksum, stores it, appends an upload event, and enqueues processing.
3. The worker scans and parses each document, storing provenance-rich extracted fields. Failures create manual-review findings.
4. Normalized identifiers are submitted to mock/sandbox adapters. Every response is converted to the shared evidence contract.
5. The rules engine evaluates the captured rule version against document and adapter evidence.
6. The scoring service derives score and risk; the constrained writer derives a cited recommendation.
7. The dashboard displays progress, evidence, findings, and recommendation without presenting them as a final government determination.
8. The officer records a decision with actor identity and reason. The API appends the decision and corresponding audit event.

## Lifecycle and failure semantics

A case moves through explicit states:

```text
draft -> uploaded -> queued -> processing -> ready_for_review -> decided
                       |            |
                       +----------> needs_manual_review
```

`needs_manual_review` is a reviewable outcome, not a hidden system error. A technical failure may be retried within a bounded policy; after retries, the case records which source or document failed and why. The API must not expose a successful or compliant state while mandatory processing is incomplete.

## Security and privacy invariants

- Use synthetic identifiers and documents in tests, fixtures, screenshots, logs, and commits.
- Encrypt transport and stored objects; keep secrets in environment-managed secret storage.
- Apply least-privilege access to database, queue, and object storage credentials.
- Use authorization checks on every case, evidence, download, and decision operation.
- Minimize sensitive values in logs, adapter calls, AI prompts, and audit payloads.
- Use scoped, expiring object links and validate access before issuing them.
- Keep malware scanning behind an interface; a no-op scanner is acceptable only when visibly configured as demo/test behavior.
- Do not scrape or connect to a government portal without documented authorization and an approved contract.

## Testing contract

Implementation is test-first. The minimum verification layers are:

- API formatting and linting.
- Unit tests for every parser, normalization rule, adapter mapping, rule condition, scoring cap, recommendation grounding constraint, and audit append behavior.
- Adapter contract tests proving every implementation returns normalized evidence.
- Integration tests for a complete asynchronous verification case.
- Web type-checking, linting, and component tests for statuses, evidence, recommendations, and required decision reasons.
- End-to-end coverage from upload through an officer-recorded decision.
- Synthetic scenarios for a compliant bidder, missing mandatory document, identity mismatch, and blacklist/debarment hit.

Every milestone must document its exact local verification commands in [progress.md](progress.md) when tooling is introduced.

## Recommended implementation order

1. Scaffold shared development tooling, API, web app, PostgreSQL, object storage, and queue.
2. Define domain types, lifecycle states, API schemas, database migrations, and four synthetic fixture families.
3. Implement secure intake, storage, scanner port, extraction, and normalization.
4. Implement the adapter port and deterministic mock/sandbox adapters.
5. Implement versioned rules, findings, scoring, recommendation constraints, and append-only audit behavior.
6. Build the officer dashboard and decision workflow against stable API contracts.
7. Add integration and end-to-end tests, then deployment/demo hardening.

Do not begin a later step by bypassing an invariant owned by an earlier one. Update [progress.md](progress.md) in the same change that completes or materially changes a milestone.
