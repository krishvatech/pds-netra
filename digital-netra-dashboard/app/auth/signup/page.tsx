'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Check, Loader2, X } from 'lucide-react';
import { AlertBox } from '@/components/ui/alert-box';
import { PasswordInput } from '@/components/ui/password-input';
import { ApiError, checkEmail, checkUsername, signup } from '@/lib/api';
import { setSession } from '@/lib/auth';

type Availability = 'idle' | 'checking' | 'available' | 'taken' | 'error';

type FieldErrors = {
  username?: string;
  email?: string;
  general?: string;
};

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
      <span className="inline-flex items-center gap-1 rounded-full border border-slate-500/30 bg-slate-500/10 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-slate-300">
        <Loader2 size={12} className="animate-spin" />
        Checking
      </span>
    );
  }
  if (status === 'available') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-emerald-300">
        <Check size={12} />
        Available
      </span>
    );
  }
  if (status === 'taken') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/15 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-amber-300">
        <X size={12} />
        Taken
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-slate-500/30 bg-slate-500/10 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-slate-300">
      Unavailable
    </span>
  );
}

export default function SignupPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [usernameStatus, setUsernameStatus] = useState<Availability>('idle');
  const [emailStatus, setEmailStatus] = useState<Availability>('idle');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const passwordErrors = useMemo(
    () => passwordRules.filter((rule) => !rule.test(password)).map((rule) => rule.id),
    [password]
  );
  const passwordsMatch = confirmPassword.length === 0 || password === confirmPassword;

  useEffect(() => {
    if (!username.trim()) {
      setUsernameStatus('idle');
      return;
    }
    setUsernameStatus('checking');
    const handle = setTimeout(async () => {
      try {
        const resp = await checkUsername(username.trim());
        setUsernameStatus(resp.available ? 'available' : 'taken');
      } catch {
        setUsernameStatus('error');
      }
    }, 500);
    return () => clearTimeout(handle);
  }, [username]);

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

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setFieldErrors({});
    setSuccess(null);

    try {
      const resp = await signup({
        username: username.trim(),
        email: email.trim(),
        phone: phone.trim() || undefined,
        password,
        confirm_password: confirmPassword
      });
      setSession(resp);
      setSuccess('Account created. Redirecting to login…');
      setTimeout(() => router.replace('/auth/login'), 900);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const detail = err.body?.detail;
        if (detail === 'username_taken') {
          setFieldErrors({ username: 'Username already taken. Choose another.' });
        } else if (detail === 'email_taken') {
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
    !username.trim() ||
    !email.trim() ||
    passwordErrors.length > 0 ||
    !password ||
    !confirmPassword ||
    !passwordsMatch ||
    usernameStatus === 'taken' ||
    emailStatus === 'taken';

  return (
    <div className="hud-card p-6 sm:p-8">
      <div className="space-y-2">
        <div className="hud-label">Identity Setup</div>
        <h1 className="text-2xl font-display text-slate-100 sm:text-3xl">Create Digital Netra ID</h1>
        <p className="text-sm text-slate-400">Register to access the monitoring console.</p>
      </div>

      <form onSubmit={onSubmit} className="mt-8 space-y-5">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="hud-label" htmlFor="username">Username</label>
              <AvailabilityBadge status={usernameStatus} />
            </div>
            <input
              id="username"
              type="text"
              className="input-field w-full"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="operator-01"
              required
            />
            {fieldErrors.username && (
              <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs sev-warning">
                {fieldErrors.username}
              </span>
            )}
          </div>
          <div className="space-y-2">
            <label className="hud-label" htmlFor="phone">Phone</label>
            <input
              id="phone"
              type="tel"
              className="input-field w-full"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="+91 98765 43210"
            />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="hud-label" htmlFor="email">Email</label>
            <AvailabilityBadge status={emailStatus} />
          </div>
          <input
            id="email"
            type="email"
            className="input-field w-full"
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
          <label className="hud-label" htmlFor="password">Password</label>
          <PasswordInput
            id="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Create a strong password"
            required
          />
          <div className="space-y-1 text-xs text-slate-300">
            {passwordRules.map((rule) => {
              const met = rule.test(password);
              return (
                <div key={rule.id} className="flex items-center gap-2">
                  {met ? <Check size={14} className="text-emerald-400" /> : <X size={14} className="text-rose-400" />}
                  <span className={met ? 'text-emerald-300' : 'text-rose-300'}>{rule.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="space-y-2">
          <label className="hud-label" htmlFor="confirmPassword">Confirm Password</label>
          <PasswordInput
            id="confirmPassword"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            placeholder="Re-enter password"
            required
          />
          {!passwordsMatch && (
            <span className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs sev-critical">
              Passwords do not match
            </span>
          )}
        </div>

        {fieldErrors.general && <AlertBox variant="error">{fieldErrors.general}</AlertBox>}
        {success && <AlertBox variant="success">{success}</AlertBox>}

        <button type="submit" className="btn-primary w-full" disabled={disableSubmit}>
          {loading ? 'Creating account…' : 'Create account'}
        </button>

        <div className="text-sm text-slate-400">
          Already have access?{' '}
          <Link href="/auth/login" className="text-sky-400 underline">
            Sign in
          </Link>
        </div>
      </form>
    </div>
  );
}
