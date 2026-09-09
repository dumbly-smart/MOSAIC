'use client';

import { FormEvent, useState } from 'react';

import { ApiError, TokenResponse, UserResponse } from '../lib/mosaic-api';
import { clearAccessToken, setAccessToken } from '../lib/officer-session';

type AuthApi = {
  login(email: string, password: string): Promise<TokenResponse>;
  getMe(token: string): Promise<UserResponse>;
};

export function OfficerLogin({
  api,
  onAuthenticated,
}: {
  api: AuthApi;
  onAuthenticated(user: UserResponse): void;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const session = await api.login(email, password);
      setAccessToken(session.access_token);
      const user = await api.getMe(session.access_token);
      setPassword('');
      onAuthenticated(user);
    } catch (reason) {
      clearAccessToken();
      setError(reason instanceof ApiError || reason instanceof Error ? reason.message : 'Sign-in failed');
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <p className="text-sm font-semibold text-blue-700">Synthetic local officer demo</p>
      <h1 className="mt-2 text-2xl font-bold text-slate-900">Officer sign in</h1>
      <p className="mt-2 text-sm text-slate-600">Use a local synthetic officer account. MOSAIC never receives Supabase service credentials in this browser.</p>
      <form className="mt-6 space-y-4" onSubmit={submit}>
        <label className="block text-sm font-medium text-slate-700">
          Email
          <input aria-label="Email" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          Password
          <input aria-label="Password" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>
        {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
        <button className="w-full rounded-lg bg-slate-900 px-4 py-2 font-semibold text-white disabled:bg-slate-400" type="submit" disabled={pending}>
          {pending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </section>
  );
}
