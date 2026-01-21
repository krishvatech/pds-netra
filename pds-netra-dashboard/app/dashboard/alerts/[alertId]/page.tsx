'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { getAlertDetail } from '@/lib/api';
import type { AlertDetail } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EventsTable } from '@/components/tables/EventsTable';
import { formatUtc, humanAlertType, severityBadgeClass } from '@/lib/formatters';
import { ErrorBanner } from '@/components/ui/error-banner';

export default function AlertDetailPage() {
  const params = useParams<{ alertId: string }>();
  const alertId = params.alertId;

  const [detail, setDetail] = useState<AlertDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setError(null);
      try {
        const d = await getAlertDetail(alertId);
        if (mounted) setDetail(d);
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

  return (
    <Card className="animate-fade-up">
      <CardHeader>
        <div className="text-xl font-semibold font-display">Alert Detail</div>
        <div className="text-sm text-slate-600">Review the full timeline and context for this alert.</div>
      </CardHeader>
      <CardContent>
        {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}
        {!detail && !error && <div className="text-sm text-slate-600">Loading…</div>}

        {detail && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
              <div className="p-4 rounded-xl glass-panel">
                <div className="text-xs text-slate-600">Type</div>
                <div className="mt-1 font-semibold font-display">{humanAlertType(detail.alert_type)}</div>
              </div>
              <div className="p-4 rounded-xl glass-panel">
                <div className="text-xs text-slate-600">Severity</div>
                <div className="mt-2">
                  <Badge className={severityBadgeClass(detail.severity_final)}>{detail.severity_final.toUpperCase()}</Badge>
                </div>
              </div>
              <div className="p-4 rounded-xl glass-panel">
                <div className="text-xs text-slate-600">Status</div>
                <div className="mt-1 font-semibold">{detail.status}</div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
              <div className="p-4 rounded-xl glass-panel">
                <div className="text-xs text-slate-600">Godown</div>
                <div className="font-semibold">{detail.godown_id}</div>
                {detail.district && <div className="text-sm text-slate-600">{detail.district}</div>}
              </div>
              <div className="p-4 rounded-xl glass-panel">
                <div className="text-xs text-slate-600">Time window</div>
                <div className="text-sm">
                  <span className="font-medium">Start:</span> {formatUtc(detail.start_time)}
                </div>
                <div className="text-sm">
                  <span className="font-medium">End:</span> {formatUtc(detail.end_time)}
                </div>
              </div>
            </div>

            {detail.summary && (
              <div className="p-4 rounded-xl glass-panel mb-4">
                <div className="text-xs text-slate-600">Summary</div>
                <div className="mt-1">{detail.summary}</div>
              </div>
            )}

            {keyMetaEntries.length > 0 && (
              <div className="p-4 rounded-xl glass-panel mb-4">
                <div className="text-xs text-slate-600 mb-2">Key details</div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  {keyMetaEntries.map(([k, v]) => (
                    <div key={k} className="text-sm">
                      <span className="text-slate-600">{k}:</span> <span className="font-medium">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="mb-2 text-sm font-semibold">Linked events ({detail.events.length})</div>
            <EventsTable events={detail.events} showGodown={false} />
          </>
        )}
      </CardContent>
    </Card>
  );
}
