# MOSAIC Implementation Progress

Last updated: 2026-09-03

This file is the shared implementation ledger for humans and coding agents. Update it in the same commit as meaningful progress. Record only verified repository state—plans and intentions are not completed work.

## Status legend

- `[ ]` Not started
- `[~]` In progress; include the active branch or blocker in Notes
- `[x]` Completed and verified; include the verification evidence in Notes
- `[!]` Blocked; state the concrete dependency or decision required

## Current state

MOSAIC is in the documentation and architecture stage. The application, infrastructure, database schema, fixtures, and automated test suites have not been scaffolded. The next implementation task is Phase 1: repository and local-development scaffolding.

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
- [ ] Scaffold `services/api` with FastAPI and typed settings.
- [ ] Add PostgreSQL, S3-compatible storage, and queue services for local development.
- [ ] Add repeatable setup, formatting, linting, type-checking, and test commands.
- [ ] Add ignore rules for secrets, uploads, runtime storage, build output, and `.superpowers/` artifacts.
- [ ] Document environment variables with safe placeholder values.

Exit evidence: a clean checkout can start all services and run the initial API and web verification commands without real credentials or bidder data.

### Phase 2 — Domain contracts and synthetic fixtures

- [ ] Define case lifecycle, normalized evidence, findings, decisions, and audit event types.
- [ ] Define versioned tender rule and rule-set representations.
- [ ] Add database migrations for the core data model.
- [ ] Create synthetic compliant-bidder fixtures.
- [ ] Create synthetic missing-mandatory-document fixtures.
- [ ] Create synthetic identity-mismatch fixtures.
- [ ] Create synthetic blacklist/debarment-hit fixtures.

Exit evidence: schema/type tests and migrations pass, and fixture validation proves no real identifiers or uploaded documents are present.

### Phase 3 — Secure intake and extraction

- [ ] Enforce file extension, MIME, signature, and size allowlists.
- [ ] Add checksum creation and encrypted object-storage persistence.
- [ ] Define malware-scanner interface and labelled demo/test implementation.
- [ ] Implement PDF native text extraction with OCR fallback.
- [ ] Implement image OCR, DOCX paragraph/table parsing, and hardened XML parsing.
- [ ] Store confidence and exact source provenance for extracted fields.
- [ ] Fail closed to `needs_manual_review` for unsupported, unreadable, or uncertain input.

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
- [ ] Evaluate applicability and produce evidence-linked findings.
- [ ] Implement deterministic scoring, risk bands, and critical caps.
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

No executable project tooling exists yet. Phase 1 must replace this statement with exact commands for:

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

## Decisions

| Date | Decision | Reason |
|---|---|---|
| 2026-09-01 | Keep officer authority over all final outcomes | MOSAIC is decision support, not an autonomous procurement authority. |
| 2026-09-01 | Put portals behind normalized adapter interfaces | The engine remains independent of provider response formats and can fail closed. |
| 2026-09-01 | Use synthetic data and labelled mock/sandbox adapters for the MVP | Protects bidder data and avoids unsupported claims of government integration. |
| 2026-09-03 | Treat this file as the implementation status ledger | Agents and humans need one concise, evidence-based view of completed and remaining work. |

## Active work and blockers

- Active work: none after the documentation baseline is committed.
- Blockers: none for Phase 1 scaffolding.
- Next task: write and approve a test-first implementation plan for Phase 1 only.

## Update checklist

When changing this file:

1. Update the date and only the milestones affected by the change.
2. Link or name the tests and verification commands actually run.
3. Add architectural decisions only when they constrain future implementation.
4. Record blockers as concrete missing inputs, access, or decisions.
5. Keep sensitive bidder data, secrets, uploaded files, and unverifiable claims out of the ledger.
