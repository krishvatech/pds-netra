'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';

import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { getCameras, getGodowns, getStationMonitoringAlerts } from '@/lib/api';
import { getUser } from '@/lib/auth';
import { formatUtc } from '@/lib/formatters';
import type { CameraInfo, GodownListItem, StationMonitoringAlertItem } from '@/lib/types';

export default function StationMonitoringPage() {
  const [alerts, setAlerts] = useState<StationMonitoringAlertItem[]>([]);
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [zoneOptions, setZoneOptions] = useState<string[]>([]);

  const [godownId, setGodownId] = useState('');
  const [cameraId, setCameraId] = useState('');
  const [zoneId, setZoneId] = useState('');
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

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const resp = await getGodowns({ page: 1, page_size: 200 });
        const items = Array.isArray(resp) ? resp : resp.items ?? [];
        if (mounted) setGodowns(items);
      } catch {
        if (mounted) setGodowns([]);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const items = await getCameras(godownId ? { godown_id: godownId } : undefined);
        if (mounted) {
          setCameras(items);
          if (cameraId && !items.find((c) => c.camera_id === cameraId)) {
            setCameraId('');
          }
        }
      } catch {
        if (mounted) setCameras([]);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [godownId, cameraId]);

  const params = useMemo(() => {
    const p: Record<string, string | number> = { page: 1, page_size: 200 };
    if (godownId) p.godown_id = godownId;
    if (cameraId) p.camera_id = cameraId;
    if (zoneId) p.zone_id = zoneId;
    if (dateFrom) p.from = new Date(`${dateFrom}T00:00:00`).toISOString();
    if (dateTo) p.to = new Date(`${dateTo}T23:59:59`).toISOString();
    return p;
  }, [godownId, cameraId, zoneId, dateFrom, dateTo]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setError(null);
      try {
        const resp = await getStationMonitoringAlerts(params);
        const items = resp.items ?? [];
        if (!mounted) return;
        setAlerts(items);
        const zones = new Set<string>();
        for (const item of items) {
          const z = item.zone_id || String((item.extra as any)?.workstation_zone_id || '');
          if (z) zones.add(z);
        }
        setZoneOptions(Array.from(zones).sort());
      } catch {
        if (mounted) setError('Unable to load station monitoring alerts.');
      }
    })();
    return () => {
      mounted = false;
    };
  }, [params]);

  const stats = useMemo(() => {
    const total = alerts.length;
    const byZone: Record<string, number> = {};
    const byCamera: Record<string, number> = {};
    for (const alert of alerts) {
      const z = alert.zone_id || String((alert.extra as any)?.workstation_zone_id || 'unknown');
      const c = alert.camera_id || 'unknown';
      byZone[z] = (byZone[z] ?? 0) + 1;
      byCamera[c] = (byCamera[c] ?? 0) + 1;
    }
    const topZones = Object.entries(byZone).sort((a, b) => b[1] - a[1]).slice(0, 3);
    const topCameras = Object.entries(byCamera).sort((a, b) => b[1] - a[1]).slice(0, 3);
    return { total, topZones, topCameras };
  }, [alerts]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">Workplace safety</div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Station Monitoring
          </div>
          <div className="text-sm text-slate-300">Workstation absence alerts by camera zone.</div>
        </div>
        <div className="intel-banner">Workstation compliance</div>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Filters</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <div>
              <Label>Godown</Label>
              <Select
                value={godownId}
                onChange={(e) => {
                  setGodownId(e.target.value);
                  setCameraId('');
                }}
                options={[
                  { label: 'All', value: '' },
                  ...godowns.map((g) => ({ label: `${g.name ?? g.godown_id}`, value: g.godown_id })),
                ]}
              />
            </div>
            <div>
              <Label>Camera</Label>
              <Select
                value={cameraId}
                onChange={(e) => setCameraId(e.target.value)}
                options={[
                  { label: 'All', value: '' },
                  ...cameras.map((c) => ({ label: c.label ?? c.camera_id, value: c.camera_id })),
                ]}
              />
            </div>
            <div>
              <Label>Zone</Label>
              <Select
                value={zoneId}
                onChange={(e) => setZoneId(e.target.value)}
                options={[
                  { label: 'All', value: '' },
                  ...zoneOptions.map((z) => ({ label: z, value: z })),
                ]}
              />
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

      <div className="metric-grid">
        <div className="hud-card p-5">
          <div className="hud-label">Total alerts</div>
          <div className="hud-value mt-2">{stats.total}</div>
        </div>
        <div className="hud-card p-5">
          <div className="hud-label">Top zones</div>
          <div className="text-sm text-slate-200 mt-2">
            {stats.topZones.length === 0
              ? '-'
              : stats.topZones.map(([zone, count]) => `${zone} (${count})`).join(', ')}
          </div>
        </div>
        <div className="hud-card p-5">
          <div className="hud-label">Top cameras</div>
          <div className="text-sm text-slate-200 mt-2">
            {stats.topCameras.length === 0
              ? '-'
              : stats.topCameras.map(([cam, count]) => `${cam} (${count})`).join(', ')}
          </div>
        </div>
      </div>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Station Monitoring Incidents</div>
        </CardHeader>
        <CardContent>
          <div className="table-shell overflow-auto">
            <table className="min-w-[900px] text-sm">
              <thead>
                <tr className="text-left text-slate-400">
                  <th className="py-2 pr-3">Time</th>
                  <th className="py-2 pr-3">Camera</th>
                  <th className="py-2 pr-3">Zone</th>
                  <th className="py-2 pr-3">Absent Duration</th>
                  <th className="py-2 pr-3">Threshold</th>
                  <th className="py-2 pr-3">Evidence</th>
                  <th className="py-2 pr-3">Alert ID</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a) => {
                  const absentSeconds = String((a.extra as any)?.absent_seconds ?? '-');
                  const thresholdSeconds = String((a.extra as any)?.threshold_seconds ?? '-');
                  const snapshot = a.snapshot_url || String((a.extra as any)?.snapshot_url || '');
                  return (
                    <tr key={a.id} className="border-t border-white/10">
                      <td className="py-2 pr-3">{formatUtc(a.start_time)}</td>
                      <td className="py-2 pr-3">{a.camera_id ?? '-'}</td>
                      <td className="py-2 pr-3">{a.zone_id ?? String((a.extra as any)?.workstation_zone_id || '-')}</td>
                      <td className="py-2 pr-3">{absentSeconds === '-' ? '-' : `${absentSeconds}s`}</td>
                      <td className="py-2 pr-3">{thresholdSeconds === '-' ? '-' : `${thresholdSeconds}s`}</td>
                      <td className="py-2 pr-3">
                        {snapshot ? (
                          <a className="underline" href={snapshot} target="_blank" rel="noreferrer">
                            View
                          </a>
                        ) : (
                          '-'
                        )}
                      </td>
                      <td className="py-2 pr-3">
                        <Link href={`/dashboard/alerts/${encodeURIComponent(a.id)}`} className="hover:underline">
                          {a.id}
                        </Link>
                      </td>
                    </tr>
                  );
                })}
                {alerts.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-slate-500">
                      No station monitoring alerts found.
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
