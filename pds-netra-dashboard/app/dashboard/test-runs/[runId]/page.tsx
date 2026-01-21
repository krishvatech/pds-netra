'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import {
  activateTestRun,
  deactivateTestRun,
  getAlerts,
  getEvents,
  getTestRunDetail
} from '@/lib/api';
import type { AlertItem, EventItem, TestRunDetail } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { EventsTable } from '@/components/tables/EventsTable';
import { AlertsTable } from '@/components/tables/AlertsTable';
import { formatUtc } from '@/lib/formatters';

export default function TestRunDetailPage() {
  const params = useParams();
  const runId = String(params?.runId ?? '');
  const [run, setRun] = useState<TestRunDetail | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sizes, setSizes] = useState<Record<string, { w: number; h: number }>>({});

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!runId) return;
      setError(null);
      try {
        const detail = await getTestRunDetail(runId);
        if (mounted) setRun(detail);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load test run');
      }
    })();
    return () => {
      mounted = false;
    };
  }, [runId]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!run?.godown_id || !run?.camera_id) return;
      try {
        const eventsResp = await getEvents({
          godown_id: run.godown_id,
          camera_id: run.camera_id,
          page: 1,
          page_size: 50
        });
        const alertsResp = await getAlerts({
          godown_id: run.godown_id,
          status: 'OPEN',
          page: 1,
          page_size: 50
        });
        if (mounted) {
          setEvents(Array.isArray(eventsResp) ? eventsResp : eventsResp.items);
          setAlerts(Array.isArray(alertsResp) ? alertsResp : alertsResp.items);
        }
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load related events');
      }
    })();
    return () => {
      mounted = false;
    };
  }, [run?.godown_id, run?.camera_id]);

  const handleActivate = async () => {
    if (!run) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await activateTestRun(run.run_id);
      if (resp.run) setRun(resp.run);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to activate test run');
    } finally {
      setLoading(false);
    }
  };

  const handleDeactivate = async () => {
    if (!run) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await deactivateTestRun(run.run_id);
      if (resp.run) setRun(resp.run);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to deactivate test run');
    } finally {
      setLoading(false);
    }
  };

  if (!runId) {
    return <div className="text-sm text-slate-600">Missing run id.</div>;
  }

  const snapshotEvents = events.filter((e) => e.image_url && e.bbox && e.bbox.length === 4).slice(0, 6);

  return (
    <div className="space-y-5">
      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-xl font-semibold font-display">Test Run Detail</div>
          <div className="text-sm text-slate-600">Run ID: {runId}</div>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}
          {run ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-slate-700">
                <div>Godown: {run.godown_id}</div>
                <div>Camera: {run.camera_id}</div>
                <div>Zone: {run.zone_id ?? '-'}</div>
                <div>Status: {run.status}</div>
                <div>Created: {run.created_at ? formatUtc(run.created_at) : '-'}</div>
                <div>Updated: {run.updated_at ? formatUtc(run.updated_at) : '-'}</div>
              </div>
              <div className="flex items-center gap-3">
                <Button onClick={handleActivate} disabled={loading}>
                  Activate
                </Button>
                <Button variant="outline" onClick={handleDeactivate} disabled={loading}>
                  Deactivate
                </Button>
              </div>
            </>
          ) : (
            <div className="text-sm text-slate-600">Loading run detail…</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="text-lg font-semibold font-display">Detection snapshots</div>
          <div className="text-sm text-slate-600">Recent frames with bounding boxes.</div>
        </CardHeader>
        <CardContent>
          {snapshotEvents.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {snapshotEvents.map((event) => {
                const key = event.id?.toString() ?? event.event_id;
                const dims = sizes[key];
                const [x1, y1, x2, y2] = event.bbox as [number, number, number, number];
                const scaleX = dims ? 100 / dims.w : 0;
                const scaleY = dims ? 100 / dims.h : 0;
                return (
                  <div key={key} className="rounded-2xl border border-white/40 bg-white/70 p-3">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Event</div>
                    <div className="text-sm font-semibold text-slate-800">{event.event_type}</div>
                    <div className="mt-3 relative overflow-hidden rounded-xl border border-white/60 bg-slate-100">
                      <img
                        src={event.image_url ?? ''}
                        alt={event.event_type}
                        className="w-full h-auto block"
                        onLoad={(e) => {
                          const img = e.currentTarget;
                          setSizes((prev) => ({
                            ...prev,
                            [key]: { w: img.naturalWidth, h: img.naturalHeight }
                          }));
                        }}
                      />
                      {dims && (
                        <div
                          className="absolute border-2 border-amber-400"
                          style={{
                            left: `${x1 * scaleX}%`,
                            top: `${y1 * scaleY}%`,
                            width: `${(x2 - x1) * scaleX}%`,
                            height: `${(y2 - y1) * scaleY}%`
                          }}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-sm text-slate-600">No snapshots yet.</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="text-lg font-semibold font-display">Recent events</div>
          <div className="text-sm text-slate-600">Last 50 events for this camera.</div>
        </CardHeader>
        <CardContent>
          {events.length > 0 ? <EventsTable events={events} /> : <div className="text-sm text-slate-600">No events yet.</div>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="text-lg font-semibold font-display">Open alerts</div>
          <div className="text-sm text-slate-600">Alerts for this godown during the test run window.</div>
        </CardHeader>
        <CardContent>
          {alerts.length > 0 ? <AlertsTable alerts={alerts} /> : <div className="text-sm text-slate-600">No alerts yet.</div>}
        </CardContent>
      </Card>
    </div>
  );
}
