'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { login } from '@/lib/api';
import { setSession } from '@/lib/auth';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const resp = await login(username, password);
      setSession(resp);
      router.replace('/dashboard/overview');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
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
          <div className="text-sm uppercase tracking-[0.3em] text-slate-500">Secure Access</div>
          <div className="text-2xl font-semibold font-display">PDS Netra Command</div>
          <div className="text-sm text-slate-600">Sign in to continue</div>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="username">Username</Label>
              <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="e.g. admin" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            </div>

            {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-2">{error}</div>}

            <Button type="submit" className="w-full" disabled={loading || !username || !password}>
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>

            <div className="text-xs text-slate-500">
              Tip: For PoC, backend may accept a demo account (ask your backend config).
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
