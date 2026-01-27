'use client';

import { useEffect, useMemo, useState } from 'react';
import { getDispatchTrace, getEvents, getGodowns, getMovementSummary, getMovementTimeline, createDispatchIssue } from '@/lib/api';
import type { DispatchTraceItem, EventItem, MovementSummary, MovementTimelinePoint, GodownListItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { MovementTimelineChart } from '@/components/charts/MovementTimelineChart';
import { DispatchTraceTable } from '@/components/tables/DispatchTraceTable';
import { MovementEventsTable } from '@/components/tables/MovementEventsTable';

const rangeOptions = [
  { label: 'Last 24 hours', value: '1' },
  { label: 'Last 7 days', value: '7' },
  { label: 'Last 30 days', value: '30' }
];

const movementTypeOptions = [
  { label: 'All movement types', value: '' },
  { label: 'Normal', value: 'NORMAL' },
  { label: 'Odd hours', value: 'ODD_HOURS' },
  { label: 'Unplanned', value: 'UNPLANNED' },
  { label: 'Tally mismatch', value: 'TALLY_MISMATCH' },
  { label: 'After hours', value: 'AFTER_HOURS' }
];

function buildDateRange(days: number) {
  const now = new Date();
  const from = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
  return { from: from.toISOString(), to: now.toISOString() };
}

function formatCount(value: number | undefined) {
  if (value === undefined || Number.isNaN(value)) return '-';
  return value.toString();
}

function toSeries(items: MovementTimelinePoint[]) {
  const buckets = new Map<string, Record<string, string | number>>();
  const types = new Set<string>();
  for (const item of items) {
    const key = item.t;
    const entry = buckets.get(key) ?? { t: item.t };
    entry[item.movement_type] = item.count;
    buckets.set(key, entry);
    types.add(item.movement_type);
  }
  const data = Array.from(buckets.values()).sort((a, b) => {
    return new Date(a.t as string).getTime() - new Date(b.t as string).getTime();
  });
  return { data, types: Array.from(types).sort() };
}

export default function DispatchPage() {
  const [rangeDays, setRangeDays] = useState('7');
  const [godownId, setGodownId] = useState('');
  const [movementType, setMovementType] = useState('');
  const [summary, setSummary] = useState<MovementSummary | null>(null);
  const [timeline, setTimeline] = useState<MovementTimelinePoint[]>([]);
  const [trace, setTrace] = useState<DispatchTraceItem[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const [issueGodown, setIssueGodown] = useState('');
  const [issueCamera, setIssueCamera] = useState('');
  const [issueZone, setIssueZone] = useState('');
  const [issueTime, setIssueTime] = useState('');
  const [createStatus, setCreateStatus] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await getGodowns();
        if (mounted) setGodowns(data);
      } catch {
        // Ignore; godown filters will remain manual
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setRefreshKey((v) => v + 1);
    }, 30000);
    return () => window.clearInterval(interval);
  }, []);

  const dateRange = useMemo(() => buildDateRange(Number(rangeDays)), [rangeDays]);
  const bucket = Number(rangeDays) > 3 ? 'day' : 'hour';

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [summaryResp, timelineResp, traceResp, eventsResp] = await Promise.all([
          getMovementSummary({
            godown_id: godownId || undefined,
            date_from: dateRange.from,
            date_to: dateRange.to
          }),
          getMovementTimeline({
            bucket,
            godown_id: godownId || undefined,
            date_from: dateRange.from,
            date_to: dateRange.to
          }),
          getDispatchTrace({
            godown_id: godownId || undefined,
            date_from: dateRange.from,
            date_to: dateRange.to
          }),
          getEvents({
            godown_id: godownId || undefined,
            event_type: 'BAG_MOVEMENT',
            date_from: dateRange.from,
            date_to: dateRange.to,
            page: 1,
            page_size: 200
          })
        ]);
        if (!mounted) return;
        setSummary(summaryResp);
        setTimeline(timelineResp.items ?? []);
        setTrace(traceResp.items ?? []);
        const items = Array.isArray(eventsResp) ? eventsResp : eventsResp.items;
        setEvents(items);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load dispatch reports');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [bucket, dateRange.from, dateRange.to, godownId, refreshKey]);

  const movementCounts = summary?.counts_by_type ?? {};
  const { data: timelineSeries, types: timelineTypes } = useMemo(() => toSeries(timeline), [timeline]);

  const filteredEvents = useMemo(() => {
    if (!movementType) return events;
    return events.filter((ev) => String(ev.meta?.movement_type ?? '').toUpperCase() === movementType);
  }, [events, movementType]);

  const slaStats = useMemo(() => {
    const total = trace.length;
    const met = trace.filter((i) => i.sla_met).length;
    const missed = total - met;
    const delays = trace.map((i) => i.delay_minutes).filter((v): v is number => typeof v === 'number');
    const avgDelay = delays.length ? Math.round(delays.reduce((a, b) => a + b, 0) / delays.length) : null;
    return { total, met, missed, avgDelay };
  }, [trace]);

  const godownOptions = useMemo(() => {
    const options = godowns.map((g) => ({
      label: `${g.name ?? g.godown_id} (${g.godown_id})`,
      value: g.godown_id
    }));
    return [{ label: 'All godowns', value: '' }, ...options];
  }, [godowns]);

  async function handleCreateIssue() {
    setCreateStatus(null);
    if (!issueGodown || !issueTime) {
      setCreateStatus('Godown and issue time are required.');
      return;
    }
    try {
      const ts = new Date(issueTime);
      if (Number.isNaN(ts.getTime())) {
        setCreateStatus('Invalid issue time.');
        return;
      }
      await createDispatchIssue({
        godown_id: issueGodown,
        camera_id: issueCamera || undefined,
        zone_id: issueZone || undefined,
        issue_time_utc: ts.toISOString()
      });
      setCreateStatus('Dispatch issue created.');
      setRefreshKey((v) => v + 1);
      setIssueCamera('');
      setIssueZone('');
      setIssueTime('');
    } catch (e) {
      setCreateStatus(e instanceof Error ? e.message : 'Failed to create dispatch issue.');
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Dispatch intelligence
          </div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Dispatch Movement Tracker
          </div>
          <div className="text-sm text-slate-300">
            Track foodgrain movement readiness, dispatch SLAs, and operational delays.
          </div>
        </div>
        <div className="intel-banner">SLA watch</div>
      </div>

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Filters</div>
          <div className="text-sm text-slate-300">Scope the movement timeline and dispatch trace.</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <div className="text-xs text-slate-400 mb-1">Range</div>
              <Select value={rangeDays} onChange={(e) => setRangeDays(e.target.value)} options={rangeOptions} />
            </div>
            <div>
              <div className="text-xs text-slate-400 mb-1">Godown</div>
              <Select value={godownId} onChange={(e) => setGodownId(e.target.value)} options={godownOptions} />
            </div>
            <div className="flex items-end">
              <div className="text-xs text-slate-400">Timeline bucket: {bucket.toUpperCase()}</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {error && (
        <Card className="hud-card">
          <CardContent>
            <ErrorBanner message={error} onRetry={() => window.location.reload()} />
          </CardContent>
        </Card>
      )}

      <div className="metric-grid">
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Movement events</div>
          <div className="hud-value mt-2">{formatCount(summary?.total_events)}</div>
          <div className="text-xs text-slate-400 mt-2">All tagged movement detections</div>
        </div>
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Unplanned</div>
          <div className="hud-value mt-2">{formatCount(movementCounts.UNPLANNED)}</div>
          <div className="text-xs text-slate-400 mt-2">Movement without allocation</div>
        </div>
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">SLA met</div>
          <div className="hud-value mt-2">{slaStats.met}/{slaStats.total}</div>
          <div className="text-xs text-slate-400 mt-2">Within 24h dispatch window</div>
        </div>
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Avg delay (min)</div>
          <div className="hud-value mt-2">{slaStats.avgDelay ?? '-'}</div>
          <div className="text-xs text-slate-400 mt-2">Time to first movement</div>
        </div>
      </div>

      <MovementTimelineChart data={timelineSeries} series={timelineTypes} />

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Dispatch SLA tracker</div>
          <div className="text-sm text-slate-300">Issue → first movement trace, SLA compliance, and delays.</div>
        </CardHeader>
        <CardContent>
          {loading ? <div className="text-sm text-slate-400">Loading…</div> : <DispatchTraceTable items={trace} />}
        </CardContent>
      </Card>

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Movement activity log</div>
          <div className="text-sm text-slate-300">Operational movement events captured from edge.</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            <div>
              <div className="text-xs text-slate-400 mb-1">Movement type</div>
              <Select value={movementType} onChange={(e) => setMovementType(e.target.value)} options={movementTypeOptions} />
            </div>
            <div className="flex items-end">
              <div className="text-xs text-slate-400">Showing {filteredEvents.length} of {events.length} events.</div>
            </div>
          </div>
          {loading ? <div className="text-sm text-slate-400">Loading…</div> : <MovementEventsTable events={filteredEvents} />}
        </CardContent>
      </Card>

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Create dispatch issue</div>
          <div className="text-sm text-slate-300">Record a dispatch order to track 24h start compliance.</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <div className="text-xs text-slate-400 mb-1">Godown</div>
              <Select
                value={issueGodown}
                onChange={(e) => setIssueGodown(e.target.value)}
                options={[{ label: 'Select godown', value: '' }, ...godownOptions.filter((o) => o.value)]}
              />
            </div>
            <div>
              <div className="text-xs text-slate-400 mb-1">Camera (optional)</div>
              <Input value={issueCamera} onChange={(e) => setIssueCamera(e.target.value)} placeholder="CAM_AISLE_3" />
            </div>
            <div>
              <div className="text-xs text-slate-400 mb-1">Zone (optional)</div>
              <Input value={issueZone} onChange={(e) => setIssueZone(e.target.value)} placeholder="aisle_zone3" />
            </div>
            <div>
              <div className="text-xs text-slate-400 mb-1">Issue time</div>
              <Input type="datetime-local" value={issueTime} onChange={(e) => setIssueTime(e.target.value)} />
            </div>
          </div>
          <div className="mt-4 flex items-center gap-3">
            <Button onClick={handleCreateIssue}>Create issue</Button>
            {createStatus && <div className="text-sm text-slate-300">{createStatus}</div>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
