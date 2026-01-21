'use client';

import { useEffect, useMemo, useState } from 'react';
import { getHealthSummary } from '@/lib/api';
import type { HealthSummary } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table';
import { formatUtc } from '@/lib/formatters';
import { ErrorBanner } from '@/components/ui/error-banner';

function onlineBadge(online: boolean) {
  return online ? (
    <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200">Online</Badge>
  ) : (
    <Badge className="bg-red-100 text-red-800 border-red-200">Offline</Badge>
  );
}

export default function HealthPage() {
  const [summary, setSummary] = useState<HealthSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setError(null);
      try {
        const s = await getHealthSummary();
        if (mounted) setSummary(s);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load health');
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const rows = useMemo(() => summary?.recent_camera_status ?? [], [summary]);

  return (
    <Card className="animate-fade-up">
      <CardHeader>
        <div className="text-xl font-semibold font-display">System Health</div>
        <div className="text-sm text-slate-600">Camera and device status across godowns.</div>
        {summary && (
          <div className="text-xs uppercase tracking-[0.3em] text-slate-500">
            Updated {formatUtc(summary.timestamp_utc)}
          </div>
        )}
      </CardHeader>
      <CardContent>
        {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}
        {!summary && !error && <div className="text-sm text-slate-600">Loading…</div>}

        {summary && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4 stagger">
              <div className="p-4 rounded-xl glass-panel">
                <div className="text-xs text-slate-600">Godowns with camera issues</div>
                <div className="text-2xl font-semibold mt-1">{summary.godowns_with_issues}</div>
              </div>
              <div className="p-4 rounded-xl glass-panel">
                <div className="text-xs text-slate-600">Offline cameras</div>
                <div className="text-2xl font-semibold mt-1">{summary.offline_cameras}</div>
              </div>
              <div className="p-4 rounded-xl glass-panel">
                <div className="text-xs text-slate-600">Recent health events</div>
                <div className="text-2xl font-semibold mt-1">{summary.recent_health_events}</div>
              </div>
            </div>

            <div className="mb-2 text-sm font-semibold">Recent camera status</div>
            <div className="table-shell overflow-auto">
              <Table>
                <THead>
                  <TR>
                    <TH>Godown</TH>
                    <TH>Camera</TH>
                    <TH>Status</TH>
                    <TH>Last frame</TH>
                    <TH>Last tamper reason</TH>
                  </TR>
                </THead>
                <TBody>
                  {rows.length === 0 && (
                    <TR>
                      <TD colSpan={5} className="py-10 text-center text-slate-600">
                        No recent camera status available.
                      </TD>
                    </TR>
                  )}
                  {rows.map((r) => (
                    <TR key={`${r.godown_id}-${r.camera_id}`}>
                      <TD className="font-medium">{r.godown_id}</TD>
                      <TD>{r.camera_id}</TD>
                      <TD>{onlineBadge(r.online)}</TD>
                      <TD>{formatUtc(r.last_frame_utc)}</TD>
                      <TD>{r.last_tamper_reason ?? '-'}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
