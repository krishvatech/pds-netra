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
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { formatUtc } from '@/lib/formatters';

const tabs = [
  { key: 'person', label: 'Person After-hours', alertType: 'AFTER_HOURS_PERSON_PRESENCE' },
  { key: 'vehicle', label: 'Vehicle After-hours', alertType: 'AFTER_HOURS_VEHICLE_PRESENCE' }
] as const;

type TabKey = typeof tabs[number]['key'];
const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

const mockAlerts: AlertItem[] = [
  {
    id: 'AH-001',
    godown_id: 'GDN_SAMPLE',
    godown_name: 'Pethapur',
    district: 'Gandhinagar',
    camera_id: 'CAM_GATE_1',
    alert_type: 'AFTER_HOURS_PERSON_PRESENCE',
    severity_final: 'critical',
    status: 'OPEN',
    start_time: new Date().toISOString(),
    summary: 'After-hours person detected',
    count_events: 1,
    key_meta: {
      detected_count: 2,
      snapshot_url: '#'
    }
  }
];

export default function AfterHoursPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('person');
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [godownId, setGodownId] = useState('');
  const [status, setStatus] = useState<AlertStatus | ''>('OPEN');
  const [onlyOpen, setOnlyOpen] = useState(true);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!godownId) {
      const user = getUser();
      if (user?.godown_id) setGodownId(String(user.godown_id));
    }
  }, [godownId]);

  const alertType = useMemo(() => {
    const tab = tabs.find((t) => t.key === activeTab);
    return tab?.alertType ?? 'AFTER_HOURS_PERSON_PRESENCE';
  }, [activeTab]);

  const params = useMemo(() => {
    const p: Record<string, any> = {
      page: 1,
      page_size: 100,
      alert_type: alertType
    };
    if (godownId.trim()) p.godown_id = godownId.trim();
    if (status) p.status = status;
    if (onlyOpen) p.status = 'OPEN';
    if (dateFrom) p.date_from = new Date(dateFrom).toISOString();
    if (dateTo) p.date_to = new Date(dateTo).toISOString();
    return p;
  }, [alertType, godownId, status, onlyOpen, dateFrom, dateTo]);

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
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load after-hours alerts');
      }
    })();
    return () => {
      mounted = false;
    };
  }, [params]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">After-hours presence</div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            After-hours Violation Monitor
          </div>
          <div className="text-sm text-slate-300">Immediate alerts when people or vehicles appear after-hours.</div>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/dashboard/after-hours/policies" className="text-sm text-amber-300 hover:underline">
            Policy overrides
          </Link>
          <div className="intel-banner">High priority</div>
        </div>
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
              <Label>Date from</Label>
              <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </div>
            <div>
              <Label>Date to</Label>
              <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </div>
            <div className="flex items-end">
              <Button
                variant={onlyOpen ? 'default' : 'outline'}
                onClick={() => setOnlyOpen((prev) => !prev)}
              >
                {onlyOpen ? 'Only Open' : 'All Statuses'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">After-hours alerts</div>
        </CardHeader>
        <CardContent>
          <div className="table-shell overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400">
                  <th className="py-2 pr-3">Time</th>
                  <th className="py-2 pr-3">Godown</th>
                  <th className="py-2 pr-3">Camera</th>
                  <th className="py-2 pr-3">Count</th>
                  <th className="py-2 pr-3">Plate</th>
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
                    <td className="py-2 pr-3">{a.camera_id ?? '-'}</td>
                    <td className="py-2 pr-3">{a.key_meta?.detected_count ?? '-'}</td>
                    <td className="py-2 pr-3">{a.key_meta?.vehicle_plate ?? '-'}</td>
                    <td className="py-2 pr-3">
                      {a.key_meta?.snapshot_url ? (
                        <a className="text-amber-300 hover:underline" href={String(a.key_meta.snapshot_url)} target="_blank" rel="noreferrer">
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
                    <td colSpan={8} className="py-6 text-center text-slate-500">No alerts found.</td>
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
