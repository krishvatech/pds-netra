'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import type { AlertItem, AlertStatus } from '@/lib/types';
import { getAlerts } from '@/lib/api';
import { getUser } from '@/lib/auth';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { ErrorBanner } from '@/components/ui/error-banner';
import { formatUtc } from '@/lib/formatters';
import { friendlyErrorMessage } from '@/lib/friendly-error';

const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

const mockAlerts: AlertItem[] = [
  {
    id: 'PROX-001',
    godown_id: 'GDN_SAMPLE',
    godown_name: 'Pethapur',
    district: 'Gandhinagar',
    camera_id: 'CAM_AISLE_2',
    alert_type: 'PROXIMITY_SOCIALIZING',
    severity_final: 'warning',
    status: 'OPEN',
    start_time: new Date().toISOString(),
    summary: 'Proximity socializing detected (group size 3)',
    count_events: 1,
    key_meta: {
      zone_id: 'AISLE_2',
      detected_count: 3,
      snapshot_url: '#'
    }
  }
];

export default function ProximitySocializingPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [godownId, setGodownId] = useState('');
  const [status, setStatus] = useState<AlertStatus | ''>('OPEN');
  const [minGroupSize, setMinGroupSize] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [dateNotice, setDateNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!godownId) {
      const user = getUser();
      if (user?.godown_id) setGodownId(String(user.godown_id));
    }
  }, [godownId]);

  const params = useMemo(() => {
    const p: Record<string, any> = {
      page: 1,
      page_size: 100,
      alert_type: 'PROXIMITY_SOCIALIZING'
    };
    if (godownId.trim()) p.godown_id = godownId.trim();
    if (status) p.status = status;
    if (dateFrom) p.date_from = new Date(dateFrom).toISOString();
    if (dateTo) p.date_to = new Date(dateTo).toISOString();
    return p;
  }, [godownId, status, dateFrom, dateTo]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setError(null);
      try {
        if (MOCK_MODE) {
          if (mounted) setAlerts(mockAlerts);
          return;
        }
        const resp = await getAlerts(params);
        const items = Array.isArray(resp) ? resp : resp.items ?? [];
        if (mounted) setAlerts(items);
      } catch (e) {
        if (mounted)
          setError(
            friendlyErrorMessage(
              e,
              'Unable to load proximity socializing alerts. Please refresh or check your connection.'
            )
          );
      }
    })();
    return () => {
      mounted = false;
    };
  }, [params]);

  const filteredAlerts = useMemo(() => {
    if (!minGroupSize) return alerts;
    const min = Number(minGroupSize);
    if (Number.isNaN(min)) return alerts;
    return alerts.filter((a) => {
      const count = a.key_meta?.detected_count ?? a.key_meta?.group_size;
      if (count === null || count === undefined) return false;
      return Number(count) >= min;
    });
  }, [alerts, minGroupSize]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">Proximity socializing</div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Proximity Socializing Monitor
          </div>
          <div className="text-sm text-slate-300">Detects groups staying too close beyond a threshold duration.</div>
        </div>
        <div className="intel-banner">Safety compliance</div>
      </div>

      {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Filters</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <div>
              <Label>Godown</Label>
              <Input value={godownId} onChange={(e) => setGodownId(e.target.value)} placeholder="Auto (from login)" />
            </div>
            <div>
              <Label>Status</Label>
              <Select
                value={status}
                onChange={(e) => setStatus(e.target.value as AlertStatus | '')}
                options={[
                  { label: 'All', value: '' },
                  { label: 'Open', value: 'OPEN' },
                  { label: 'Acknowledged', value: 'ACK' },
                  { label: 'Closed', value: 'CLOSED' }
                ]}
              />
            </div>
            <div>
              <Label>Min group size</Label>
              <Input value={minGroupSize} onChange={(e) => setMinGroupSize(e.target.value)} placeholder="2" />
            </div>
            <div>
              <Label>Date from</Label>
              <Input
                type="date"
                value={dateFrom}
                max={dateTo || undefined}
                onChange={(e) => {
                  const next = e.target.value;
                  setDateNotice(null);
                  setDateFrom(next);
                  if (next && dateTo && next > dateTo) {
                    setDateTo(next);
                    setDateNotice('Adjusted Date to to keep the range valid.');
                  }
                }}
              />
            </div>
            <div>
              <Label>Date to</Label>
              <Input
                type="date"
                value={dateTo}
                min={dateFrom || undefined}
                onChange={(e) => {
                  const next = e.target.value;
                  setDateNotice(null);
                  setDateTo(next);
                  if (dateFrom && next && next < dateFrom) {
                    setDateFrom(next);
                    setDateNotice('Adjusted Date from to keep the range valid.');
                  }
                }}
              />
            </div>
          </div>
          {dateNotice && <div className="text-xs text-amber-300 mt-2">{dateNotice}</div>}
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Proximity socializing alerts</div>
        </CardHeader>
        <CardContent>
          <div className="table-shell overflow-auto">
            <table className="min-w-[720px] text-sm">
              <thead>
                <tr className="text-left text-slate-400">
                  <th className="py-2 pr-3">Time</th>
                  <th className="py-2 pr-3">Godown</th>
                  <th className="py-2 pr-3">Camera</th>
                  <th className="py-2 pr-3">Zone</th>
                  <th className="py-2 pr-3">Group size</th>
                  <th className="py-2 pr-3">Summary</th>
                  <th className="py-2 pr-3">Evidence</th>
                  <th className="py-2 pr-3">Severity</th>
                  <th className="py-2 pr-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.map((a) => (
                  <tr key={a.id} className="border-t border-white/10">
                    <td className="py-2 pr-3">
                      <Link href={`/dashboard/alerts/${encodeURIComponent(a.id)}`} className="hover:underline">
                        {formatUtc(a.start_time)}
                      </Link>
                    </td>
                    <td className="py-2 pr-3">{a.godown_name ?? a.godown_id}</td>
                    <td className="py-2 pr-3">{a.camera_id ?? '-'}</td>
                    <td className="py-2 pr-3">{a.key_meta?.zone_id ?? '-'}</td>
                    <td className="py-2 pr-3">{a.key_meta?.detected_count ?? a.key_meta?.group_size ?? '-'}</td>
                    <td className="py-2 pr-3">{a.summary ?? '-'}</td>
                    <td className="py-2 pr-3">
                      {a.key_meta?.snapshot_url ? (
                        <a
                          className="inline-flex items-center gap-2 text-amber-300 hover:underline"
                          href={String(a.key_meta.snapshot_url)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <img
                            src={String(a.key_meta.snapshot_url)}
                            alt="Evidence snapshot"
                            className="h-10 w-16 rounded border border-white/10 object-cover"
                          />
                          Snapshot
                        </a>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="py-2 pr-3">{a.severity_final.toUpperCase()}</td>
                    <td className="py-2 pr-3">{a.status}</td>
                  </tr>
                ))}
                {filteredAlerts.length === 0 && (
                  <tr>
                    <td colSpan={9} className="py-6 text-center text-slate-500">
                      No proximity socializing alerts found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}