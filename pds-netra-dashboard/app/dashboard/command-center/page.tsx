'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  getAlerts,
  getDispatchTrace,
  getHealthSummary,
  getMovementSummary,
  getMovementTimeline,
  getOverviewData
} from '@/lib/api';
import type { AlertItem, MovementSummary, MovementTimelinePoint, OverviewData, DispatchTraceItem, HealthSummary } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { MovementTimelineChart, SeriesPoint } from '@/components/charts/MovementTimelineChart';
import { AlertsOverTimeChart } from '@/components/charts/AlertsOverTimeChart';
import { formatUtc, humanAlertType, severityBadgeClass } from '@/lib/formatters';
import { ErrorBanner } from '@/components/ui/error-banner';
import { friendlyErrorMessage } from '@/lib/friendly-error';

function buildRange(days: number) {
  const now = new Date();
  const from = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
  return { from: from.toISOString(), to: now.toISOString() };
}

function toSeries(items: MovementTimelinePoint[]) {
  const buckets = new Map<string, SeriesPoint>();
  const types = new Set<string>();
  for (const item of items) {
    const entry = buckets.get(item.t) ?? { t: item.t };
    entry[item.movement_type] = item.count;
    buckets.set(item.t, entry);
    types.add(item.movement_type);
  }
  const data = Array.from(buckets.values()).sort((a, b) => {
    return new Date(a.t as string).getTime() - new Date(b.t as string).getTime();
  });
  return { data, types: Array.from(types).sort() };
}

export default function CommandCenterPage() {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [movement, setMovement] = useState<MovementSummary | null>(null);
  const [timeline, setTimeline] = useState<MovementTimelinePoint[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [dispatchTrace, setDispatchTrace] = useState<DispatchTraceItem[]>([]);
  const [health, setHealth] = useState<HealthSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const range = useMemo(() => buildRange(7), []);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setError(null);
      try {
        const [overviewResp, movementResp, timelineResp, alertsResp, traceResp, healthResp] = await Promise.all([
          getOverviewData(),
          getMovementSummary({ date_from: range.from, date_to: range.to }),
          getMovementTimeline({ bucket: 'day', date_from: range.from, date_to: range.to }),
          getAlerts({ status: 'OPEN', page: 1, page_size: 8 }),
          getDispatchTrace({ date_from: range.from, date_to: range.to }),
          getHealthSummary()
        ]);
        if (!mounted) return;
        setOverview(overviewResp);
        setMovement(movementResp);
        setTimeline(timelineResp.items ?? []);
        const items = Array.isArray(alertsResp) ? alertsResp : alertsResp.items;
        setAlerts(items);
        setDispatchTrace(traceResp.items ?? []);
        setHealth(healthResp);
      } catch (e) {
        if (mounted)
          setError(
            friendlyErrorMessage(
              e,
              'Unable to load the command center. Check your network or refresh the page.'
            )
          );
      }
    })();
    return () => {
      mounted = false;
    };
  }, [range.from, range.to]);

  const { data: timelineData, types: timelineTypes } = useMemo(() => toSeries(timeline), [timeline]);

  const slaStats = useMemo(() => {
    const total = dispatchTrace.length;
    const met = dispatchTrace.filter((i) => i.sla_met).length;
    const missed = total - met;
    return { total, met, missed };
  }, [dispatchTrace]);

  const alertsOverTime = useMemo(() => overview?.stats.alerts_over_time ?? [], [overview]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Command live
          </div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            State Command Center
          </div>
          <div className="text-sm text-slate-300">
            Live operational health, movement compliance, and incident pressure.
          </div>
        </div>
        <div className="intel-banner">Updated {formatUtc(overview?.timestamp_utc)}</div>
      </div>

      {error && (
        <Card>
          <CardContent>
            <ErrorBanner message={error} onRetry={() => window.location.reload()} />
          </CardContent>
        </Card>
      )}

      <div className="metric-grid">
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Godowns monitored</div>
          <div className="hud-value mt-2">{overview?.stats.godowns_monitored ?? '-'}</div>
          <div className="text-xs text-slate-400 mt-2">Active sites across state</div>
        </div>
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Open alerts</div>
          <div className="hud-value mt-2">
            {overview ? overview.stats.open_alerts_critical + overview.stats.open_alerts_warning : '-'}
          </div>
          <div className="text-xs text-slate-400 mt-2">
            Critical {overview?.stats.open_alerts_critical ?? '-'} • Warning {overview?.stats.open_alerts_warning ?? '-'}
          </div>
        </div>
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Movement events (7d)</div>
          <div className="hud-value mt-2">{movement?.total_events ?? '-'}</div>
          <div className="text-xs text-slate-400 mt-2">Unplanned {movement?.counts_by_type?.UNPLANNED ?? 0}</div>
        </div>
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Dispatch SLA (7d)</div>
          <div className="hud-value mt-2">{slaStats.met}/{slaStats.total}</div>
          <div className="text-xs text-slate-400 mt-2">Missed {slaStats.missed}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <MovementTimelineChart data={timelineData} series={timelineTypes} />
        <AlertsOverTimeChart data={alertsOverTime} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card className="animate-fade-up xl:col-span-2">
          <CardHeader>
            <div className="text-lg font-semibold font-display">Live incident queue</div>
            <div className="text-sm text-slate-600">Highest severity alerts awaiting response.</div>
          </CardHeader>
          <CardContent>
            {alerts.length === 0 ? (
              <div className="text-sm text-slate-600">No open alerts right now.</div>
            ) : (
              <div className="space-y-3">
                {alerts.map((a) => (
                  <div key={a.id} className="incident-card p-4 flex items-start justify-between gap-4">
                    <div>
                      <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Alert</div>
                      <div className="text-base font-semibold text-slate-100">{humanAlertType(a.alert_type)}</div>
                      <div className="text-xs text-slate-400 mt-1">
                        {a.godown_name ?? a.godown_id} • {formatUtc(a.start_time)}
                      </div>
                      {a.summary && <div className="text-xs text-slate-500 mt-2">{a.summary}</div>}
                    </div>
                    <Badge className={severityBadgeClass(a.severity_final)}>{a.severity_final.toUpperCase()}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
        <Card className="animate-fade-up">
          <CardHeader>
            <div className="text-lg font-semibold font-display">System pulse</div>
            <div className="text-sm text-slate-600">Live health rollup.</div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">Cameras offline</span>
                <span className="font-semibold">{health?.cameras_offline ?? '-'}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">Godowns w/ issues</span>
                <span className="font-semibold">{health?.godowns_with_issues ?? '-'}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">MQTT consumer</span>
                <span className="font-semibold">{health?.mqtt_consumer?.connected ? 'Connected' : 'Offline'}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
