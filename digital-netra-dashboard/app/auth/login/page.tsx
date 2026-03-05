'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import type { FormEvent } from 'react';
import { AlertBox } from '@/components/ui/alert-box';
import { PasswordInput } from '@/components/ui/password-input';
import { ApiError, login } from '@/lib/api';
import { getSessionUser, setSession } from '@/lib/auth';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const resp = await login({ email, password });
      setSession(resp);
      await getSessionUser();
      setSuccess('Access granted. Redirecting to dashboard…');
      setTimeout(() => router.replace('/dashboard'), 800);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Invalid email or password. Please try again.');
      } else {
        setError('Unable to sign in right now. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="hud-card p-6 sm:p-8">
      <div className="space-y-2">
        <div className="hud-label">Secure Access</div>
        <h1 className="text-2xl font-display text-slate-100 sm:text-3xl">Digital Netra Login</h1>
        <p className="text-sm text-slate-400">Sign in with your verified email to continue.</p>
      </div>

      <form onSubmit={onSubmit} className="mt-8 space-y-5">
        <div className="space-y-2">
          <label className="hud-label" htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            className="input-field w-full"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@digitalnetra.ai"
            required
          />
        </div>

        <div className="space-y-2">
          <label className="hud-label" htmlFor="password">Password</label>
          <PasswordInput
            id="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
            required
          />
        </div>

        {error && <AlertBox variant="error">{error}</AlertBox>}
        {success && <AlertBox variant="success">{success}</AlertBox>}

        <button
          type="submit"
          className="btn-primary w-full"
          disabled={loading || !email || !password}
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>

        <div className="text-sm text-slate-400">
          New here?{' '}
          <Link href="/auth/signup" className="text-sky-400 underline">
            Create an account
          </Link>
        </div>
      </form>
    </div>
  );
}
