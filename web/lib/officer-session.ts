const ACCESS_TOKEN_KEY = 'mosaic.access-token';

export function getAccessToken(): string | null {
  return storage()?.getItem(ACCESS_TOKEN_KEY) ?? null;
}

export function setAccessToken(token: string): void {
  storage()?.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  storage()?.removeItem(ACCESS_TOKEN_KEY);
}

function storage(): Storage | null {
  return typeof window === 'undefined' ? null : window.sessionStorage;
}
