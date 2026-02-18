'use client';

import { useEffect, useMemo, useState } from 'react';
import { getOverviewData } from '@/lib/api';
import type { OverviewData } from '@/lib/types';
import { HealthStatusCard } from '@/components/cards/HealthStatusCard';
import { GodownSummaryCard } from '@/components/cards/GodownSummaryCard';
import { AlertsByTypeChart } from '@/components/charts/AlertsByTypeChart';
import { AlertsOverTimeChart } from '@/components/charts/AlertsOverTimeChart';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { formatUtc } from '@/lib/formatters';

export default function OverviewPage() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inlineErrorClass = 'text-xs text-red-400';

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const d = await getOverviewData();
        if (mounted) setData(d);
      } catch (_e) {
        if (mounted) setError('Unable to load overview data; please refresh.');
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const alertsByType = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.stats.alerts_by_type).map(([k, v]) => ({ name: k, count: v }));
  }, [data]);

  const alertsOverTime = useMemo(() => {
    if (!data) return [];
    return data.stats.alerts_over_time;
  }, [data]);

  if (error) {
    return (
      <Card>
        <CardHeader>
          <div className="text-lg font-semibold font-display">Overview</div>
        </CardHeader>
        <CardContent>
          <p className={inlineErrorClass}>{error}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4 md:space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="text-2xl font-semibold tracking-tight text-slate-100 md:text-3xl lg:text-4xl">
            Statewide Command View
          </div>
          <div className="text-sm text-muted-foreground">
            Live telemetry, alert pressure, and godown readiness at a glance.
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs uppercase tracking-widest opacity-70">
          <div className="flex items-center gap-2 text-slate-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            Live system
          </div>
          <div className="text-slate-400">
            Updated {formatUtc(data?.timestamp_utc)}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger">
        <HealthStatusCard title="Godowns monitored" value={data?.stats.godowns_monitored ?? '-'} />
        <HealthStatusCard title="Open alerts (Critical / Warning)" value={data ? `${data.stats.open_alerts_critical} / ${data.stats.open_alerts_warning}` : '-'} />
        <HealthStatusCard title="Cameras with issues" value={data?.stats.cameras_with_issues ?? '-'} tone="warning" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 stagger">
        <HealthStatusCard
          title="After-hours person alerts (24h / 7d)"
          value={
            data
              ? `${data.stats.after_hours_person_24h ?? 0} / ${data.stats.after_hours_person_7d ?? 0}`
              : '-'
          }
        />
        <HealthStatusCard
          title="After-hours vehicle alerts (24h / 7d)"
          value={
            data
              ? `${data.stats.after_hours_vehicle_24h ?? 0} / ${data.stats.after_hours_vehicle_7d ?? 0}`
              : '-'
          }
        />
        <HealthStatusCard
          title="Animal intrusion alerts (24h / 7d)"
          value={
            data
              ? `${data.stats.animal_intrusions_24h ?? 0} / ${data.stats.animal_intrusions_7d ?? 0}`
              : '-'
          }
        />
        <HealthStatusCard
          title="Fire alerts (24h / 7d)"
          value={
            data
              ? `${data.stats.fire_alerts_24h ?? 0} / ${data.stats.fire_alerts_7d ?? 0}`
              : '-'
          }
        />
        <HealthStatusCard
          title="Open gate sessions"
          value={data ? `${data.stats.open_gate_sessions ?? 0}` : '-'}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 stagger">
        <AlertsByTypeChart data={alertsByType} />
        <AlertsOverTimeChart data={alertsOverTime} />
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-lg font-semibold">Godown readiness</div>
          <div className="text-sm text-muted-foreground">Quick status view</div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {(data?.godowns ?? []).map((g) => (
            <GodownSummaryCard key={g.godown_id} godown={g} />
          ))}
          {!data && (
            <div className="text-sm text-slate-600">Loading…</div>
          )}
        </div>
      </div>
    </div>
  );
}
