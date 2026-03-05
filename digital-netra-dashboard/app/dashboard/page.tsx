'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import { getSessionUser } from '@/lib/auth';
import type { User } from '@/lib/types';

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    async function guard() {
      const sessionUser = await getSessionUser();
      if (!sessionUser) {
        router.replace('/auth/login');
        return;
      }
      setUser(sessionUser);
    }
    guard();
  }, [router]);

  return (
    <div className="space-y-6">
      {user && !user.is_active && (
        <AlertBox variant="warning">
          This account has been deactivated. Please contact an administrator to restore access.
        </AlertBox>
      )}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Live
          </div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Dashboard
          </div>
          <div className="text-sm text-slate-300">Live operational health and incident pressure.</div>
        </div>
        <div className="intel-banner">Updated Mar 5, 2026 · 2:45 PM IST</div>
      </div>

      <div className="metric-grid">
        <div className="hud-card p-5">
          <div className="hud-label">Total cameras</div>
          <div className="hud-value mt-2">24</div>
          <div className="text-xs text-slate-400 mt-2">Across all godowns</div>
        </div>
        <div className="hud-card p-5">
          <div className="hud-label">Active cameras</div>
          <div className="hud-value mt-2">21</div>
          <div className="text-xs text-slate-400 mt-2">Live feeds online</div>
        </div>
        <div className="hud-card p-5">
          <div className="hud-label">Cameras offline</div>
          <div className="hud-value mt-2">3</div>
          <div className="text-xs text-slate-400 mt-2">Needs attention</div>
        </div>
        <div className="hud-card p-5">
          <div className="hud-label">Open alerts</div>
          <div className="hud-value mt-2">7</div>
          <div className="text-xs text-slate-400 mt-2 flex items-center gap-2">
            <span>Critical 5</span>
            <span className="text-slate-500">•</span>
            <span>Warning 2</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="hud-card p-5 xl:col-span-2">
          <div className="text-lg font-semibold font-display">Incident queue</div>
          <div className="text-sm text-slate-400 mt-1">Highest severity alerts awaiting response.</div>
          <div className="mt-4 space-y-3">
            <div className="incident-card p-4 flex items-start justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Alert</div>
                <div className="text-base font-semibold text-slate-100">After-hours presence</div>
                <div className="text-xs text-slate-400 mt-1 flex flex-wrap items-center gap-2">
                  <span>Godown 12</span>
                  <span className="text-slate-500">•</span>
                  <span>2 min ago</span>
                </div>
              </div>
              <div className="hud-pill sev-critical">CRITICAL</div>
            </div>
            <div className="incident-card p-4 flex items-start justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Alert</div>
                <div className="text-base font-semibold text-slate-100">Camera tamper</div>
                <div className="text-xs text-slate-400 mt-1 flex flex-wrap items-center gap-2">
                  <span>Godown 08</span>
                  <span className="text-slate-500">•</span>
                  <span>11 min ago</span>
                </div>
              </div>
              <div className="hud-pill sev-warning">WARNING</div>
            </div>
          </div>
        </div>

        <div className="hud-card p-5">
          <div className="text-lg font-semibold font-display">System pulse</div>
          <div className="text-sm text-slate-400 mt-1">Live health rollup.</div>
          <div className="mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Edge devices online</span>
              <span className="font-semibold">58</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">MQTT backlog</span>
              <span className="font-semibold">0</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Alerts in last hour</span>
              <span className="font-semibold">9</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
