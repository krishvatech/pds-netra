'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Check, Loader2, X } from 'lucide-react';
import { AlertBox } from '@/components/ui/alert-box';
import { BrandLogo } from '@/components/ui/brand-logo';
import { PasswordInput } from '@/components/ui/password-input';
import { ApiError, checkEmail, checkUsername, signup } from '@/lib/api';
import { setSession } from '@/lib/auth';

type FieldErrors = {
  email?: string;
  password?: string;
  confirmPassword?: string;
  general?: string;
};

type Availability = 'idle' | 'checking' | 'available' | 'taken' | 'error';

const passwordRules = [
  { id: 'min_length', label: 'At least 8 characters', test: (value: string) => value.length >= 8 },
  { id: 'uppercase', label: 'One uppercase letter', test: (value: string) => /[A-Z]/.test(value) },
  { id: 'lowercase', label: 'One lowercase letter', test: (value: string) => /[a-z]/.test(value) },
  { id: 'digit', label: 'One number', test: (value: string) => /\d/.test(value) },
  { id: 'special', label: 'One special character', test: (value: string) => /[^A-Za-z0-9]/.test(value) }
];

function AvailabilityBadge({ status }: { status: Availability }) {
  if (status === 'idle') return null;
  if (status === 'checking') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-slate-400/30 bg-slate-400/10 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-slate-200">
        <Loader2 size={12} className="animate-spin" />
        Checking
      </span>
    );
  }
  if (status === 'available') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/40 bg-emerald-400/10 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-emerald-200">
        <Check size={12} />
        Available
      </span>
    );
  }
  if (status === 'taken') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/40 bg-amber-400/10 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-amber-200">
        <X size={12} />
        Taken
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-slate-400/30 bg-slate-400/10 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-slate-200">
      Unavailable
    </span>
  );
}

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [emailStatus, setEmailStatus] = useState<Availability>('idle');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const passwordErrors = useMemo(
    () => passwordRules.filter((rule) => !rule.test(password)).map((rule) => rule.id),
    [password]
  );
  const passwordsMatch = confirmPassword.length === 0 || password === confirmPassword;
  const missingPasswordLabels = useMemo(
    () => passwordRules.filter((rule) => passwordErrors.includes(rule.id)).map((rule) => rule.label),
    [passwordErrors]
  );

  useEffect(() => {
    const trimmed = email.trim();
    if (!trimmed || !/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(trimmed)) {
      setEmailStatus('idle');
      return;
    }
    setEmailStatus('checking');
    const handle = setTimeout(async () => {
      try {
        const resp = await checkEmail(trimmed);
        setEmailStatus(resp.available ? 'available' : 'taken');
      } catch {
        setEmailStatus('error');
      }
    }, 500);
    return () => clearTimeout(handle);
  }, [email]);

  function normalizeUsername(value: string) {
    return value.toLowerCase().replace(/[^a-z0-9]/g, '');
  }

  async function allocateUsername() {
    const base = normalizeUsername(`${firstName}${lastName}`) || 'user';
    const candidates = [base, `${base}${Math.floor(Math.random() * 900 + 100)}`];
    for (const candidate of candidates) {
      try {
        const resp = await checkUsername(candidate);
        if (resp.available) return candidate;
      } catch {
        // ignore and try next
      }
    }
    return null;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setFieldErrors({});
    setSuccess(null);

    if (passwordErrors.length > 0) {
      setFieldErrors({ password: `Missing: ${missingPasswordLabels.join(', ')}.` });
      setLoading(false);
      return;
    }
    if (!passwordsMatch) {
      setFieldErrors({ confirmPassword: 'Passwords do not match.' });
      setLoading(false);
      return;
    }

    try {
      const username = await allocateUsername();
      if (!username) {
        setFieldErrors({ general: 'Unable to allocate a username. Please try again.' });
        setLoading(false);
        return;
      }
      const resp = await signup({
        username,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        password,
        confirm_password: confirmPassword
      });
      setSession(resp);
      setSuccess('Account created. Redirecting to login…');
      setTimeout(() => router.replace('/auth/login'), 900);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400 && err.body?.detail?.rules) {
        const rules = Array.isArray(err.body.detail.rules) ? err.body.detail.rules : [];
        const labels = passwordRules.filter((rule) => rules.includes(rule.id)).map((rule) => rule.label);
        setFieldErrors({ password: `Missing: ${labels.join(', ')}.` });
      } else if (err instanceof ApiError && err.status === 409) {
        const detail = err.body?.detail;
        if (detail === 'email_taken') {
          setFieldErrors({ email: 'Email already registered. Use another.' });
        } else {
          setFieldErrors({ general: 'Account already exists. Please sign in.' });
        }
      } else {
        setFieldErrors({ general: 'Unable to create account right now. Please try again.' });
      }
    } finally {
      setLoading(false);
    }
  }

  const disableSubmit =
    loading ||
    !firstName.trim() ||
    !lastName.trim() ||
    !email.trim() ||
    !password ||
    !confirmPassword ||
    emailStatus === 'taken';

  return (
    <div className="rounded-2xl border border-white/15 bg-white/10 p-6 shadow-[0_28px_70px_-50px_rgba(2,6,23,0.9)] backdrop-blur-xl sm:p-8">
      <div className="flex flex-col items-center gap-3 text-center">
        <BrandLogo className="h-24 w-auto" />
        <div className="space-y-2">
          <div className="text-[11px] font-semibold uppercase tracking-[0.35em] text-slate-300/80">
            Identity Setup
          </div>
          <h1 className="text-2xl font-display text-slate-100 sm:text-3xl">Create Digital Netra ID</h1>
          <p className="text-sm text-slate-400">Register to access the monitoring console.</p>
        </div>
      </div>

      <div className="mt-6 h-px w-full bg-white/10" />

      <form onSubmit={onSubmit} className="mt-6 space-y-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80" htmlFor="firstName">
              First Name
            </label>
            <input
              id="firstName"
              type="text"
              className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
              value={firstName}
              onChange={(event) => setFirstName(event.target.value)}
              placeholder="John"
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80" htmlFor="lastName">
              Last Name
            </label>
            <input
              id="lastName"
              type="text"
              className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
              value={lastName}
              onChange={(event) => setLastName(event.target.value)}
              placeholder="Duo"
              required
            />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80" htmlFor="email">
              Email
            </label>
            <AvailabilityBadge status={emailStatus} />
          </div>
          <input
            id="email"
            type="email"
            className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@digitalnetra.ai"
            required
          />
          {fieldErrors.email && (
            <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs sev-warning">
              {fieldErrors.email}
            </span>
          )}
        </div>

        <div className="space-y-2">
          <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80" htmlFor="password">
            Password
          </label>
          <PasswordInput
            id="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Create a strong password"
            className="rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
            required
          />
          {passwordErrors.length > 0 && (
            <div className="text-xs text-amber-200">Stronger password required.</div>
          )}
          {fieldErrors.password && (
            <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs sev-warning">
              {fieldErrors.password}
            </span>
          )}
        </div>

        <div className="space-y-2">
          <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80" htmlFor="confirmPassword">
            Confirm Password
          </label>
          <PasswordInput
            id="confirmPassword"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            placeholder="Re-enter password"
            className="rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
            required
          />
          {!passwordsMatch && (
            <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs sev-critical">
              Passwords do not match
            </span>
          )}
          {fieldErrors.confirmPassword && (
            <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs sev-critical">
              {fieldErrors.confirmPassword}
            </span>
          )}
        </div>

        {fieldErrors.general && <AlertBox variant="error">{fieldErrors.general}</AlertBox>}
        {success && <AlertBox variant="success">{success}</AlertBox>}

        <button
          type="submit"
          className="btn-primary w-full rounded-full py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60"
          disabled={disableSubmit}
        >
          {loading ? 'Creating account…' : 'Create account'}
        </button>

        <div className="text-sm text-slate-400">
          Already have access?{' '}
          <Link href="/auth/login" className="text-sky-300 underline decoration-sky-300/40 underline-offset-4">
            Sign in
          </Link>
        </div>
      </form>
    </div>
  );
}
