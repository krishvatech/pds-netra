'use client';

import { useEffect, useMemo, useState } from 'react';
import { getDispatchTrace, getEvents, getGodowns, getMovementSummary, getMovementTimeline, createDispatchIssue, updateDispatchIssue, deleteDispatchIssue } from '@/lib/api';
import { ConfirmDialog } from '@/components/ui/dialog';
import type { DispatchTraceItem, EventItem, MovementSummary, MovementTimelinePoint, GodownListItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { MovementTimelineChart, SeriesPoint } from '@/components/charts/MovementTimelineChart';
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
  const buckets = new Map<string, SeriesPoint>();
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
  const inlineErrorClass = 'text-xs text-red-400';
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
  const [editingIssue, setEditingIssue] = useState<DispatchTraceItem | null>(null);
  const [deletingIssue, setDeletingIssue] = useState<DispatchTraceItem | null>(null);
  const [editForm, setEditForm] = useState({
    godown_id: '',
    camera_id: '',
    zone_id: '',
    issue_time_utc: ''
  });
  const [isBusy, setIsBusy] = useState(false);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await getGodowns();
        if (mounted) {
          const list = Array.isArray(data) ? data : data.items;
          setGodowns(list);
        }
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
      } catch (_e) {
        if (mounted) setError('Unable to load dispatch reports; please refresh.');
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
    } catch (_e) {
      setCreateStatus('Unable to create the issue right now; please retry.');
    }
  }

  async function handleUpdateIssue() {
    if (!editingIssue) return;
    setIsBusy(true);
    try {
      const ts = new Date(editForm.issue_time_utc);
      if (Number.isNaN(ts.getTime())) {
        alert('Invalid issue time.');
        return;
      }
      await updateDispatchIssue(editingIssue.issue_id, {
        godown_id: editForm.godown_id,
        camera_id: editForm.camera_id || null,
        zone_id: editForm.zone_id || null,
        issue_time_utc: ts.toISOString()
      });
      setEditingIssue(null);
      setRefreshKey((v) => v + 1);
    } catch (_e) {
      alert('Unable to update the issue right now; please try again.');
    } finally {
      setIsBusy(false);
    }
  }

  async function handleDeleteIssue() {
    if (!deletingIssue) return;
    setIsBusy(true);
    try {
      await deleteDispatchIssue(deletingIssue.issue_id);
      setDeletingIssue(null);
      setRefreshKey((v) => v + 1);
    } catch (_e) {
      alert('Unable to delete the issue right now; please try again.');
    } finally {
      setIsBusy(false);
    }
  }

  function startEdit(issue: DispatchTraceItem) {
    setEditingIssue(issue);
    setEditForm({
      godown_id: issue.godown_id,
      camera_id: issue.camera_id || '',
      zone_id: issue.zone_id || '',
      issue_time_utc: issue.issue_time_utc ? new Date(issue.issue_time_utc).toISOString().slice(0, 16) : ''
    });
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
        <div className="hud-card">
          <CardContent>
            <p className={inlineErrorClass}>{error}</p>
          </CardContent>
        </div>
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
          {loading ? (
            <div className="text-sm text-slate-400">Loading…</div>
          ) : (
            <div className="[&_tr:hover]:bg-white/[0.03] transition-colors">
              <DispatchTraceTable items={trace} onEdit={startEdit} onDelete={setDeletingIssue} />
            </div>
          )}
        </CardContent>
      </Card>

      {editingIssue && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-md" onClick={() => !isBusy && setEditingIssue(null)} />
          <div className="modal-shell modal-body relative w-full max-w-lg hud-card overflow-hidden animate-fade-up">
            <div className="p-6 sm:p-8">
              <div className="text-2xl font-semibold font-display text-white mb-1">Edit dispatch issue</div>
              <div className="text-sm text-slate-400 mb-8">Update the tracking details for issue #{editingIssue.issue_id}</div>

              <div className="space-y-6">
                <div>
                  <label className="hud-label block mb-2">Godown source</label>
                  <Select
                    value={editForm.godown_id}
                    onChange={(e) => setEditForm(pv => ({ ...pv, godown_id: e.target.value }))}
                    options={godownOptions.filter(o => o.value)}
                    className="!bg-white/5 !border-white/10 !text-white focus:!border-amber-500/50"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <div>
                    <label className="hud-label block mb-2">Camera label</label>
                    <Input
                      value={editForm.camera_id}
                      onChange={(e) => setEditForm(pv => ({ ...pv, camera_id: e.target.value }))}
                      placeholder="e.g. Office"
                      className="!bg-white/5 !border-white/10 !text-white placeholder:text-slate-500 focus:!border-amber-500/50"
                    />
                  </div>
                  <div>
                    <label className="hud-label block mb-2">Zone identifier</label>
                    <Input
                      value={editForm.zone_id}
                      onChange={(e) => setEditForm(pv => ({ ...pv, zone_id: e.target.value }))}
                      placeholder="e.g. all"
                      className="!bg-white/5 !border-white/10 !text-white placeholder:text-slate-500 focus:!border-amber-500/50"
                    />
                  </div>
                </div>

                <div>
                  <label className="hud-label block mb-2">Occurrence time (UTC)</label>
                  <Input
                    type="datetime-local"
                    value={editForm.issue_time_utc}
                    onChange={(e) => setEditForm(pv => ({ ...pv, issue_time_utc: e.target.value }))}
                    className="!bg-white/5 !border-white/10 !text-white focus:!border-amber-500/50"
                  />
                </div>
              </div>

              <div className="mt-10 flex flex-col-reverse sm:flex-row justify-end gap-3">
                <Button
                  variant="outline"
                  onClick={() => setEditingIssue(null)}
                  disabled={isBusy}
                  className="!bg-white/5 !border-white/10 !text-slate-300 hover:!bg-white/10 hover:!text-white border-0"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleUpdateIssue}
                  disabled={isBusy}
                  className="min-w-[140px]"
                >
                  {isBusy ? 'Saving changes...' : 'Update issue'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!deletingIssue}
        title="Delete dispatch issue"
        message={`Are you sure you want to delete issue #${deletingIssue?.issue_id}? This cannot be undone.`}
        confirmLabel="Delete"
        confirmVariant="danger"
        isBusy={isBusy}
        onConfirm={handleDeleteIssue}
        onCancel={() => setDeletingIssue(null)}
      />

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
