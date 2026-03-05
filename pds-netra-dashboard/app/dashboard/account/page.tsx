'use client';

import { useMemo } from 'react';
import { getUser } from '@/lib/auth';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

export default function AccountSettingsPage() {
  const user = useMemo(() => getUser(), []);

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <div className="hud-pill">Account settings</div>
        <h1 className="text-3xl font-semibold font-display tracking-tight text-slate-100">Manage your profile</h1>
        <p className="text-sm text-slate-300">Basic account details and role context for this session.</p>
      </div>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display text-slate-100">Profile</div>
          <div className="text-sm text-slate-300">Session-backed user info.</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 text-sm text-slate-200 md:grid-cols-2">
            <div><span className="text-slate-400">Name:</span> {user?.name ?? '-'}</div>
            <div><span className="text-slate-400">Username:</span> {user?.username ?? '-'}</div>
            <div><span className="text-slate-400">Role:</span> {user?.role ?? '-'}</div>
            <div><span className="text-slate-400">District:</span> {user?.district ?? '-'}</div>
            <div><span className="text-slate-400">Godown:</span> {user?.godown_id ?? '-'}</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
