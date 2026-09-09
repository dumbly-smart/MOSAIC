export type CaseStatus = 'draft' | 'processing' | 'ready_for_review' | 'closed';
export type DocumentKind = 'tender' | 'bidder';
export type VerificationRunStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'needs_manual_review';

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

export type UserResponse = { id: string; email: string | null };

export type CaseResponse = {
  id: string;
  created_by: string;
  tender_title: string;
  description: string | null;
  status: CaseStatus;
  created_at: string;
  updated_at: string;
};

export type DocumentResponse = {
  id: string;
  case_id: string;
  kind: DocumentKind;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  processing_status: string;
  created_at: string;
};

export type VerificationRunResponse = {
  id: string;
  case_id: string;
  status: VerificationRunStatus;
  policy_version: string;
  score: number | null;
  result: unknown | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type VerificationFinding = {
  criterionId: string | null;
  clause: string | null;
  status: string | null;
  reason: string | null;
  reasonCode: string | null;
  policyVersion: string | null;
  ruleVersion: string | null;
  evidence: Evidence | null;
  retrieval: RetrievalEntry[];
};

export type Evidence = {
  sourceQuote: string | null;
  documentId: string | null;
  page: number | null;
  line: number | null;
};

export type RetrievalEntry = {
  rank: number | null;
  similarity: number | null;
  page: number | null;
  lineStart: number | null;
  lineEnd: number | null;
};

export type VerificationReport = {
  score: number;
  results: VerificationFinding[];
  review_required: boolean;
  clarification_required: boolean;
  unresolved_criteria: string[];
  recommendation: 'qualify' | 'request_clarification' | 'manual_review';
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

type FetchImplementation = typeof fetch;

export class MosaicApi {
  private readonly baseUrl: string;

  constructor(baseUrl: string, private readonly fetchImpl: FetchImplementation = fetch) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  login(email: string, password: string): Promise<TokenResponse> {
    return this.request('/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
      headers: { 'Content-Type': 'application/json' },
    });
  }

  getMe(token: string): Promise<UserResponse> {
    return this.request('/v1/me', { headers: this.authHeaders(token) });
  }

  createCase(
    token: string,
    input: { tender_title: string; description?: string },
  ): Promise<CaseResponse> {
    return this.request('/v1/cases', {
      method: 'POST',
      headers: { ...this.authHeaders(token), 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
  }

  uploadDocument(
    token: string,
    caseId: string,
    kind: DocumentKind,
    file: File,
  ): Promise<DocumentResponse> {
    const form = new FormData();
    form.set('kind', kind);
    form.set('file', file);
    return this.request(`/v1/cases/${caseId}/documents`, {
      method: 'POST',
      headers: this.authHeaders(token),
      body: form,
    });
  }

  listDocuments(token: string, caseId: string): Promise<DocumentResponse[]> {
    return this.request(`/v1/cases/${caseId}/documents`, {
      headers: this.authHeaders(token),
    });
  }

  startVerification(token: string, caseId: string): Promise<VerificationRunResponse> {
    return this.request(`/v1/cases/${caseId}/verification-runs`, {
      method: 'POST',
      headers: { ...this.authHeaders(token), 'Content-Type': 'application/json' },
      body: JSON.stringify({ force_ocr_bidder: false, top_k: 5 }),
    });
  }

  getVerification(token: string, runId: string): Promise<VerificationRunResponse> {
    return this.request(`/v1/verification-runs/${runId}`, {
      headers: this.authHeaders(token),
    });
  }

  private authHeaders(token: string): HeadersInit {
    return { Authorization: `Bearer ${token}` };
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    if (!this.baseUrl) {
      throw new ApiError(0, 'MOSAIC API URL is not configured');
    }
    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}${path}`, init);
    } catch {
      throw new ApiError(0, 'Unable to reach the MOSAIC API');
    }
    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try {
        const body: unknown = await response.json();
        if (isRecord(body) && typeof body.detail === 'string') message = body.detail;
      } catch {
        // A non-JSON error remains a status-based error.
      }
      throw new ApiError(response.status, message);
    }
    return (await response.json()) as T;
  }
}

export function asVerificationReport(value: unknown): VerificationReport | null {
  if (!isRecord(value) || !Array.isArray(value.results)) return null;
  if (
    typeof value.score !== 'number' ||
    typeof value.review_required !== 'boolean' ||
    typeof value.clarification_required !== 'boolean' ||
    !Array.isArray(value.unresolved_criteria) ||
    !value.unresolved_criteria.every((item) => typeof item === 'string') ||
    !isRecommendation(value.recommendation)
  ) {
    return null;
  }
  return {
    score: value.score,
    results: value.results.map(asFinding),
    review_required: value.review_required,
    clarification_required: value.clarification_required,
    unresolved_criteria: value.unresolved_criteria,
    recommendation: value.recommendation,
  };
}

function asFinding(value: unknown): VerificationFinding {
  const finding = isRecord(value) ? value : {};
  return {
    criterionId: stringOrNull(finding.criterion_id),
    clause: stringOrNull(finding.clause),
    status: stringOrNull(finding.status),
    reason: stringOrNull(finding.reason),
    reasonCode: stringOrNull(finding.reason_code),
    policyVersion: stringOrNull(finding.policy_version),
    ruleVersion: stringOrNull(finding.rule_version),
    evidence: asEvidence(finding.evidence),
    retrieval: Array.isArray(finding.retrieval) ? finding.retrieval.map(asRetrieval) : [],
  };
}

function asEvidence(value: unknown): Evidence | null {
  if (!isRecord(value)) return null;
  return {
    sourceQuote: stringOrNull(value.source_quote),
    documentId: stringOrNull(value.document_id),
    page: numberOrNull(value.page),
    line: numberOrNull(value.line),
  };
}

function asRetrieval(value: unknown): RetrievalEntry {
  const entry = isRecord(value) ? value : {};
  return {
    rank: numberOrNull(entry.rank),
    similarity: numberOrNull(entry.similarity),
    page: numberOrNull(entry.page),
    lineStart: numberOrNull(entry.line_start),
    lineEnd: numberOrNull(entry.line_end),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isRecommendation(value: unknown): value is VerificationReport['recommendation'] {
  return value === 'qualify' || value === 'request_clarification' || value === 'manual_review';
}

function stringOrNull(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}
