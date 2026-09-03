# MOSAIC Architecture

This document defines the implementation architecture for MOSAIC. It converts the product constraints in [AGENTS.md](AGENTS.md) and the detailed [design specification](docs/superpowers/specs/2026-09-01-mosaic-design.md) into concrete components, processing stages, service boundaries, and safety invariants.

If the documents disagree, `AGENTS.md` is authoritative for product and safety boundaries.

## 1. System purpose

MOSAIC—Multi-portal Officer-led Statutory Assessment and Integrated Compliance—is an officer-facing decision-support system for bidder compliance review in Government e-Marketplace procurement.

It accepts a bidder document package, extracts structured evidence using native parsers, OCR, and Qwen3-VL, retrieves relevant tender requirements using vector search, compares bidder evidence against those requirements, verifies selected claims using labelled mock or sandbox portal adapters, and produces explainable compliance findings.

MOSAIC does not autonomously qualify or disqualify bidders. Only an authenticated Procurement Officer can record the final qualification, disqualification, clarification, or manual-review decision.

## 2. Demo and safety boundary

The hackathon MVP must:

- Use synthetic bidder identities and documents.
- Use clearly labelled mock or sandbox portal adapters.
- Never claim live access to GeM, GSTN, MCA21, Income Tax, EPFO, ESIC, DigiLocker, or another government system.
- Never treat unavailable, uncertain, incomplete, or conflicting evidence as verified.
- Show the source and reasoning behind every finding.
- Clearly distinguish an AI-generated comparison, a system recommendation, and an officer’s final decision.

Real government portal integrations may only be introduced after an authorized API contract and security review exist.

## 3. Core verification principle

MOSAIC separates retrieval, comparison, verification, and decision-making:

- **Embeddings and pgvector retrieve candidate matches.**
- **Qwen3-VL extracts and compares document evidence.**
- **Portal adapters verify selected external claims.**
- **The deterministic rule engine creates compliance findings.**
- **The recommendation service summarizes those findings.**
- **The Procurement Officer makes the final decision.**

A vector similarity score is not proof of compliance. A Qwen3-VL response is not a final procurement decision. A portal timeout is not evidence of non-compliance.

## 4. Logical architecture

```text
                              authenticated HTTPS
+---------------------+      upload/review/decision      +----------------------+
| Officer dashboard   | --------------------------------> | Verification API     |
| Next.js + TypeScript| <-------------------------------- | FastAPI              |
+---------------------+   cases/findings/evidence/status +----------+-----------+
                                                                  |
                          +---------------------------------------+------------------+
                          |                    |                  |                  |
                          v                    v                  v                  v
                  +---------------+    +---------------+   +-------------+   +-------------+
                  | PostgreSQL    |    | Object storage|   | Job queue   |   | Audit store |
                  | + pgvector    |    | encrypted docs|   +------+------+   | append-only |
                  | cases/rules/  |    | + derivatives |          |          +-------------+
                  | embeddings    |    +---------------+          |
                  +---------------+                               v
                                                        +---------+----------+
                                                        | Processing worker  |
                                                        +---------+----------+
                                                                  |
                    +----------------+-----------------------------+-------------------+
                    |                |                |                |                |
                    v                v                v                v                v
              file validation   parsers/OCR     Qwen3-VL       vector retrieval   portal adapters
                                                extraction       with pgvector     mock/sandbox
                    |                |                |                |                |
                    +----------------+----------------+----------------+----------------+
                                                                  |
                                                                  v
                                                     evidence comparison pipeline
                                                                  |
                                                                  v
                                                   deterministic rules and scoring
                                                                  |
                                                                  v
                                                      grounded recommendation
                                                                  |
                                                                  v
                                                        officer final decision
```

## 5. Repository layout

```text
apps/
  web/                     Next.js officer dashboard
services/
  api/
    app/
      api/                 HTTP routes and request/response schemas
      domain/              framework-independent entities, states, and policies
      intake/              file validation, checksums, and upload handling
      extraction/          parsers, OCR, Qwen3-VL extraction, and normalization
      retrieval/           chunking, embeddings, pgvector search, and reranking
      comparison/          Qwen3-VL comparison and structured-output validation
      adapters/            portal ports and mock/sandbox implementations
      rules/               versioned tender rules, evaluation, and scoring
      recommendations/     grounded recommendation generation
      audit/               append-only audit event creation and verification
      infrastructure/      database, storage, queue, model, and scanner implementations
    tests/
      unit/
      integration/
workers/                   background processing entry point
fixtures/synthetic/        generated demo packages and portal records
infra/                     local development and deployment configuration
docs/                      detailed designs, contracts, and evaluation results
```

Dependencies must point inward. Domain rules must not depend on FastAPI, PostgreSQL, pgvector, Qwen-specific response formats, or portal-specific responses. Model, embedding, database, storage, queue, and portal implementations depend on domain interfaces.

## 6. Officer dashboard

The dashboard allows an authenticated Procurement Officer to:

- Create and browse verification cases.
- Select a published tender and rule-set version.
- Upload supported bidder documents.
- Monitor processing status for every file.
- Review extracted fields with source document and page references.
- Review retrieved tender clauses and similarity scores.
- Review AI comparisons and associated evidence.
- Review mock or sandbox portal verification results.
- Review deterministic findings, severity, score, and risk.
- Distinguish recommendations from final decisions.
- Record a qualification, disqualification, clarification, or manual-review decision with a reason.
- View the append-only case audit history.

The dashboard consumes API contracts only. It must not calculate similarity, findings, scores, risk levels, or recommendations. A missing response or loading state must never appear as successful verification.

## 7. Verification API

The FastAPI service is responsible for:

- Authenticating users and deriving actor identity from the authenticated session.
- Authorizing access to cases, documents, evidence, and decisions.
- Validating file type and size before accepting content.
- Creating cases, documents, verification runs, and jobs.
- Capturing the selected tender rule-set version.
- Returning stable case, progress, evidence, finding, and decision representations.
- Issuing short-lived, scoped links for authorized evidence access.
- Rejecting decisions without a reason.
- Rejecting client-supplied actor identities that conflict with authentication.
- Appending audit events for significant actions.

Route handlers must remain thin. Business rules and lifecycle invariants belong in domain services and must be testable without starting FastAPI.

## 8. Background processing worker

The worker executes the verification pipeline asynchronously:

1. Scan accepted files through a malware-scanner interface.
2. Classify each document.
3. Extract native text and structure when available.
4. Run OCR or Qwen3-VL when visual understanding is required.
5. Normalize extracted fields while preserving provenance.
6. Create searchable chunks from tender requirements and bidder evidence.
7. Generate embeddings and store them using pgvector.
8. Retrieve the most relevant tender clauses and reference evidence.
9. Ask Qwen3-VL to compare the retrieved requirements with source evidence.
10. Validate the model’s structured response.
11. Query mock or sandbox portal adapters when external verification is required.
12. Run deterministic tender rules.
13. Calculate score and risk.
14. Produce a grounded recommendation.
15. Store results and append audit events.

Jobs must be idempotent by case ID and verification-run ID. Retrying a job must not duplicate findings, decisions, or audit events.

## 9. Document intake

Supported MVP file types are PDF, PNG, JPG/JPEG, DOCX, and XML.

The intake service validates the file extension, declared MIME type, detected signature, configured size limit, checksum, and duplicate status. It must not trust the filename alone.

XML processing disables external entities and network access. Unsupported or unreadable files produce a manual-review result rather than being ignored.

## 10. Extraction pipeline

Extraction uses the least complex reliable method:

- Text-based PDF: native text extraction first.
- Scanned PDF: OCR or Qwen3-VL fallback.
- Image: OCR and Qwen3-VL visual extraction.
- DOCX: paragraph and table extraction.
- XML: secure structured parsing.
- Complex tables, seals, labels, or layouts: Qwen3-VL extraction.

Qwen3-VL receives only the pages or regions required for the extraction task. Sensitive data must be minimized in prompts and logs.

Every extracted field includes:

```text
ExtractedField
  id
  case_id
  document_id
  field_name
  raw_value
  normalized_value
  value_type
  confidence
  page_number
  region
  extraction_method
  model_version
  created_at
```

Extraction methods include `native_pdf`, `ocr`, `docx_parser`, `xml_parser`, and `qwen3_vl`.

Confidence below the configured threshold produces `needs_manual_review`. The source location is retained for officer inspection. Qwen3-VL must return a validated structured schema; free-form model text must not enter the rule engine directly.

## 11. Tender requirement indexing

Each published tender is converted into versioned, searchable requirements:

1. Parse tender documents into sections and clauses.
2. Split them into meaningful chunks without losing clause boundaries.
3. Assign stable requirement identifiers.
4. Generate embeddings using the configured embedding model.
5. Store the embeddings using pgvector.
6. Link every record to its tender and rule-set version.

```text
TenderRequirement
  id
  tender_id
  rule_set_version
  clause_reference
  requirement_type
  requirement_text
  normalized_requirement
  source_document_id
  page_number
  embedding
  embedding_model
  embedding_version
  created_at
```

Published requirements are immutable. Updating a tender creates a new version instead of silently replacing previous requirements.

## 12. Vector retrieval with pgvector

For each bidder evidence unit, the retrieval service:

1. Creates a query using the evidence and document context.
2. Generates an embedding.
3. Searches pgvector for similar tender requirements.
4. Filters candidates by the selected tender and rule-set version.
5. Retrieves multiple candidates rather than accepting the top result automatically.
6. Applies similarity and relevance thresholds.
7. Passes valid candidates to the comparison stage.

```text
RetrievalCandidate
  requirement_id
  bidder_evidence_id
  similarity_score
  retrieval_rank
  embedding_model
  embedding_version
  retrieved_at
```

Vector retrieval is candidate discovery only. Similarity does not establish compliance. If no candidate passes the threshold, the result becomes `no_reliable_match` or `needs_manual_review`; the system must not force a match.

## 13. Qwen3-VL comparison

Qwen3-VL compares original bidder evidence with retrieved tender requirements. Its input may include the relevant page or image region, extracted text, structured fields, the retrieved clause, its requirement identifier, permitted portal evidence, and a strict output schema.

Example output:

```json
{
  "requirement_id": "REQ-012",
  "bidder_evidence_id": "EVID-104",
  "comparison": "match",
  "extracted_value": "Example value",
  "expected_value": "Example requirement",
  "explanation": "The submitted certificate contains the required value.",
  "document_evidence": {
    "document_id": "DOC-008",
    "page": 3,
    "region": "x1,y1,x2,y2"
  },
  "model_confidence": 0.91
}
```

Allowed comparison states are `match`, `mismatch`, `partial`, `conflicting`, `uncertain`, and `no_evidence`.

The comparison service must:

- Validate responses against a schema.
- Reject missing or invalid evidence references.
- Reject requirement IDs not supplied to the model.
- Store the model and prompt-template versions.
- Preserve retrieval candidates and page/region provenance.
- Apply confidence thresholds.
- Return `uncertain` when evidence is insufficient.

The model may compare and explain evidence. It may not make the final qualification or disqualification decision.

## 14. Portal adapter boundary

Portal adapters validate selected claims against external evidence. During the hackathon they are deterministic mocks or authorized sandboxes and are labelled as such in the dashboard and output.

Example:

```text
Document GSTIN claim
        |
        v
Mock GST portal adapter
        |
        v
Registration status and registered entity
        |
        v
Normalized EvidenceResult
```

The rule engine consumes a shared contract:

```text
EvidenceResult
  source
  source_type
  subject_identifier
  attribute
  value
  status
  retrieved_at
  reference
  raw_evidence_location
```

Evidence statuses are `verified`, `inconsistent`, `unavailable`, and `needs_manual_review`.

Timeouts, invalid responses, and exhausted retries resolve to `unavailable`. They never produce implicit verification or automatic disqualification.

## 15. Rules and findings

Tender rules are deterministic and versioned. A published rule cannot be edited in place; changes create a new rule-set version. Every verification run captures the exact version before processing.

Rules may evaluate required-document presence, extracted values, cross-document identifier consistency, Qwen3-VL comparisons, retrieval confidence, portal evidence, certificate dates, eligibility thresholds, blacklist evidence, and manual-review conditions.

Example:

```text
Rule ID: GST-IDENTITY-01

IF:
  GST certificate is present
  AND extracted GSTIN confidence meets the threshold
  AND mock portal evidence is available
  AND document GSTIN equals portal GSTIN
  AND registered business names are consistent

THEN:
  status = verified

ELSE IF identifiers conflict:
  status = inconsistent

ELSE:
  status = needs_manual_review
```

```text
Finding
  id
  case_id
  verification_run_id
  rule_id
  rule_set_version
  status
  severity
  explanation
  evidence_refs[]
  retrieval_refs[]
  comparison_ref
  portal_evidence_refs[]
  created_at
```

Finding statuses are `verified`, `missing`, `inconsistent`, `not_applicable`, `unavailable`, and `needs_manual_review`. Severities are `informational`, `low`, `medium`, `high`, and `critical`.

Every finding must be explainable using stored evidence. A model-generated claim without evidence cannot become a verified finding.

## 16. Scoring and risk

Scoring is deterministic and derived from versioned rules and findings. The scoring service defines rule weight, severity, mandatory status, score contribution, risk contribution, critical caps, and manual-review behavior.

`not_applicable` does not reduce the score. Unavailable, conflicting, uncertain, or low-confidence evidence cannot be treated as verified. Critical unresolved conditions may apply a documented score cap. The calculation must be reproducible without calling Qwen3-VL.

## 17. Recommendations

The recommendation service receives only validated rules, findings, evidence references, score, risk, and unresolved conditions.

It may return `qualify`, `request_clarification`, `manual_review`, or `consider_disqualification`, citing the supporting findings.

It must not invent evidence, override deterministic findings, present its output as a final government decision, or record an officer decision. A template-based recommendation is acceptable for the MVP. If an AI writer is used, its output must remain grounded in validated findings.

## 18. Officer decision

Only an authenticated Procurement Officer records the final decision.

```text
OfficerDecision
  id
  case_id
  actor_id
  action
  reason
  finding_refs[]
  created_at
```

Allowed actions are `qualify`, `disqualify`, `request_clarification`, and `manual_review`.

Actor identity comes from the authenticated session, not an arbitrary dashboard value. Decisions are immutable. A changed decision creates a new record and audit event.

## 19. Persistence

PostgreSQL stores users, roles, tenders, versions, rule sets, requirements, cases, documents, extracted fields, embeddings, retrieval candidates, Qwen3-VL comparisons, portal evidence, findings, scores, risks, recommendations, officer decisions, audit events, and verification runs.

pgvector stores embeddings for tender requirements and permitted bidder-evidence chunks.

Encrypted S3-compatible object storage holds originals, derived page images, OCR output, cropped evidence regions, protected model-input artifacts, and retained adapter evidence. Database records store opaque object keys rather than public URLs.

## 20. Audit trail

Audit events are insert-only:

```text
AuditEvent
  event_id
  case_id
  actor_or_service
  action
  timestamp
  correlation_id
  payload
  payload_hash
  previous_event_hash
  event_hash
```

The previous-event hash creates a chain that makes silent modification more detectable. Corrections append a new event; existing audit events are not updated or deleted through normal operations.

Audited actions include case creation, upload, processing, extraction, retrieval, AI comparison, portal lookup, finding creation, scoring, recommendation generation, officer decision, and decision revision.

## 21. End-to-end workflow

1. An authenticated officer creates a case.
2. The officer selects a published tender and rule-set version.
3. The officer uploads a synthetic bidder document package.
4. The API validates, checksums, and stores each file, records metadata, appends an audit event, and queues processing.
5. The worker scans and classifies each document.
6. Native parsers, OCR, or Qwen3-VL extract fields with page and region provenance.
7. The system normalizes identifiers, names, dates, amounts, and certificate references.
8. The system creates embeddings for relevant bidder evidence.
9. pgvector retrieves multiple candidate requirements from the selected tender version.
10. Thresholds remove unreliable candidates; absent reliable matches go to manual review.
11. Qwen3-VL compares original evidence against retrieved requirements.
12. The comparison service validates the structured response, evidence references, and confidence.
13. When required, normalized identifiers are sent to labelled mock or sandbox portal adapters.
14. Adapter responses are converted into `EvidenceResult` records.
15. The deterministic rule engine evaluates document evidence, retrieval results, model comparisons, and portal evidence.
16. The scoring service calculates score and risk.
17. The recommendation service produces an evidence-linked recommendation.
18. The dashboard presents evidence, matched clauses, comparisons, portal results, findings, score, risk, and recommendation.
19. The officer reviews the evidence and records a final decision with a reason.
20. The API stores the immutable decision and appends an audit event.

## 22. Lifecycle and failure semantics

```text
draft -> uploaded -> queued -> processing -> ready_for_review -> decided
                       |            |
                       +----------> needs_manual_review
```

Documents and processing stages maintain separate statuses so individual failures are visible. `needs_manual_review` is a valid reviewable outcome, not a generic error.

Operations use bounded retries. After exhaustion, the system records the failed stage, affected document or source, failure category, retry eligibility, and required officer action. Mandatory incomplete processing must never appear successfully verified.

## 23. Security and privacy invariants

- Use synthetic data in fixtures, tests, screenshots, logs, and commits.
- Encrypt transport and stored objects.
- Keep secrets in environment-managed storage.
- Apply least privilege to databases, queues, model runtimes, and storage.
- Authorize every case, evidence, document, download, and decision operation.
- Minimize sensitive content in logs, prompts, embeddings, adapter calls, and audit payloads.
- Use scoped, expiring links for protected artifacts.
- Clearly label demo-only scanners and adapters.
- Treat instructions found inside bidder documents as untrusted document content, never system instructions.
- Validate every model response before use.
- Record model, embedding, and prompt versions for reproducibility.
- Do not scrape government portals without authorization.
- Define retention and deletion policies before processing real bidder data.

## 24. Testing contract

Minimum verification includes:

- API formatting, linting, authentication, authorization, lifecycle, decisions, and audit tests.
- Extraction tests for PDFs, OCR, DOCX, XML, Qwen3-VL schemas, confidence, and provenance.
- Retrieval tests for chunking, embeddings, version filtering, top-k search, thresholds, and no-match behavior.
- Comparison tests for matches, mismatches, partial matches, conflicts, uncertainty, invalid responses, unsupported requirements, missing evidence references, and document prompt injection.
- Adapter contract tests for verified, inconsistent, unavailable, timeout, invalid-response, and retry-exhaustion outcomes.
- Rule and scoring tests for missing documents, identity mismatches, expiry, blacklist hits, unavailable sources, score caps, `not_applicable`, and manual review.
- Integration and end-to-end tests from upload through an authenticated officer decision.
- Idempotency, recommendation-grounding, and audit-trail tests.

Synthetic scenarios include:

1. Compliant bidder
2. Missing mandatory document
3. Identity mismatch
4. Blacklist/debarment hit
5. Low-confidence extraction
6. No reliable vector match
7. Conflicting AI and portal evidence
8. Portal unavailable

## 25. Hackathon MVP scope

The hackathon MVP prioritizes a polished vertical workflow:

- PDF and image uploads
- Native extraction plus Qwen3-VL
- One embedding model
- PostgreSQL with pgvector
- Three to five versioned compliance rules
- Two or three deterministic mock portal adapters
- Four primary synthetic scenarios
- Evidence-linked findings
- Deterministic score and risk
- Grounded recommendation
- Officer-recorded decision
- Visible audit trail

Post-hackathon extensions may include complete DOCX/XML support, a distributed queue, production object storage and malware scanning, additional portal adapters, large-scale retrieval evaluation, optimized model serving, and authorized government APIs.

## 26. Evaluation metrics

The demo should measure:

- Field-extraction accuracy
- Requirement-retrieval recall at top-k
- Comparison accuracy
- Percentage of findings with valid evidence references
- Manual-review rate
- Average processing time per bidder package
- Unsupported model claims
- Agreement with expected synthetic outcomes
- Estimated reduction in officer review time

Evaluation must use synthetic documents with known expected results.

## 27. Recommended implementation order

1. Scaffold FastAPI, Next.js, PostgreSQL, and pgvector.
2. Define cases, documents, tenders, requirements, runs, lifecycle states, and API schemas.
3. Create synthetic bidder packages and expected outcomes.
4. Implement secure intake and storage.
5. Implement native extraction, OCR, and Qwen3-VL structured extraction.
6. Implement tender chunking, embeddings, pgvector indexing, and top-k retrieval.
7. Implement Qwen3-VL comparison with strict schemas and confidence handling.
8. Implement normalized mock or sandbox portal adapters.
9. Implement deterministic rules, findings, scoring, and risk.
10. Implement grounded recommendations.
11. Build the officer review and decision workflow.
12. Add append-only, hash-chained auditing.
13. Add integration and end-to-end tests.
14. Measure retrieval, extraction, comparison, and workflow performance.
15. Harden and rehearse the hackathon demonstration.

Do not bypass a safety invariant to begin a later implementation stage. Update [progress.md](progress.md) whenever a milestone is completed or materially changed.
