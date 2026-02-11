'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { register } from '@/lib/api';
import { getSessionUser, setSession } from '@/lib/auth';

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [role, setRole] = useState('USER');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (password !== confirm) {
        throw new Error('Passwords do not match');
      }
      const resp = await register(username, password, role);
      setSession(resp);
      await getSessionUser();
      router.replace('/dashboard/overview');
    } catch (err) {
      const message =
        err instanceof Error && err.message === 'Passwords do not match'
          ? err.message
          : friendlyErrorMessage(err, 'Check your inputs or try again.');
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell flex items-center justify-center px-6 py-12">
      <div className="app-bg" />
      <div className="app-grid" />
      <div className="pointer-events-none absolute -top-20 right-16 h-56 w-56 rounded-full bg-gradient-to-br from-amber-400/40 via-orange-400/30 to-transparent blur-3xl animate-float" />
      <div className="pointer-events-none absolute bottom-[-120px] left-[-80px] h-72 w-72 rounded-full bg-gradient-to-tr from-sky-400/40 via-blue-400/30 to-transparent blur-3xl animate-float" />
      <Card className="w-full max-w-md relative z-10 glass-panel-strong">
        <CardHeader>
          <div className="text-sm uppercase tracking-[0.3em] text-slate-500">Create Account</div>
          <div className="text-2xl font-semibold font-display">PDS Netra Command</div>
          <div className="text-sm text-slate-600">Register to continue</div>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="username">Username</Label>
              <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="e.g. operator1" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 6 characters" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="confirm">Confirm Password</Label>
              <Input id="confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Repeat password" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="role">Role</Label>
              <select
                id="role"
                className="w-full h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="USER">User</option>
                <option value="STATE_ADMIN">Admin</option>
              </select>
              <div className="text-xs text-slate-500">
                Admin accounts require an existing admin to create.
              </div>
            </div>

            {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-2">{error}</div>}

            <Button type="submit" className="w-full" disabled={loading || !username || !password || !confirm}>
              {loading ? 'Creating account...' : 'Create account'}
            </Button>

            <div className="text-xs text-slate-500">
              Already registered? <Link className="underline" href="/dashboard/login">Sign in</Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
