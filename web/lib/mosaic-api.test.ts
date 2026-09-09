import { describe, expect, test, vi } from 'vitest';

import { asVerificationReport, MosaicApi } from './mosaic-api';

const caseId = '11111111-1111-1111-1111-111111111111';
const pdfFile = new File(['%PDF-1.7\nsynthetic'], 'bidder.pdf', {
  type: 'application/pdf',
});

describe('MosaicApi', () => {
  test('uploads a bidder PDF with bearer authorization and the documented multipart kind', async () => {
    let receivedInit: RequestInit | undefined;
    const api = new MosaicApi('http://api.example.test', async (input, init) => {
      expect(input).toBe(`http://api.example.test/v1/cases/${caseId}/documents`);
      receivedInit = init;
      return Response.json({
        id: '22222222-2222-2222-2222-222222222222',
        case_id: caseId,
        kind: 'bidder',
        original_filename: 'bidder.pdf',
        content_type: 'application/pdf',
        size_bytes: 19,
        sha256: 'a'.repeat(64),
        processing_status: 'uploaded',
        created_at: '2026-09-09T00:00:00Z',
      }, { status: 201 });
    });

    await api.uploadDocument('token-1', caseId, 'bidder', pdfFile);

    expect(new Headers(receivedInit?.headers).get('authorization')).toBe('Bearer token-1');
    expect((receivedInit?.body as FormData).get('kind')).toBe('bidder');
  });

  test('uses the configured API base URL for login', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(Response.json({
      access_token: 'access-token',
      refresh_token: 'refresh-token',
      token_type: 'bearer',
      expires_in: 3600,
    }));
    const api = new MosaicApi('http://api.example.test/', fetchSpy);

    await api.login('officer@example.test', 'correct-password');

    expect(fetchSpy).toHaveBeenCalledWith(
      'http://api.example.test/v1/auth/login',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  test('rejects malformed nested verification results', () => {
    expect(asVerificationReport({ score: 70, results: 'not-a-list' })).toBeNull();
  });
});
