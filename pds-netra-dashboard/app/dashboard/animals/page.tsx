'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import type { AlertItem } from '@/lib/types';
import { getAlerts } from '@/lib/api';
import { getUser } from '@/lib/auth';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { formatUtc } from '@/lib/formatters';

const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

const mockAlerts: AlertItem[] = [
  {
    id: 'AN-001',
    godown_id: 'GDN_SAMPLE',
    godown_name: 'Pethapur',
    district: 'Gandhinagar',
    camera_id: 'CAM_GATE_1',
    alert_type: 'ANIMAL_INTRUSION',
    severity_final: 'critical',
    status: 'OPEN',
    start_time: new Date().toISOString(),
    summary: 'Animal intrusion detected (cow)',
    count_events: 1,
    key_meta: {
      animal_species: 'cow',
      animal_count: 1,
      animal_confidence: 0.84,
      animal_is_night: true,
      snapshot_url: '#'
    }
  }
];

export default function AnimalsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [godownId, setGodownId] = useState('');
  const [species, setSpecies] = useState('');
  const [status, setStatus] = useState<string>('OPEN');
  const [onlyNight, setOnlyNight] = useState(true);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
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
      alert_type: 'ANIMAL_INTRUSION'
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
        if (mounted) setAlerts(resp.items ?? []);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load animal intrusion alerts');
      }
    })();
    return () => {
      mounted = false;
    };
  }, [params]);

  const filteredAlerts = useMemo(() => {
    const normalizedSpecies = species.trim().toLowerCase();
    return alerts.filter((alert) => {
      if (onlyNight && alert.key_meta?.animal_is_night !== true) return false;
      if (normalizedSpecies) {
        const value = String(alert.key_meta?.animal_species ?? '').toLowerCase();
        if (!value.includes(normalizedSpecies)) return false;
      }
      return true;
    });
  }, [alerts, species, onlyNight]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">Animal intrusion</div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Animal Intrusion Monitor
          </div>
          <div className="text-sm text-slate-300">Immediate alerts when animals enter sensitive zones.</div>
        </div>
        <div className="intel-banner">Night priority</div>
      </div>

      {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Filters</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
            <div>
              <Label>Godown</Label>
              <Input value={godownId} onChange={(e) => setGodownId(e.target.value)} placeholder="Auto (from login)" />
            </div>
            <div>
              <Label>Species</Label>
              <Input value={species} onChange={(e) => setSpecies(e.target.value)} placeholder="Cow / Dog" />
            </div>
            <div>
              <Label>Status</Label>
              <Select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
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
              <Button variant={onlyNight ? 'default' : 'outline'} onClick={() => setOnlyNight((prev) => !prev)}>
                {onlyNight ? 'Night only' : 'All hours'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Animal intrusion alerts</div>
        </CardHeader>
        <CardContent>
          <div className="table-shell overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400">
                  <th className="py-2 pr-3">Time</th>
                  <th className="py-2 pr-3">Godown</th>
                  <th className="py-2 pr-3">Camera</th>
                  <th className="py-2 pr-3">Species</th>
                  <th className="py-2 pr-3">Count</th>
                  <th className="py-2 pr-3">Night</th>
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
                    <td className="py-2 pr-3">{a.key_meta?.animal_species ?? '-'}</td>
                    <td className="py-2 pr-3">{a.key_meta?.animal_count ?? '-'}</td>
                    <td className="py-2 pr-3">
                      {a.key_meta?.animal_is_night === null || a.key_meta?.animal_is_night === undefined
                        ? '-'
                        : a.key_meta?.animal_is_night
                          ? 'Yes'
                          : 'No'}
                    </td>
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
                    <td colSpan={9} className="py-6 text-center text-slate-500">No animal intrusion alerts found.</td>
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
