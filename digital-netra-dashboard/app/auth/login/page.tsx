'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import type { FormEvent } from 'react';
import { AlertBox } from '@/components/ui/alert-box';
import { BrandLogo } from '@/components/ui/brand-logo';
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
    <div className="rounded-2xl border border-white/15 bg-white/10 p-6 shadow-[0_28px_70px_-50px_rgba(2,6,23,0.9)] backdrop-blur-xl sm:p-8">
      <div className="flex flex-col items-center gap-3 text-center">
        <BrandLogo className="h-24 w-auto" />
        <div className="space-y-2">
          <div className="text-[11px] font-semibold uppercase tracking-[0.35em] text-slate-300/80">
            Secure Access
          </div>
          <h1 className="text-2xl font-display text-slate-100 sm:text-3xl">Digital Netra Command</h1>
          <p className="text-sm text-slate-400">Sign in to continue</p>
        </div>
      </div>

      <div className="mt-6 h-px w-full bg-white/10" />

      <form onSubmit={onSubmit} className="mt-6 space-y-5">
        <div className="space-y-2">
          <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@digitalnetra.ai"
            required
          />
        </div>

        <div className="space-y-2">
          <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80" htmlFor="password">
            Password
          </label>
          <PasswordInput
            id="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
            className="rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
            required
          />
        </div>

        {error && <AlertBox variant="error">{error}</AlertBox>}
        {success && <AlertBox variant="success">{success}</AlertBox>}

        <button
          type="submit"
          className="btn-primary w-full rounded-full py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60"
          disabled={loading || !email || !password}
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>

        <div className="text-xs text-slate-400">
          New user?{' '}
          <Link href="/auth/signup" className="text-sky-300 underline decoration-sky-300/40 underline-offset-4">
            Create account
          </Link>
        </div>
      </form>
    </div>
  );
}
