'use client';

import { useEffect, useMemo, useState } from 'react';
import { createAlertAction, getAlerts } from '@/lib/api';
import type { AlertItem, Severity } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { formatUtc, humanAlertType, severityBadgeClass } from '@/lib/formatters';
import { ErrorBanner } from '@/components/ui/error-banner';

const severityOptions = [
  { label: 'All severities', value: '' },
  { label: 'Critical', value: 'critical' },
  { label: 'Warning', value: 'warning' },
  { label: 'Info', value: 'info' }
];

export default function IncidentsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [severity, setSeverity] = useState('');
  const [assignee, setAssignee] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const resp = await getAlerts({ status: 'OPEN', severity: (severity || undefined) as Severity | undefined, page: 1, page_size: 50 });
      const items = Array.isArray(resp) ? resp : resp.items;
      setAlerts(items);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load incidents');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [severity]);

  const openCount = useMemo(() => alerts.length, [alerts]);

  async function doAction(alertId: string, actionType: string, note?: string) {
    try {
      await createAlertAction(alertId, { action_type: actionType, note });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update alert');
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="text-3xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">Incident Triage</div>
          <div className="text-sm text-slate-300">Prioritize, assign, and resolve live incidents.</div>
        </div>
        <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Open incidents: {openCount}</div>
      </div>

      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Filters</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <div className="text-xs text-slate-600 mb-1">Severity</div>
              <Select value={severity} onChange={(e) => setSeverity(e.target.value)} options={severityOptions} />
            </div>
            <div className="flex items-end text-xs text-slate-500">Actions sync in real time to edge response teams.</div>
          </div>
        </CardContent>
      </Card>

      {error && (
        <Card>
          <CardContent>
            <ErrorBanner message={error} onRetry={() => window.location.reload()} />
          </CardContent>
        </Card>
      )}

      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Open alerts</div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-sm text-slate-600">Loading…</div>
          ) : alerts.length === 0 ? (
            <div className="text-sm text-slate-600">No open incidents.</div>
          ) : (
            <div className="space-y-3">
              {alerts.map((a) => (
                <div key={a.id} className="incident-card p-4 grid grid-cols-1 xl:grid-cols-[1.4fr_1fr] gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge className={severityBadgeClass(a.severity_final)}>{a.severity_final.toUpperCase()}</Badge>
                      <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Alert</div>
                    </div>
                    <div className="mt-2 text-lg font-semibold text-slate-100">{humanAlertType(a.alert_type)}</div>
                    <div className="text-xs text-slate-400 mt-1">
                      {a.godown_name ?? a.godown_id} • {formatUtc(a.start_time)}
                    </div>
                    {a.summary && <div className="text-xs text-slate-500 mt-2">{a.summary}</div>}
                  </div>
                  <div className="space-y-3">
                    <div>
                      <div className="text-xs text-slate-500 mb-1">Assign responder</div>
                      <div className="flex items-center gap-2">
                        <Input
                          value={assignee[a.id] ?? ''}
                          onChange={(e) => setAssignee((prev) => ({ ...prev, [a.id]: e.target.value }))}
                          placeholder="Name / Team"
                        />
                        <Button variant="outline" onClick={() => doAction(a.id, 'ASSIGN', assignee[a.id])}>Assign</Button>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="outline" onClick={() => doAction(a.id, 'ACK')}>Acknowledge</Button>
                      <Button onClick={() => doAction(a.id, 'RESOLVE')}>Resolve</Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
