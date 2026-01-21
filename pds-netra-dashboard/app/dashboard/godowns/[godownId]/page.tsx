'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { getGodownDetail, getGodownHealth, getEvents, getAlerts } from '@/lib/api';
import type { AlertItem, EventItem, GodownDetail, GodownHealth } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { EventsTable } from '@/components/tables/EventsTable';
import { AlertsTable } from '@/components/tables/AlertsTable';
import { Table, THead, TBody, TR, TH, TD } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { formatUtc } from '@/lib/formatters';
import { ErrorBanner } from '@/components/ui/error-banner';

function onlineBadge(online: boolean) {
  return online ? (
    <Badge className="bg-green-100 text-green-800 border-green-200">Online</Badge>
  ) : (
    <Badge className="bg-red-100 text-red-800 border-red-200">Offline</Badge>
  );
}

export default function GodownDetailPage() {
  const params = useParams<{ godownId: string }>();
  const godownId = params.godownId;

  const [detail, setDetail] = useState<GodownDetail | null>(null);
  const [health, setHealth] = useState<GodownHealth | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const last24hFrom = useMemo(() => {
    const d = new Date(Date.now() - 24 * 60 * 60 * 1000);
    return d.toISOString();
  }, []);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setError(null);
      try {
        const [d, h, e, a] = await Promise.all([
          getGodownDetail(godownId),
          getGodownHealth(godownId),
          getEvents({ godown_id: godownId, date_from: last24hFrom, page: 1, page_size: 25 }),
          getAlerts({ godown_id: godownId, date_from: last24hFrom, status: 'OPEN', page: 1, page_size: 25 })
        ]);
        if (!mounted) return;
        setDetail(d);
        setHealth(h);
        setEvents(e.items);
        setAlerts(a.items);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load godown');
      }
    })();

    return () => {
      mounted = false;
    };
  }, [godownId, last24hFrom]);

  return (
    <div className="space-y-4">
      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-2xl font-semibold font-display">{detail?.name ?? godownId}</div>
          <div className="text-sm text-slate-600">
            District: {detail?.district ?? '-'} • Cameras: {detail?.cameras?.length ?? health?.cameras?.length ?? '-'}
          </div>
        </CardHeader>
        <CardContent>
          {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <div className="text-lg font-semibold mb-2">Cameras</div>
              <div className="table-shell overflow-auto">
                <Table>
                  <THead>
                    <TR>
                      <TH>Camera</TH>
                      <TH>Role</TH>
                      <TH>Status</TH>
                      <TH>Last Frame</TH>
                      <TH>Reason</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {(health?.cameras ?? detail?.cameras ?? []).map((c: any) => (
                      <TR key={c.camera_id ?? c.id}>
                        <TD className="font-medium">{c.camera_id ?? c.id}</TD>
                        <TD>{c.role ?? '-'}</TD>
                        <TD>{onlineBadge(Boolean(c.online ?? c.is_online ?? c.last_health_status === 'OK'))}</TD>
                        <TD>{formatUtc(c.last_frame_utc ?? c.last_frame_time_utc ?? null)}</TD>
                        <TD>{c.last_tamper_reason ?? '-'}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </div>
            </div>

            <div>
              <div className="text-lg font-semibold mb-2">Open alerts (last 24h)</div>
              <AlertsTable alerts={alerts} />
            </div>
          </div>

          <div className="mt-6">
            <div className="text-lg font-semibold mb-2">Recent events (last 24h)</div>
            <EventsTable events={events} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
