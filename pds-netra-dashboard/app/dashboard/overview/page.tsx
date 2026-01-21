'use client';

import { useEffect, useMemo, useState } from 'react';
import { getOverviewData } from '@/lib/api';
import type { OverviewData } from '@/lib/types';
import { HealthStatusCard } from '@/components/cards/HealthStatusCard';
import { GodownSummaryCard } from '@/components/cards/GodownSummaryCard';
import { AlertsByTypeChart } from '@/components/charts/AlertsByTypeChart';
import { AlertsOverTimeChart } from '@/components/charts/AlertsOverTimeChart';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { ErrorBanner } from '@/components/ui/error-banner';
import { formatUtc } from '@/lib/formatters';

export default function OverviewPage() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const d = await getOverviewData();
        if (mounted) setData(d);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load overview');
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
          <ErrorBanner message={error} onRetry={() => window.location.reload()} />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-3xl font-semibold font-display tracking-tight">
            Statewide Command View
          </div>
          <div className="text-sm text-slate-600">
            Live telemetry, alert pressure, and godown readiness at a glance.
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.3em] text-slate-500">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          Live system
        </div>
        <div className="text-xs uppercase tracking-[0.3em] text-slate-500">
          Updated {formatUtc(data?.timestamp_utc)}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 stagger">
        <HealthStatusCard title="Godowns monitored" value={data?.stats.godowns_monitored ?? '-'} />
        <HealthStatusCard title="Open alerts (Critical / Warning)" value={data ? `${data.stats.open_alerts_critical} / ${data.stats.open_alerts_warning}` : '-'} />
        <HealthStatusCard title="Cameras with issues" value={data?.stats.cameras_with_issues ?? '-'} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 stagger">
        <AlertsByTypeChart data={alertsByType} />
        <AlertsOverTimeChart data={alertsOverTime} />
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-lg font-semibold font-display">Godown readiness</div>
          <div className="text-sm text-slate-600">Quick status view</div>
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
