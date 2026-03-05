'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import { ApiError, updateAccount } from '@/lib/api';
import { getSessionUser, setUser as persistUser } from '@/lib/auth';
import type { User } from '@/lib/types';

export default function AccountPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    async function guard() {
      const sessionUser = await getSessionUser();
      if (!sessionUser) {
        router.replace('/auth/login');
        return;
      }
      setUser(sessionUser);
      setFirstName(sessionUser.first_name ?? '');
      setLastName(sessionUser.last_name ?? '');
      setEmail(sessionUser.email ?? '');
      setPhone(sessionUser.phone ?? '');
    }
    guard();
  }, [router]);

  async function handleSave() {
    if (!user) return;
    setError(null);
    setSuccess(null);

    const trimmedFirst = firstName.trim();
    const trimmedLast = lastName.trim();
    const trimmedEmail = email.trim();
    const trimmedPhone = phone.trim();

    if (!trimmedFirst) {
      setError('First name is required.');
      return;
    }
    if (!trimmedLast) {
      setError('Last name is required.');
      return;
    }
    if (!trimmedEmail) {
      setError('Email is required.');
      return;
    }

    if (password || confirmPassword) {
      if (password !== confirmPassword) {
        setError('Passwords do not match.');
        return;
      }
    }

    const payload: {
      first_name: string;
      last_name: string;
      email: string;
      phone: string;
      password?: string;
      confirm_password?: string;
    } = {
      first_name: trimmedFirst,
      last_name: trimmedLast,
      email: trimmedEmail,
      phone: trimmedPhone
    };

    if (password) {
      payload.password = password;
      payload.confirm_password = confirmPassword;
    }

    try {
      setSaving(true);
      const updated = await updateAccount(payload);
      setUser(updated);
      persistUser(updated);
      setFirstName(updated.first_name ?? '');
      setLastName(updated.last_name ?? '');
      setEmail(updated.email ?? '');
      setPhone(updated.phone ?? '');
      setPassword('');
      setConfirmPassword('');
      setSuccess('Account updated successfully.');
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setError('Email already in use. Please choose another.');
        } else if (err.status === 400 && err.body?.detail?.rules) {
          setError('Password does not meet requirements. Please review and try again.');
        } else if (err.status === 400 && typeof err.body?.detail === 'string') {
          setError(err.body.detail);
        } else {
          setError('Unable to save changes. Please try again.');
        }
      } else {
        setError('Unable to save changes. Please try again.');
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="hud-pill">
          <span className="pulse-dot pulse-info" />
          Account
        </div>
        <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
          Account Settings
        </div>
        <div className="text-sm text-slate-300">
          Update your profile details and password. Account deactivation requires an administrator.
        </div>
      </div>

      <div className="hud-card p-6 space-y-6">
        {error && <AlertBox variant="error">{error}</AlertBox>}
        {success && <AlertBox variant="success">{success}</AlertBox>}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="hud-label" htmlFor="firstName">First name</label>
            <input
              id="firstName"
              type="text"
              className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
              placeholder="First name"
              value={firstName}
              onChange={(event) => setFirstName(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label className="hud-label" htmlFor="lastName">Last name</label>
            <input
              id="lastName"
              type="text"
              className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
              placeholder="Last name"
              value={lastName}
              onChange={(event) => setLastName(event.target.value)}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="hud-label" htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
              placeholder="email@digitalnetra.ai"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label className="hud-label" htmlFor="phone">Phone number</label>
            <input
              id="phone"
              type="tel"
              className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
              placeholder="+91 98765 43210"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="hud-label" htmlFor="password">New password</label>
            <input
              id="password"
              type="password"
              className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
              placeholder="••••••••"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label className="hud-label" htmlFor="confirmPassword">Confirm password</label>
            <input
              id="confirmPassword"
              type="password"
              className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn-primary rounded-full px-5 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            onClick={handleSave}
            disabled={saving || !user}
          >
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
