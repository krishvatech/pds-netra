'use client';

import { useEffect, useMemo, useState } from 'react';
import { getUser } from '@/lib/auth';
import { getAnprDailyReport, getAnprEvents, getAnprVehicles, getGodowns } from '@/lib/api';
import type { AnprDailyReportResponse, AnprEvent, AnprEventsResponse, AnprVehicle, GodownListItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Table, THead, TBody, TR, TH, TD } from '@/components/ui/table';
import { ErrorBanner } from '@/components/ui/error-banner';

function toDateStr(d: Date) {
  return d.toISOString().slice(0, 10);
}

function toDateTimeLocalStr(d: Date) {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}T${hh}:${min}`;
}

function formatInTimezone(tsUtc: string, timezone: string) {
  try {
    const dt = new Date(tsUtc);
    return new Intl.DateTimeFormat('en-GB', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    }).format(dt);
  } catch {
    return tsUtc;
  }
}

export default function AnprReportsPage() {
  const [godownId, setGodownId] = useState('');
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [timezoneName, setTimezoneName] = useState('Asia/Kolkata');
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 6);
    return toDateStr(d);
  });
  const [dateTo, setDateTo] = useState(() => toDateStr(new Date()));
  const [dateTimeFrom, setDateTimeFrom] = useState(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return toDateTimeLocalStr(d);
  });
  const [dateTimeTo, setDateTimeTo] = useState(() => toDateTimeLocalStr(new Date()));
  const [sessionLimit, setSessionLimit] = useState(2000);

  const [data, setData] = useState<AnprDailyReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionData, setSessionData] = useState<AnprEventsResponse | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [vehicles, setVehicles] = useState<AnprVehicle[]>([]);

  const godownOptions = useMemo(() => {
    const opts = godowns.map((g) => ({ label: g.name || g.godown_id, value: g.godown_id }));
    if (godownId && !opts.some((o) => o.value === godownId)) {
      return [{ label: godownId, value: godownId }, ...opts];
    }
    return opts;
  }, [godowns, godownId]);

  useEffect(() => {
    if (!godownId) {
      const user = getUser();
      if (user?.godown_id) setGodownId(String(user.godown_id));
    }
  }, [godownId]);

  useEffect(() => {
    let alive = true;
    async function loadGodowns() {
      try {
        const resp = await getGodowns({});
        const items = Array.isArray(resp) ? resp : resp.items;
        if (alive) setGodowns(items || []);
      } catch {
        // Non-blocking.
      }
    }
    loadGodowns();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    async function loadVehicles() {
      if (!godownId) {
        if (alive) setVehicles([]);
        return;
      }
      try {
        const resp = await getAnprVehicles({
          godown_id: godownId,
          page: 1,
          page_size: 500
        });
        if (alive) setVehicles(resp.items || []);
      } catch {
        if (alive) setVehicles([]);
      }
    }
    loadVehicles();
    return () => {
      alive = false;
    };
  }, [godownId]);

  async function load() {
    if (!godownId || !dateFrom || !dateTo) return;
    try {
      setError(null);
      const resp = await getAnprDailyReport({
        godown_id: godownId,
        timezone_name: timezoneName,
        date_from: dateFrom,
        date_to: dateTo
      });
      setData(resp);
    } catch (e: any) {
      setError(e?.message || 'Failed to load report');
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [godownId, timezoneName, dateFrom, dateTo]);

  async function loadSessions() {
    if (!godownId) return;
    try {
      setSessionLoading(true);
      setSessionError(null);
      const resp = await getAnprEvents({
        godown_id: godownId,
        limit: sessionLimit
      });
      setSessionData(resp);
    } catch (e: any) {
      setSessionError(e?.message || 'Failed to load session report');
    } finally {
      setSessionLoading(false);
    }
  }

  useEffect(() => {
    loadSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [godownId, sessionLimit]);

  const totals = useMemo(() => {
    const rows = data?.rows || [];
    return rows.reduce(
      (acc, r) => {
        acc.planned_items += Number(r.planned_items || 0);
        acc.arrived += Number(r.arrived || 0);
        acc.delayed += Number(r.delayed || 0);
        acc.no_show += Number(r.no_show || 0);
        acc.cancelled += Number(r.cancelled || 0);
        return acc;
      },
      { planned_items: 0, arrived: 0, delayed: 0, no_show: 0, cancelled: 0 }
    );
  }, [data]);

  const vehicleMap = useMemo(() => {
    const map = new Map<string, AnprVehicle>();
    for (const v of vehicles) {
      const raw = (v.plate_raw || '').toUpperCase().trim();
      const norm = (v.plate_norm || '').toUpperCase().trim();
      if (raw) map.set(raw, v);
      if (norm) map.set(norm, v);
    }
    return map;
  }, [vehicles]);

  const sessionRows = useMemo(() => {
    const events = sessionData?.events || [];
    if (!events.length) return [];
    const fromMs = dateTimeFrom ? new Date(dateTimeFrom).getTime() : -Infinity;
    const toMs = dateTimeTo ? new Date(dateTimeTo).getTime() : Infinity;
    const byPlate: Record<string, AnprEvent[]> = {};
    for (const e of events) {
      const t = new Date(e.timestamp_utc || e.timestamp_local).getTime();
      if (Number.isNaN(t)) continue;
      if (t < fromMs || t > toMs) continue;
      const key = (e.plate_text || '').toUpperCase().trim();
      if (!key) continue;
      if (!byPlate[key]) byPlate[key] = [];
      byPlate[key].push(e);
    }

    const rows = Object.entries(byPlate).map(([plate, items]) => {
      items.sort(
        (a, b) =>
          new Date(a.timestamp_utc || a.timestamp_local).getTime() -
          new Date(b.timestamp_utc || b.timestamp_local).getTime()
      );
      const first = items[0];
      const last = items[items.length - 1];
      const vehicle = vehicleMap.get(plate);
      return {
        plate,
        transporter: vehicle?.transporter || 'N/A',
        notes: vehicle?.notes || 'N/A',
        firstSeen: first.timestamp_utc,
        lastSeen: last.timestamp_utc,
        events: items.length,
        status: (last.match_status || 'UNKNOWN').toUpperCase(),
        camera: last.camera_id || 'N/A'
      };
    });

    rows.sort((a, b) => String(b.lastSeen).localeCompare(String(a.lastSeen)));
    return rows;
  }, [sessionData, dateTimeFrom, dateTimeTo, vehicleMap]);

  const sessionStats = useMemo(() => {
    const events = sessionData?.events || [];
    const fromMs = dateTimeFrom ? new Date(dateTimeFrom).getTime() : -Infinity;
    const toMs = dateTimeTo ? new Date(dateTimeTo).getTime() : Infinity;
    const count = events.filter((e) => {
      const t = new Date(e.timestamp_utc || e.timestamp_local).getTime();
      return !Number.isNaN(t) && t >= fromMs && t <= toMs;
    }).length;
    return { vehicles: sessionRows.length, events: count };
  }, [sessionData, sessionRows.length, dateTimeFrom, dateTimeTo]);

  function exportCsv() {
    const rows = data?.rows || [];
    const lines: string[] = [];

    lines.push('DAILY_SUMMARY');
    const header = ['date_local', 'expected_count', 'planned_items', 'arrived', 'delayed', 'no_show', 'cancelled'];
    lines.push(header.join(','));
    for (const r of rows) {
      lines.push(
        [
          r.date_local,
          r.expected_count ?? '',
          r.planned_items ?? 0,
          r.arrived ?? 0,
          r.delayed ?? 0,
          r.no_show ?? 0,
          r.cancelled ?? 0
        ].join(',')
      );
    }

    lines.push('');
    lines.push('SESSION_REPORT');
    const sessionHeader = [
      'plate',
      'transporter',
      'notes',
      'first_seen_utc',
      'last_seen_utc',
      'events',
      'status',
      'camera'
    ];
    lines.push(sessionHeader.join(','));
    for (const s of sessionRows) {
      lines.push(
        [
          s.plate,
          s.transporter,
          s.notes,
          s.firstSeen,
          s.lastSeen,
          s.events,
          s.status,
          s.camera
        ].join(',')
      );
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `anpr_report_${godownId}_${dateFrom}_to_${dateTo}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">Reports</div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            ANPR Reports
          </div>
          <div className="text-sm text-slate-300">Daily performance summary across planned vs actual arrivals.</div>
        </div>
        <div className="hud-card p-4 min-w-[240px]">
          <div className="hud-label">Total planned</div>
          <div className="hud-value">{totals.planned_items}</div>
          <div className="text-xs text-slate-500">Range: {dateFrom} to {dateTo}</div>
        </div>
      </div>
      {error && <ErrorBanner message={error} />}
      {sessionError && <ErrorBanner message={sessionError} />}

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Filters</div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">Daily summary range</div>
          <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
            <div className="md:col-span-2">
              <Label>Godown</Label>
              <Select
                value={godownId}
                onChange={(e) => setGodownId(e.target.value)}
                options={godownOptions}
                placeholder="Select godown..."
              />
            </div>
            <div>
              <Label>Timezone</Label>
              <Input value={timezoneName} onChange={(e) => setTimezoneName(e.target.value)} />
            </div>
            <div>
              <Label>Date From</Label>
              <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </div>
            <div>
              <Label>Date To</Label>
              <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </div>
            <div className="flex items-end gap-2">
              <Button onClick={load}>Refresh</Button>
              <Button variant="outline" onClick={exportCsv} disabled={!data?.rows?.length}>
                Export CSV
              </Button>
            </div>
          </div>

          <div className="text-xs uppercase tracking-wide text-slate-400">Session report range</div>
          <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
            <div>
              <Label>From (Date &amp; Time)</Label>
              <Input type="datetime-local" value={dateTimeFrom} onChange={(e) => setDateTimeFrom(e.target.value)} />
            </div>
            <div>
              <Label>To (Date &amp; Time)</Label>
              <Input type="datetime-local" value={dateTimeTo} onChange={(e) => setDateTimeTo(e.target.value)} />
            </div>
            <div>
              <Label>Events Limit</Label>
              <Input
                type="number"
                value={sessionLimit}
                onChange={(e) => setSessionLimit(Math.min(5000, Number(e.target.value) || 2000))}
              />
            </div>
            <div className="flex items-end gap-2">
              <Button onClick={loadSessions} disabled={sessionLoading}>
                {sessionLoading ? 'Refreshing...' : 'Refresh Sessions'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader className="flex items-center justify-between">
          <div className="text-lg font-semibold font-display">Daily Summary</div>
          <div className="hud-pill">Report grid</div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-xs text-slate-300">
            Planned items: {totals.planned_items} | Arrived: {totals.arrived} | Delayed: {totals.delayed} | No show: {totals.no_show} | Cancelled: {totals.cancelled}
          </div>
          <div className="table-shell overflow-auto">
            <Table>
              <THead>
                <TR>
                  <TH>Date</TH>
                  <TH>Expected Count</TH>
                  <TH>Planned Items</TH>
                  <TH>Arrived</TH>
                  <TH>Delayed</TH>
                  <TH>No Show</TH>
                  <TH>Cancelled</TH>
                </TR>
              </THead>
              <TBody>
                {(data?.rows || []).length === 0 ? (
                  <TR>
                    <TD colSpan={7} className="text-sm text-slate-500">
                      No rows
                    </TD>
                  </TR>
                ) : (
                  (data?.rows || []).map((r) => (
                    <TR key={r.date_local}>
                      <TD className="font-semibold">{r.date_local}</TD>
                      <TD>{r.expected_count ?? 'N/A'}</TD>
                      <TD>{r.planned_items}</TD>
                      <TD>{r.arrived}</TD>
                      <TD>{r.delayed}</TD>
                      <TD>{r.no_show}</TD>
                      <TD>{r.cancelled}</TD>
                    </TR>
                  ))
                )}
              </TBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader className="flex items-center justify-between">
          <div className="text-lg font-semibold font-display">Session Report</div>
          <div className="hud-pill">Live/session report</div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-xs text-slate-300">
            Vehicles: {sessionStats.vehicles} | Events: {sessionStats.events} | Timezone: {timezoneName}
          </div>
          <div className="table-shell overflow-auto">
            <Table>
              <THead>
                <TR>
                  <TH>Plate</TH>
                  <TH>Transporter</TH>
                  <TH>Notes</TH>
                  <TH>First Seen</TH>
                  <TH>Last Seen</TH>
                  <TH>Events</TH>
                  <TH>Status</TH>
                  <TH>Camera</TH>
                </TR>
              </THead>
              <TBody>
                {sessionRows.length === 0 ? (
                  <TR>
                    <TD colSpan={8} className="text-sm text-slate-500">
                      No session data in range
                    </TD>
                  </TR>
                ) : (
                  sessionRows.map((row) => (
                    <TR key={`${row.plate}-${row.lastSeen}`}>
                      <TD className="font-semibold">{row.plate}</TD>
                      <TD>{row.transporter}</TD>
                      <TD className="max-w-[240px] truncate">{row.notes}</TD>
                      <TD>{formatInTimezone(row.firstSeen, timezoneName)}</TD>
                      <TD>{formatInTimezone(row.lastSeen, timezoneName)}</TD>
                      <TD>{row.events}</TD>
                      <TD>{row.status}</TD>
                      <TD>{row.camera}</TD>
                    </TR>
                  ))
                )}
              </TBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
