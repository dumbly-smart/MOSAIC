import { afterEach, expect, test } from 'vitest';

import { clearAccessToken, getAccessToken, setAccessToken } from './officer-session';

afterEach(() => clearAccessToken());

test('stores only the access token in session storage', () => {
  setAccessToken('access-123');

  expect(getAccessToken()).toBe('access-123');
  expect(sessionStorage.getItem('mosaic.access-token')).toBe('access-123');
  expect(sessionStorage.getItem('refresh-token')).toBeNull();
});
