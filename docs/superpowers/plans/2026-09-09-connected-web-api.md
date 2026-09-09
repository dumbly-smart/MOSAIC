# Connected Web API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax.

**Goal:** Build a secure officer workflow that logs in through the existing FastAPI API, uploads PDFs, runs verification, and renders grounded results.

**Architecture:** A typed browser client owns documented request construction and guards the public schema's intentionally untyped nested result. Client components compose login, case intake, upload, polling, and results; session storage holds only the access token. Vitest covers transport/component states and Playwright drives a browser flow with complete synthetic API-contract responses.

**Tech Stack:** Next.js 16, React 19, TypeScript, Vitest, Testing Library, Playwright, existing FastAPI.

**Spec:** docs/superpowers/specs/2026-09-09-connected-web-api-design.md

## Global Constraints

- Use NEXT_PUBLIC_MOSAIC_API_URL; never hardcode an API URL or expose Supabase, database, storage, or server-secret credentials.
- Persist only access_token in browser sessionStorage; never persist passwords or refresh tokens.
- Accept application/pdf only. The server remains authoritative for configured size and PDF-header validation.
- The present API does not supply risk. Render “Risk: Not supplied by this run”; do not derive it.
- Final qualification, disqualification, and clarification decisions remain with a Procurement Officer. Identify this as local/mock-sandbox, never a live portal integration.
- Use synthetic fixtures only. Do not commit .env, uploads, .next, node_modules, .venv, .superpowers, credentials, or models.

---

## File Structure

- web/lib/mosaic-api.ts: public API types, runtime report guards, fetch client, normalized errors.
- web/lib/officer-session.ts: session-only access-token lifecycle.
- web/components/officer-login.tsx: synthetic officer sign-in.
- web/components/document-intake.tsx: case form, PDF uploads, per-file state, run start.
- web/components/officer-workflow.tsx: authenticated orchestration and polling lifecycle.
- web/components/verification-results.tsx: run status, advisory, score, evidence, safety boundary.
- web/**/*.test.tsx and web/**/*.test.ts: transport and component tests.
- web/vitest.config.ts, web/test/setup.ts, web/playwright.config.ts, web/e2e/officer-flow.spec.ts: test tooling and browser flow.
- web/app/page.tsx, web/app/government/page.tsx, web/app/bidder/page.tsx, web/app/results/page.tsx: connected-page composition and removal of fabricated results.
- web/.env.example and web/README.md: public URL and local stack instructions.

### Task 1: Set up web testing

**Files:**
- Modify: web/package.json and web/package-lock.json
- Create: web/vitest.config.ts, web/test/setup.ts, web/playwright.config.ts, web/test/smoke.test.ts

**Interfaces:**
- Produces npm run typecheck, npm test, and npm run test:e2e.
- Vitest uses jsdom and Testing Library matchers; Playwright starts Next at port 3000.

- [ ] **Step 1: Write the failing test**

~~~ts
import { expect, test } from 'vitest';

test('test environment exposes DOM matchers', () => {
  document.body.innerHTML = '<button>Open workspace</button>';
  expect(document.querySelector('button')).toHaveTextContent('Open workspace');
});
~~~

- [ ] **Step 2: Run it to verify red**

Run: cd web && npm test -- --run test/smoke.test.ts

Expected: FAIL because no test script/configuration exists.

- [ ] **Step 3: Implement the test harness**

Add scripts:

~~~json
{
  "typecheck": "tsc --noEmit",
  "test": "vitest run",
  "test:watch": "vitest",
  "test:e2e": "playwright test"
}
~~~

Install development dependencies vitest, jsdom, @testing-library/react, @testing-library/jest-dom, @testing-library/user-event, and @playwright/test. Configure Vitest to include **/*.test.{ts,tsx}, use jsdom, and load a setup module importing @testing-library/jest-dom/vitest. Configure Playwright with Chromium and an npm run dev web server.

- [ ] **Step 4: Verify green**

Run: cd web && npm test -- --run test/smoke.test.ts && npm run typecheck

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add web/package.json web/package-lock.json web/vitest.config.ts web/test/setup.ts web/playwright.config.ts web/test/smoke.test.ts
git commit -m "test: configure web component and browser tests"
~~~

### Task 2: Create the contract-grounded API client

**Files:**
- Create: web/lib/mosaic-api.ts
- Create: web/lib/mosaic-api.test.ts

**Interfaces:**
- Produces new MosaicApi(baseUrl, fetchImpl).
- Produces login, getMe, createCase, uploadDocument, listDocuments, startVerification, and getVerification.
- Produces ApiError { status, message } and asVerificationReport(value): VerificationReport | null.

- [ ] **Step 1: Write failing behavior tests**

The production changes that must make these tests fail are dropping bearer authorization, changing multipart kind, hardcoding a base URL, or trusting malformed nested results.

~~~ts
test('uploads bidder PDFs using bearer authorization and multipart kind', async () => {
  const request = await captureRequest(() =>
    api.uploadDocument('token-1', CASE_ID, 'bidder', pdfFile),
  );
  expect(request.headers.get('authorization')).toBe('Bearer token-1');
  expect((await request.formData()).get('kind')).toBe('bidder');
});

test('rejects malformed nested verification results', () => {
  expect(asVerificationReport({ score: 70, results: 'not-a-list' })).toBeNull();
});

test('uses the configured API base URL', async () => {
  await api.login('officer@example.test', 'correct-password');
  expect(fetchSpy).toHaveBeenCalledWith(
    'http://api.example.test/v1/auth/login',
    expect.anything(),
  );
});
~~~

Fixtures include every documented token, case, document, and run field—not partial mock data.

- [ ] **Step 2: Verify red**

Run: cd web && npm test -- --run lib/mosaic-api.test.ts

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement the minimum client**

Copy top-level types exactly from services/api/app/schemas.py. Trim the supplied base URL and throw a clear configuration error if empty. Send JSON to auth/case/run endpoints; send FormData without manually setting content type for uploads. Send bearer authorization to every protected route. Normalize JSON detail only when it is a string.

Guard the current local runner report:

~~~ts
type VerificationReport = {
  score: number;
  results: VerificationFinding[];
  review_required: boolean;
  clarification_required: boolean;
  unresolved_criteria: string[];
  recommendation: 'qualify' | 'request_clarification' | 'manual_review';
};
~~~

A guarded finding may expose criterion id, clause, status, reason, reason code, policy/rule version, evidence, and retrieval values. No risk type is introduced.

- [ ] **Step 4: Verify green**

Run: cd web && npm test -- --run lib/mosaic-api.test.ts && npm run typecheck && npm run lint

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add web/lib/mosaic-api.ts web/lib/mosaic-api.test.ts
git commit -m "feat: add contract-grounded Mosaic API client"
~~~

### Task 3: Add session-only synthetic officer login

**Files:**
- Create: web/lib/officer-session.ts and web/lib/officer-session.test.ts
- Create: web/components/officer-login.tsx and web/components/officer-login.test.tsx

**Interfaces:**
- Produces getAccessToken(), setAccessToken(token), and clearAccessToken() backed by session-storage key mosaic.access-token.
- Produces OfficerLogin with an API client and a verified UserResponse callback.

- [ ] **Step 1: Write failing tests**

~~~tsx
test('stores only the access token in session storage', () => {
  setAccessToken('access-123');
  expect(sessionStorage.getItem('mosaic.access-token')).toBe('access-123');
  expect(sessionStorage.getItem('refresh-token')).toBeNull();
});

test('shows rejected login without retaining a token', async () => {
  render(<OfficerLogin api={rejectingApi} onAuthenticated={vi.fn()} />);
  await userEvent.type(screen.getByLabelText('Email'), 'officer@example.test');
  await userEvent.type(screen.getByLabelText('Password'), 'incorrect');
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  expect(await screen.findByText('Invalid email or password')).toBeVisible();
  expect(sessionStorage.getItem('mosaic.access-token')).toBeNull();
});
~~~

- [ ] **Step 2: Verify red**

Run: cd web && npm test -- --run lib/officer-session.test.ts components/officer-login.test.tsx

Expected: FAIL because session and login code do not exist.

- [ ] **Step 3: Implement session/login**

Guard storage access for SSR. Call API login, store only access_token, then call getMe; clear storage if either call fails. Disable submit while pending. Clearly label synthetic local officer authentication and never render password values.

- [ ] **Step 4: Verify green**

Run: cd web && npm test -- --run lib/officer-session.test.ts components/officer-login.test.tsx && npm run typecheck && npm run lint

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add web/lib/officer-session.ts web/lib/officer-session.test.ts web/components/officer-login.tsx web/components/officer-login.test.tsx
git commit -m "feat: add session-only officer login"
~~~

### Task 4: Add case creation, PDF uploads, and run polling

**Files:**
- Create: web/components/document-intake.tsx and web/components/document-intake.test.tsx
- Create: web/components/officer-workflow.tsx and web/components/officer-workflow.test.tsx

**Interfaces:**
- Produces OfficerWorkflow.
- Produces DocumentIntake with API, token, case, and run-start callback.
- Starts with exactly { force_ocr_bidder: false, top_k: 5 } and polls queued/running runs only.

- [ ] **Step 1: Write failing state tests**

~~~tsx
test('rejects a non-PDF bidder file before upload', async () => {
  render(<DocumentIntake api={api} token="token" case={caseFixture} onRunStarted={vi.fn()} />);
  await userEvent.upload(
    screen.getByLabelText('Bidder PDFs'),
    new File(['text'], 'bidder.txt', { type: 'text/plain' }),
  );
  expect(screen.getByText('PDF files only')).toBeVisible();
});

test('shows a server upload failure on its tender file row', async () => {
  render(<DocumentIntake api={uploadRejectingApi} token="token" case={caseFixture} onRunStarted={vi.fn()} />);
  await userEvent.upload(screen.getByLabelText('Tender PDF'), pdfFile);
  await userEvent.click(screen.getByRole('button', { name: 'Upload documents' }));
  expect(await screen.findByText('Uploaded PDF exceeds the size limit')).toBeVisible();
});

test('polls queued work until the API reports needs manual review', async () => {
  render(<OfficerWorkflow api={queuedThenManualReviewApi} />);
  expect(await screen.findByText('Manual review required')).toBeVisible();
});
~~~

- [ ] **Step 2: Verify red**

Run: cd web && npm test -- --run components/document-intake.test.tsx components/officer-workflow.test.tsx

Expected: FAIL because connected workflow components do not exist.

- [ ] **Step 3: Implement the finite workflow**

Create a case from title/optional description before uploads. Track selected, uploading, uploaded, and failed files. Allow one tender and multiple bidders. Show server-confirmed filename, processing status, byte count, and per-row error; never call a selected file uploaded before its 201.

Enable start only after server-confirmed exactly one tender and at least one bidder. Surface API 409 as “Upload exactly one tender PDF and at least one bidder PDF first.” Poll at 1,500 ms with effect cleanup; stop on completed, failed, or needs_manual_review. On 401, clear session and return to login.

- [ ] **Step 4: Verify green**

Run: cd web && npm test -- --run components/document-intake.test.tsx components/officer-workflow.test.tsx && npm run typecheck && npm run lint

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add web/components/document-intake.tsx web/components/document-intake.test.tsx web/components/officer-workflow.tsx web/components/officer-workflow.test.tsx
git commit -m "feat: add case intake uploads and verification polling"
~~~

### Task 5: Render grounded run results safely

**Files:**
- Create: web/components/verification-results.tsx and web/components/verification-results.test.tsx
- Modify: web/components/officer-workflow.tsx

**Interfaces:**
- Produces VerificationResults consuming a run response and asVerificationReport.

- [ ] **Step 1: Write failing display tests**

~~~tsx
test('renders API evidence and advisory recommendation', () => {
  render(<VerificationResults run={completedRunWithEvidence} />);
  expect(screen.getByText('Primary requirement met.')).toBeVisible();
  expect(screen.getByText('GST certificate confirms registration')).toBeVisible();
  expect(screen.getByText('Advisory: qualify')).toBeVisible();
});

test('does not invent a risk rating', () => {
  render(<VerificationResults run={completedRunWithEvidence} />);
  expect(screen.getByText('Risk: Not supplied by this run')).toBeVisible();
});

test('shows manual-review without representing a final decision', () => {
  render(<VerificationResults run={manualReviewRun} />);
  expect(screen.getByText('Manual review required')).toBeVisible();
  expect(screen.getByText(/final qualification.*Procurement Officer/i)).toBeVisible();
});
~~~

- [ ] **Step 2: Verify red**

Run: cd web && npm test -- --run components/verification-results.test.tsx

Expected: FAIL because results component does not exist.

- [ ] **Step 3: Implement guarded rendering**

Render run status, score, policy version, and error message from the documented run response. For a guarded report, render advisory recommendation, result statuses, reasons, evidence source quote/document/page/line, and retrieval rank/similarity only when supplied. For absent/malformed result, render “Result details are unavailable; review the run metadata and source documents.” Do not add an officer decision control: the API has no decision endpoint.

- [ ] **Step 4: Verify green**

Run: cd web && npm test -- --run components/verification-results.test.tsx && npm run typecheck && npm run lint

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add web/components/verification-results.tsx web/components/verification-results.test.tsx web/components/officer-workflow.tsx
git commit -m "feat: render grounded verification results safely"
~~~

### Task 6: Integrate existing pages and local documentation

**Files:**
- Modify: web/app/page.tsx, web/app/government/page.tsx, web/app/bidder/page.tsx, web/app/results/page.tsx
- Create: web/app/government/page.test.tsx and web/.env.example
- Modify: web/README.md

**Interfaces:**
- GovernmentPage constructs MosaicApi from process.env.NEXT_PUBLIC_MOSAIC_API_URL ?? ''.
- Existing entry pages link to the connected workspace instead of displaying fabricated findings or portal integration claims.

- [ ] **Step 1: Write failing page test**

~~~tsx
test('officer workspace preserves authority and sandbox boundaries', () => {
  render(<GovernmentPage />);
  expect(screen.getByText(/final qualification.*Procurement Officer/i)).toBeVisible();
  expect(screen.getByText(/local\/mock-sandbox/i)).toBeVisible();
});
~~~

- [ ] **Step 2: Verify red**

Run: cd web && npm test -- --run app/government/page.test.tsx

Expected: FAIL because the current page is a disconnected publishing mockup.

- [ ] **Step 3: Compose connected pages**

Replace alerts and hard-coded results with the workflow or links back to it. Create web/.env.example containing:

~~~dotenv
NEXT_PUBLIC_MOSAIC_API_URL=http://127.0.0.1:8000
~~~

Document commands to configure the API according to docs/supabase-api-setup.md, create a synthetic local officer account, install API dependencies into ignored .venv, run uvicorn services.api.app.main:app --reload --host 127.0.0.1 --port 8000, then run npm run dev in web. State that no frontend secret is required.

- [ ] **Step 4: Verify green**

Run: cd web && npm test -- --run app/government/page.test.tsx && npm run lint && npm run typecheck && npm run build

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add web/app/page.tsx web/app/government/page.tsx web/app/bidder/page.tsx web/app/results/page.tsx web/app/government/page.test.tsx web/.env.example web/README.md
git commit -m "feat: connect officer dashboard to API workflow"
~~~

### Task 7: Drive synthetic browser flow and full verification

**Files:**
- Create: web/e2e/officer-flow.spec.ts
- Modify: web/README.md

**Interfaces:**
- Playwright routes documented API endpoints with complete synthetic responses and asserts request methods, bearer authorization, multipart kinds, and the poll ID.
- No live portal, real account, or uploaded fixture file is used.

- [ ] **Step 1: Write failing browser flow test**

~~~ts
test('officer completes the synthetic API-backed review flow', async ({ page }) => {
  await page.route('http://127.0.0.1:8000/**', documentedSyntheticApiRoute);
  await page.goto('/government');
  await page.getByLabel('Email').fill('officer@example.test');
  await page.getByLabel('Password').fill('correct-password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByLabel('Tender title').fill('Synthetic road works tender');
  await page.getByRole('button', { name: 'Create case' }).click();
  await page.getByLabel('Tender PDF').setInputFiles(syntheticTenderPdf);
  await page.getByLabel('Bidder PDFs').setInputFiles(syntheticBidderPdf);
  await page.getByRole('button', { name: 'Upload documents' }).click();
  await page.getByRole('button', { name: 'Start verification' }).click();
  await expect(page.getByText('Primary requirement met.')).toBeVisible();
  await expect(page.getByText(/final qualification.*Procurement Officer/i)).toBeVisible();
});
~~~

- [ ] **Step 2: Verify red**

Run: cd web && npx playwright test e2e/officer-flow.spec.ts

Expected: FAIL because the connected workflow does not exist.

- [ ] **Step 3: Implement synthetic route fixtures**

Return complete login, me, case, document, queued-run, and completed-run responses matching the API spec/current runner report. Assert Bearer valid-token after login, multipart tender and bidder kinds, and polling of the returned run ID. Create PDFs in Playwright's ephemeral test-upload API, not in public or Git.

- [ ] **Step 4: Run full verification**

~~~bash
cd web
npm run typecheck
npm run lint
npm test
npx playwright install chromium
npm run test:e2e
cd ..
.venv/bin/python -m unittest discover -s services/api/tests -v
~~~

Expected: all web checks pass. If backend collection remains blocked by dependencies missing from requirements-api.txt, install repository benchmark requirements into ignored .venv and report the requirements-file gap; do not skip or weaken the suite.

- [ ] **Step 5: Commit and inspect handoff**

~~~bash
git add web/e2e/officer-flow.spec.ts web/README.md
git commit -m "test: cover connected officer browser flow"
git status --short
git branch --show-current
git log --oneline main..HEAD
~~~

## Plan Self-Review

- Tasks 2, 4, 5, and 7 cover only verified endpoints and fields.
- Tasks 2–6 cover public environment configuration, session-only tokens, PDF intake, upload/run errors, manual-review handling, evidence/status/score/advisory display, and officer/mock-sandbox safety language.
- Task 7 supplies component, browser, lint, type, build, and backend test commands.
- No task adds an undocumented risk value or a nonexistent decision endpoint.
- The API-result type and component interfaces used by later tasks are introduced in Tasks 2–5.
