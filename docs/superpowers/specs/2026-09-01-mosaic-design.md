# MOSAIC Design Specification

## Purpose

MOSAIC (Multi-portal Officer-led Statutory Assessment & Integrated Compliance) is an SIH demonstration platform for Government e-Marketplace procurement. A Procurement Officer uploads one bidder's document package and tender eligibility rules. MOSAIC extracts evidence, cross-checks it against synthetic portal responses, evaluates tender rules, and presents an explainable compliance assessment. The officer, not the system, records the final outcome.

## Scope

### In scope

- A single officer dashboard that accepts PDF, PNG, JPG, DOCX, and XML files.
- Tender-specific rules covering statutory registrations, submitted documents, local content, OEM authorization, EPFO/ESIC applicability, Startup/NSIC status, and blacklist/debarment status.
- Extraction, identifier normalization, mock portal verification, cross-source discrepancy detection, scoring, recommendations, evidence display, and append-only audit history.
- Synthetic demo data and local Docker Compose deployment.

### Out of scope

- A bidder self-service portal, real portal credentials, scraping, autonomous qualification/disqualification, and real personal or taxpayer data.
- A claim that any mock response is a live government verification.

## Architecture

```text
Officer Dashboard (Next.js)
        |
        | upload documents + tender rules; review results; record decision
        v
Verification API (FastAPI) --------------------> PostgreSQL
  | intake, cases, rules, findings, audits        cases, findings, events
  |                                                |
  +--> worker queue --> extraction pipeline        +--> object storage
  |                    PDF/OCR/DOCX/XML                 originals/derivatives
  |
  +--> portal adapter interface --> labelled mock adapters
  |
  +--> rule engine --> scoring --> constrained recommendation writer
```

The web application calls the API over authenticated HTTPS. Uploads are registered as a case, stored in object storage, and queued for processing. The worker extracts text and structured fields, normalizes identifiers, queries adapters, evaluates rules, stores evidence-backed findings, calculates a score, and creates a structured recommendation. The dashboard polls or receives case progress and lets the officer issue a reasoned decision.

## Components

### Dashboard

The dashboard has a case list and an officer verification workspace. The workspace contains:

1. Document upload and optional identifiers (GSTIN, PAN, Udyam registration, CIN).
2. Processing state and file-level extraction results.
3. A chronological evidence timeline with status and source links.
4. Compliance score, risk level, missing requirements, discrepancies, and recommendation.
5. Qualify, disqualify, and request-clarification actions. Each requires a written reason and creates an audit record.

### Verification API and worker

File intake enforces type and size allowlists, creates a SHA-256 checksum, and delegates malware scanning through an interface. Extraction uses format-specific readers: native PDF text followed by OCR fallback, image OCR, DOCX paragraph/table extraction, and secure XML parsing with external entities disabled. Unsupported, unreadable, or low-confidence data creates a manual-review finding.

Adapter ports return a normalized evidence result: `source`, `subject_identifier`, `attribute`, `value`, `status`, `retrieved_at`, `reference`, and `raw_evidence_location`. The demo supplies deterministic mock implementations for Udyam, GST, PAN/Income Tax, MCA, Startup India, NSIC, EPFO, ESIC, Make in India, OEM authorization, and blacklist/debarment. Future authorized APIs replace adapters only.

The rules engine evaluates a versioned tender rule set against extracted and adapter evidence. Rules can be mandatory, conditionally applicable, informational, or manual-review-only. A finding records one of `verified`, `missing`, `inconsistent`, `not_applicable`, `unavailable`, or `needs_manual_review` plus severity and evidence references.

### Scoring and recommendation

Score begins at 100. Configured rule weights subtract points for missing or inconsistent evidence; `not_applicable` rules do not affect the score. Critical unresolved findings cap the score and risk: blacklist/debarment hit, invalid mandatory registration, and legal-identity mismatch. Risk bands are Low (80–100), Medium (50–79), and High (below 50).

The recommendation writer receives only structured findings, rules, score, and risk. It may recommend `qualify`, `request_clarification`, `manual_review`, or `consider_disqualification`, and must cite the responsible findings. It never returns a final decision.

### Audit trail

The system appends an event for upload, extraction, adapter call, rule evaluation, score generation, recommendation, and officer decision. Events include actor/service, action, timestamp, case ID, immutable payload hash, and correlation ID. Decisions additionally include rationale. Updates create new events rather than modifying historic evidence or decisions.

## Data model

- `tenders`: metadata and current rule-set version.
- `tender_rule_sets` / `tender_rules`: versioned conditions, severity, score weight, and applicability expression.
- `verification_cases`: bidder identity, tender, progress state, calculated score/risk, and recommendation version.
- `documents`: file metadata, checksum, storage key, scan status, and extraction state.
- `extracted_fields`: normalized value, confidence, document location, and provenance.
- `evidence`: normalized adapter/document evidence and source reference.
- `findings`: evaluation result, severity, explanation, evidence links, and rule-set version.
- `officer_decisions`: decision, rationale, officer identity, and timestamp.
- `audit_events`: append-only, hash-chained event records.

## Error handling and safety

Jobs have explicit queued, processing, completed, and failed states. Transient adapter failures use bounded retries; permanent failures or unknown results create `unavailable`/`needs_manual_review` findings. Intake rejects bad types, oversize files, malformed XML, and failed malware scans. All external adapter calls, AI prompts, and logs must minimize PII. At-rest encryption, scoped signed download URLs, role-based officer access, and environment-managed secrets are required before any non-demo deployment.

## Testing and acceptance criteria

- Unit tests cover each parser, identifier normalization, rule applicability, status mapping, score caps, recommendation grounding, and audit append-only behavior.
- Adapter contract tests prove all adapters produce normalized evidence.
- Integration tests run a document package through asynchronous processing and rule evaluation.
- End-to-end tests prove an officer can upload a package, see evidence and a recommendation, and record a reasoned decision.
- Synthetic fixtures cover compliant, missing-document, identity-mismatch, and blacklisted bidders.
- Acceptance requires no pathway that automatically records qualification/disqualification and no success state produced from an unavailable verification source.

## Delivery sequence

Build the API contracts and synthetic fixtures first; then document intake/extraction, adapters, rules/scoring/audit, dashboard, and deployment/demo polish. Each phase remains demonstrable with test data and can be extended with authorized portal integrations without changing the dashboard or core rule engine.
