# Connected Web API Design

## Goal

Connect the existing Next.js officer dashboard in `web/` to the existing
FastAPI API in `services/api/`, providing an authenticated local demo from
case creation through document upload, verification polling, and grounded
review. MOSAIC remains officer decision support; it neither records an
officer decision through this flow nor presents an automated final decision.

## Verified API contract

The browser connects to the base URL provided by
`NEXT_PUBLIC_MOSAIC_API_URL`. It never receives Supabase database, storage,
or secret credentials. The API owns the Supabase Auth exchange and accepts
only an issued access token as `Authorization: Bearer <token>`.

| Operation | Request | Success response | Relevant failures |
| --- | --- | --- | --- |
| `POST /v1/auth/login` | JSON `{ email, password }`; email is 3–320 characters and password is 6–200 | `200` `{ access_token, refresh_token, token_type, expires_in }` | `401` invalid credentials; `503` verifier unavailable |
| `GET /v1/me` | Bearer token | `200` `{ id, email }` | `401` missing/invalid token |
| `POST /v1/cases` | Bearer token; JSON `{ tender_title, description? }`; title is 3–200, description at most 2,000 | `201` case `{ id, created_by, tender_title, description, status, created_at, updated_at }` | `401`, `422`, `503` database unavailable |
| `POST /v1/cases/{case_id}/documents` | Bearer token; multipart `kind` of `tender` or `bidder`, plus `file` | `201` document `{ id, case_id, kind, original_filename, content_type, size_bytes, sha256, processing_status, created_at }` | `400` empty/invalid PDF header; `413` too large; `415` non-PDF; `404` unknown case; `502` storage failure |
| `GET /v1/cases/{case_id}/documents` | Bearer token | `200` list of document responses | `404`, `401`, `503` |
| `POST /v1/cases/{case_id}/verification-runs` | Bearer token; JSON `{ force_ocr_bidder?: boolean, top_k?: 1..20 }` | `202` verification run | `409` until there is exactly one tender and at least one bidder PDF; `404`; `401`; `503` |
| `GET /v1/verification-runs/{run_id}` | Bearer token | `200` verification run | `404`; `401`; `503` |

The server accepts only `application/pdf`, rejects an empty body or one not
beginning `%PDF-`, and uses `MOSAIC_MAX_UPLOAD_BYTES` (50 MiB by default).
Because the configured value is not exposed by an endpoint, the UI will
communicate PDF-only intake and rely on the server as the authoritative size
check. It will display API errors verbatim only when safe and otherwise show a
plain action-oriented message.

A verification run has `{ id, case_id, status, policy_version, score, result,
error_message, created_at, started_at, completed_at }`. Its documented status
values are `queued`, `running`, `completed`, `failed`, and
`needs_manual_review`. `result` is deliberately typed as `dict` in the public
schema. The current local runner writes a report with `score`, `results`,
`review_required`, `clarification_required`, `unresolved_criteria`, and
`recommendation`, but those nested fields are not a Pydantic response schema.
Each current result has scoring/rule metadata, `status`, `reason`,
`reason_code`, `evidence`, and `retrieval`; evidence includes a source quote,
document id, and page or line when grounding succeeds.

The current API response does not provide `risk`. The frontend will not infer
or label a risk level as though it were API evidence. It will say that risk is
not supplied for this run. Adding a risk field requires an explicit backend
contract change, outside this frontend-connection feature.

## Architecture and flow

The existing presentation pages will become one client-side officer workflow,
with small focused modules for API transport, session state, workflow state,
and evidence rendering. The client stores only the access token in
`sessionStorage`; it does not store the refresh token, password, Supabase URL,
or any service credential. A page refresh may require another local demo
login, which is intentional for this limited session model.

1. The officer signs in with a synthetic local account. The client calls the
   API login route, keeps the access token in session storage, and gets `/v1/me`
   to display the authenticated officer identity.
2. The officer supplies a tender title (and optional description). The client
   creates one API case and holds its ID in workflow state.
3. The officer selects one tender PDF and one or more bidder PDFs. The client
   uploads the tender with `kind=tender` and each bidder with `kind=bidder`.
   Each row represents the server response, upload progress/state, or an
   actionable error. Client-side type checks accept only PDFs; the server
   remains authoritative for headers and size.
4. Once server-confirmed documents satisfy the run precondition, the officer
   starts a run with the API defaults `{ force_ocr_bidder: false, top_k: 5 }`.
   The client polls the documented run endpoint while status is `queued` or
   `running`, stops on `completed`, `failed`, or `needs_manual_review`, and
   permits a deliberate retry only by starting a new run.
5. The results view presents the returned run score, policy version, advisory
   recommendation, current finding result rows, and their groundable evidence
   / retrieval provenance. It renders manual-review and failure states without
   converting them into a qualification outcome.

All relevant screens carry the same boundary: “MOSAIC provides decision
support. A Procurement Officer makes and records the final qualification,
disqualification, or clarification decision.” They also identify the flow as
local/mock-sandbox only and never claim government-portal integration.

## Error handling

- Missing API URL: show configuration guidance and prevent requests.
- Login `401`: retain no token and show an invalid-credentials message.
- Authenticated `401`: clear the session token and require a new login.
- Create/upload/start/poll network or `5xx` failure: retain the safely known
  state and show a retry action.
- Upload `400`, `413`, or `415`: mark only the affected file as failed; do not
  mark it uploaded.
- `409` when starting: show the exact tender/bidder prerequisite.
- `needs_manual_review`: prominently stop polling and direct the officer to
  review the returned evidence; do not call it compliant or non-compliant.
- Unknown/malformed `result`: show its run metadata and a safe unavailable
  result panel rather than fabricate findings or evidence.

## Test strategy

- API-client unit tests prove request construction, bearer authorization,
  login-token handling, multipart document kinds, and normalized API errors.
- Component tests cover login failure, upload failure and success states,
  queued/running/failed/manual-review states, and evidence/status/recommendation
  displays based on complete synthetic API fixtures.
- A browser end-to-end local test starts a synthetic FastAPI test double or
  local API instance, signs in, creates a case, uploads synthetic PDFs, polls
  a completed run, and verifies the officer-boundary text and evidence.
- Existing FastAPI API tests remain part of verification. No actual personal,
  bidder, or portal data is introduced.

## File boundaries

- `web/lib/mosaic-api.ts`: typed API transport and response guards.
- `web/lib/officer-session.ts`: session-storage-only access-token lifecycle.
- `web/components/*`: testable login, intake, run-state, and evidence/result
  presentation components.
- `web/app/*`: page composition and navigation using the components.
- `web/**/*.test.tsx` and `web/**/*.test.ts`: synthetic client/component tests.
- `web/e2e/*`: local browser flow and its test fixture server setup.
- `web/.env.example` and `web/README.md`: public API URL and connected-stack
  instructions, without secrets.
