'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import type { AlertItem, AlertStatus, VehicleGateSession } from '@/lib/types';
import { getAlerts, getVehicleGateSessions } from '@/lib/api';
import { getUser } from '@/lib/auth';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { formatUtc } from '@/lib/formatters';
import { friendlyErrorMessage } from '@/lib/friendly-error';

const tabs = [
  { key: 'open', label: 'Open Vehicles (Inside Godown)' },
  { key: 'alerts', label: 'Delay Alerts' }
] as const;

type TabKey = (typeof tabs)[number]['key'];
const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

const mockSessions: VehicleGateSession[] = [
  {
    id: 'VGS-001',
    godown_id: 'GDN_SAMPLE',
    anpr_camera_id: 'CAM_GATE_1',
    plate_raw: 'GJ01AB1234',
    plate_norm: 'GJ01AB1234',
    entry_at: new Date(Date.now() - 4 * 3600 * 1000).toISOString(),
    exit_at: null,
    status: 'OPEN',
    last_seen_at: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
    reminders_sent: { '3': new Date().toISOString() },
    age_hours: 4.2,
    next_threshold_hours: 6
  }
];

const mockAlerts: AlertItem[] = [
  {
    id: 'AL-001',
    godown_id: 'GDN_SAMPLE',
    godown_name: 'Pethapur',
    district: 'Gandhinagar',
    camera_id: 'CAM_GATE_1',
    alert_type: 'DISPATCH_MOVEMENT_DELAY',
    severity_final: 'warning',
    status: 'OPEN',
    start_time: new Date().toISOString(),
    summary: 'Vehicle entered but not exited after 6 hours',
    count_events: 1,
    key_meta: {
      plate_norm: 'GJ01AB1234',
      threshold_hours: 6,
      age_hours: 6.1,
      entry_at: new Date(Date.now() - 6 * 3600 * 1000).toISOString(),
      snapshot_url: '#'
    }
  }
];

export default function DispatchMovementPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('open');
  const [sessions, setSessions] = useState<VehicleGateSession[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [godownId, setGodownId] = useState('');
  const [plateQuery, setPlateQuery] = useState('');
  const [status, setStatus] = useState<AlertStatus | ''>('OPEN');
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

  const sessionsParams = useMemo(() => {
    const p: Record<string, any> = {
      page: 1,
      page_size: 100,
      status
    };
    if (godownId.trim()) p.godown_id = godownId.trim();
    if (plateQuery.trim()) p.q = plateQuery.trim();
    if (dateFrom) p.date_from = new Date(dateFrom).toISOString();
    if (dateTo) p.date_to = new Date(dateTo).toISOString();
    return p;
  }, [status, godownId, plateQuery, dateFrom, dateTo]);

  const alertParams = useMemo(() => {
    const p: Record<string, any> = {
      page: 1,
      page_size: 100,
      alert_type: 'DISPATCH_MOVEMENT_DELAY'
    };
    if (godownId.trim()) p.godown_id = godownId.trim();
    if (status) p.status = status;
    if (dateFrom) p.date_from = new Date(dateFrom).toISOString();
    if (dateTo) p.date_to = new Date(dateTo).toISOString();
    return p;
  }, [status, godownId, dateFrom, dateTo]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setError(null);
      try {
        if (MOCK_MODE) {
          if (mounted) {
            setSessions(mockSessions);
            setAlerts(mockAlerts);
          }
          return;
        }
        const [sessionsResp, alertsResp] = await Promise.all([
          getVehicleGateSessions(sessionsParams),
          getAlerts(alertParams)
        ]);
        if (mounted) {
          setSessions(sessionsResp.items ?? []);
          const items = Array.isArray(alertsResp) ? alertsResp : alertsResp.items ?? [];
          setAlerts(items);
        }
      } catch (e) {
        if (mounted)
          setError(
            friendlyErrorMessage(
              e,
              'Unable to load dispatch movement data. Please refresh or try again.'
            )
          );
      }
    })();
    return () => {
      mounted = false;
    };
  }, [sessionsParams, alertParams]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">Dispatch movement</div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Foodgrains Movement SLA
          </div>
          <div className="text-sm text-slate-300">
            Monitor vehicles that entered for loading and enforce exit SLAs.
          </div>
          <div className="text-xs text-slate-400">
            Data source: GATE_ANPR cameras only.
          </div>
        </div>
        <div className="intel-banner">Gate ANPR</div>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <Button
            key={tab.key}
            variant={activeTab === tab.key ? 'default' : 'outline'}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </Button>
        ))}
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
              <Label>Plate</Label>
              <Input value={plateQuery} onChange={(e) => setPlateQuery(e.target.value)} placeholder="GJ01AB" />
            </div>
            <div>
              <Label>Status</Label>
              <Select
                value={status}
                onChange={(e) => setStatus(e.target.value as AlertStatus | '')}
                options={[
                  { label: 'Open', value: 'OPEN' },
                  { label: 'Closed', value: 'CLOSED' },
                  { label: 'All', value: '' }
                ]}
              />
            </div>
            <div>
              <Label>Entry from</Label>
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
                    setDateNotice('Adjusted Entry to to keep the range valid.');
                  }
                }}
              />
            </div>
            <div>
              <Label>Entry to</Label>
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
                    setDateNotice('Adjusted Entry from to keep the range valid.');
                  }
                }}
              />
            </div>
          </div>
          {dateNotice && <div className="text-xs text-amber-300 mt-2">{dateNotice}</div>}
        </CardContent>
      </Card>

      {activeTab === 'open' && (
        <Card className="hud-card">
          <CardHeader>
            <div className="text-lg font-semibold font-display">Open vehicle sessions</div>
          </CardHeader>
          <CardContent>
            <div className="table-shell overflow-auto">
              <table className="min-w-[720px] text-sm">
                <thead>
                  <tr className="text-left text-slate-400">
                    <th className="py-2 pr-3">Plate</th>
                    <th className="py-2 pr-3">Entry time</th>
                    <th className="py-2 pr-3">Age (hrs)</th>
                    <th className="py-2 pr-3">Next reminder</th>
                    <th className="py-2 pr-3">Last seen</th>
                    <th className="py-2 pr-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.id} className="border-t border-white/10">
                      <td className="py-2 pr-3">{s.plate_norm}</td>
                      <td className="py-2 pr-3">{formatUtc(s.entry_at)}</td>
                      <td className="py-2 pr-3">{s.age_hours ?? '-'}</td>
                      <td className="py-2 pr-3">
                        {s.next_threshold_hours ? `${s.next_threshold_hours}h` : '-'}
                      </td>
                      <td className="py-2 pr-3">{formatUtc(s.last_seen_at)}</td>
                      <td className="py-2 pr-3">{s.status}</td>
                    </tr>
                  ))}
                  {sessions.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-slate-500">No open vehicle sessions.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === 'alerts' && (
        <Card className="hud-card">
          <CardHeader>
            <div className="text-lg font-semibold font-display">Dispatch delay alerts</div>
          </CardHeader>
          <CardContent>
            <div className="table-shell overflow-auto">
              <table className="min-w-[720px] text-sm">
                <thead>
                  <tr className="text-left text-slate-400">
                    <th className="py-2 pr-3">Time</th>
                    <th className="py-2 pr-3">Godown</th>
                    <th className="py-2 pr-3">Plate</th>
                    <th className="py-2 pr-3">Threshold</th>
                    <th className="py-2 pr-3">Age (hrs)</th>
                    <th className="py-2 pr-3">Evidence</th>
                    <th className="py-2 pr-3">Severity</th>
                    <th className="py-2 pr-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((a) => (
                    <tr key={a.id} className="border-t border-white/10">
                      <td className="py-2 pr-3">
                        <Link href={`/dashboard/alerts/${encodeURIComponent(a.id)}`} className="hover:underline">
                          {formatUtc(a.start_time)}
                        </Link>
                      </td>
                      <td className="py-2 pr-3">{a.godown_name ?? a.godown_id}</td>
                      <td className="py-2 pr-3">{a.key_meta?.plate_norm ?? '-'}</td>
                      <td className="py-2 pr-3">{a.key_meta?.threshold_hours ?? '-'}</td>
                      <td className="py-2 pr-3">{a.key_meta?.age_hours ?? '-'}</td>
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
                  {alerts.length === 0 && (
                    <tr>
                      <td colSpan={8} className="py-6 text-center text-slate-500">No delay alerts found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
