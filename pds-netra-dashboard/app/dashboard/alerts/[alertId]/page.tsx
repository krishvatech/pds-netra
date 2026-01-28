'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { createAlertAction, getAlertActions, getAlertDetail } from '@/lib/api';
import type { AlertActionItem, AlertDetail } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EventsTable } from '@/components/tables/EventsTable';
import { formatUtc, humanAlertType, severityBadgeClass } from '@/lib/formatters';
import { ErrorBanner } from '@/components/ui/error-banner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';

export default function AlertDetailPage() {
  const params = useParams<{ alertId: string }>();
  const alertId = params.alertId;

  const [detail, setDetail] = useState<AlertDetail | null>(null);
  const [actions, setActions] = useState<AlertActionItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState('');
  const [actionType, setActionType] = useState('ACK');

  useEffect(() => {
    let mounted = true;
    (async () => {
      setError(null);
      try {
        const [d, actionsResp] = await Promise.all([
          getAlertDetail(alertId),
          getAlertActions(alertId)
        ]);
        if (mounted) {
          setDetail(d);
          setActions(actionsResp.items ?? []);
        }
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load alert');
      }
    })();
    return () => {
      mounted = false;
    };
  }, [alertId]);

  const keyMetaEntries = useMemo(() => {
    if (!detail?.key_meta) return [];
    return Object.entries(detail.key_meta).filter(([, v]) => v !== null && v !== undefined && `${v}`.trim() !== '');
  }, [detail]);

  const timeline = useMemo(() => {
    const items: Array<{ type: 'event' | 'action'; ts: string; label: string; meta?: string }> = [];
    (detail?.events ?? []).forEach((ev) => {
      items.push({
        type: 'event',
        ts: ev.timestamp_utc,
        label: ev.event_type.replaceAll('_', ' '),
        meta: ev.meta?.movement_type ?? undefined
      });
    });
    actions.forEach((a) => {
      items.push({
        type: 'action',
        ts: a.created_at ?? '',
        label: a.action_type,
        meta: a.note ?? undefined
      });
    });
    return items.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
  }, [detail, actions]);

  async function submitAction() {
    try {
      await createAlertAction(alertId, { action_type: actionType, note: note || undefined });
      const actionsResp = await getAlertActions(alertId);
      setActions(actionsResp.items ?? []);
      setNote('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add action');
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-warning" />
            Incident file
          </div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">Alert Detail</div>
          <div className="text-sm text-slate-300">Review the full timeline and context for this alert.</div>
        </div>
        <div className="intel-banner">Case view</div>
      </div>

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Incident summary</div>
        </CardHeader>
        <CardContent>
          {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}
          {!detail && !error && <div className="text-sm text-slate-600">Loading…</div>}

          {detail && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                <div className="incident-card p-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Type</div>
                  <div className="mt-1 font-semibold font-display text-slate-100">{humanAlertType(detail.alert_type)}</div>
                </div>
                <div className="incident-card p-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Severity</div>
                  <div className="mt-2">
                    <Badge className={severityBadgeClass(detail.severity_final)}>{detail.severity_final.toUpperCase()}</Badge>
                  </div>
                </div>
                <div className="incident-card p-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Status</div>
                  <div className="mt-1 font-semibold text-slate-100">{detail.status}</div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                <div className="incident-card p-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Godown</div>
                  <div className="font-semibold text-slate-100">{detail.godown_id}</div>
                  {detail.district && <div className="text-sm text-slate-400">{detail.district}</div>}
                </div>
                <div className="incident-card p-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Time window</div>
                  <div className="text-sm text-slate-200">
                    <span className="font-medium">Start:</span> {formatUtc(detail.start_time)}
                  </div>
                  <div className="text-sm text-slate-200">
                    <span className="font-medium">End:</span> {formatUtc(detail.end_time)}
                  </div>
                </div>
              </div>

              {detail.summary && (
                <div className="incident-card p-4 mb-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em]">Summary</div>
                  <div className="mt-1 text-slate-100">{detail.summary}</div>
                </div>
              )}

              <div className="incident-card p-4 mb-4">
                <div className="text-xs text-slate-400 uppercase tracking-[0.3em] mb-2">Incident actions</div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  <div>
                    <div className="text-xs text-slate-400 mb-1">Action</div>
                    <Select
                      value={actionType}
                      onChange={(e) => setActionType(e.target.value)}
                      options={[
                        { label: 'Acknowledge', value: 'ACK' },
                        { label: 'Assign', value: 'ASSIGN' },
                        { label: 'Resolve', value: 'RESOLVE' },
                        { label: 'Reopen', value: 'REOPEN' },
                        { label: 'Note', value: 'NOTE' }
                      ]}
                    />
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 mb-1">Note / Assignee</div>
                    <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional note" />
                  </div>
                  <div className="flex items-end">
                    <Button onClick={submitAction}>Log action</Button>
                  </div>
                </div>
              </div>

              {timeline.length > 0 && (
                <div className="incident-card p-4 mb-4">
                  <div className="text-xs text-slate-400 uppercase tracking-[0.3em] mb-2">Investigation timeline</div>
                  <div className="space-y-2">
                    {timeline.map((item, idx) => (
                      <div key={`${item.type}-${idx}`} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <span className="text-xs uppercase tracking-[0.3em] text-slate-400">{item.type}</span>
                          <span className="font-medium text-slate-100">{item.label}</span>
                          {item.meta && <span className="text-xs text-slate-400">{item.meta}</span>}
                        </div>
                        <div className="text-xs text-slate-400">{formatUtc(item.ts)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {keyMetaEntries.length > 0 && (
                <div className="incident-card p-4 mb-4">
                  <div className="text-xs text-slate-400 mb-2">Key details</div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                    {keyMetaEntries.map(([k, v]) => (
                      <div key={k} className="text-sm">
                        <span className="text-slate-400">{k}:</span>{' '}
                        <span className="font-medium text-slate-100">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="mb-2 text-sm font-semibold text-slate-200">Linked events ({(detail.events || []).length})</div>
              <EventsTable events={detail.events || []} showGodown={false} />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}