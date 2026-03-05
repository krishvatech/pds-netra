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
    <div className="rounded-2xl border border-white/15 bg-white/10 p-5 shadow-[0_28px_70px_-50px_rgba(2,6,23,0.9)] backdrop-blur-xl sm:p-8 [@media(max-height:700px)]:p-4">
      <div className="flex flex-col items-center gap-2 text-center sm:gap-3 [@media(max-height:700px)]:gap-1.5">
        <BrandLogo className="h-16 w-auto sm:h-20 md:h-24 [@media(max-height:700px)]:h-12" />
        <div className="space-y-2">
          <div className="text-[11px] font-semibold uppercase tracking-[0.35em] text-slate-300/80">
            Secure Access
          </div>
          <h1 className="text-2xl font-display text-slate-100 sm:text-3xl [@media(max-height:700px)]:text-xl">
            Digital Netra Command
          </h1>
          <p className="text-sm text-slate-400 [@media(max-height:700px)]:text-xs">Sign in to continue</p>
        </div>
      </div>

      <div className="mt-4 h-px w-full bg-white/10 sm:mt-6 [@media(max-height:700px)]:mt-3" />

      <form
        onSubmit={onSubmit}
        className="mt-4 space-y-4 sm:mt-6 sm:space-y-5 [@media(max-height:700px)]:mt-3 [@media(max-height:700px)]:space-y-3"
      >
        <div className="space-y-2">
          <label
            className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80 [@media(max-height:700px)]:text-[10px]"
            htmlFor="email"
          >
            Email
          </label>
          <input
            id="email"
            type="email"
            className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20 [@media(max-height:700px)]:py-2"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@digitalnetra.ai"
            required
          />
        </div>

        <div className="space-y-2">
          <label
            className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80 [@media(max-height:700px)]:text-[10px]"
            htmlFor="password"
          >
            Password
          </label>
          <PasswordInput
            id="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
            className="rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20 [@media(max-height:700px)]:py-2"
            required
          />
        </div>

        {error && <AlertBox variant="error">{error}</AlertBox>}
        {success && <AlertBox variant="success">{success}</AlertBox>}

        <button
          type="submit"
          className="btn-primary w-full rounded-full py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 [@media(max-height:700px)]:py-2"
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
