'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import {
  activateTestRun,
  deactivateTestRun,
  getAlerts,
  getEvents,
  getTestRunDetail,
  getTestRunSnapshots
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
  const [videoError, setVideoError] = useState(false);
  const [snapshots, setSnapshots] = useState<string[]>([]);
  const [snapshotPage, setSnapshotPage] = useState(1);
  const [snapshotTotal, setSnapshotTotal] = useState(0);
  const snapshotPageSize = 6;
  const [streamNonce, setStreamNonce] = useState(0);

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
    if (!runId) return;
    if (run?.status === 'COMPLETED') return;
    const timer = window.setInterval(async () => {
      try {
        const detail = await getTestRunDetail(runId);
        setRun(detail);
      } catch {
        // Ignore polling errors
      }
    }, 4000);
    return () => window.clearInterval(timer);
  }, [runId, run?.status]);

  useEffect(() => {
    if (run?.status === 'COMPLETED') {
      setVideoError(false);
    }
  }, [run?.status]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!run?.godown_id || !run?.camera_id) return;
      try {
        let eventsResp = await getEvents({
          godown_id: run.godown_id,
          camera_id: run.camera_id,
          date_from: run.created_at ?? undefined,
          page: 1,
          page_size: 50
        });
        let eventsItems = Array.isArray(eventsResp) ? eventsResp : eventsResp.items;
        if (!eventsItems.length) {
          eventsResp = await getEvents({
            godown_id: run.godown_id,
            camera_id: run.camera_id,
            page: 1,
            page_size: 50
          });
          eventsItems = Array.isArray(eventsResp) ? eventsResp : eventsResp.items;
        }
        let alertsResp = await getAlerts({
          godown_id: run.godown_id,
          status: 'OPEN',
          date_from: run.created_at ?? undefined,
          page: 1,
          page_size: 50
        });
        let alertsItems = Array.isArray(alertsResp) ? alertsResp : alertsResp.items;
        if (!alertsItems.length) {
          alertsResp = await getAlerts({
            godown_id: run.godown_id,
            status: 'OPEN',
            page: 1,
            page_size: 50
          });
          alertsItems = Array.isArray(alertsResp) ? alertsResp : alertsResp.items;
        }
        const snapsResp = await getTestRunSnapshots(run.run_id, run.camera_id, {
          page: snapshotPage,
          page_size: snapshotPageSize
        });
        if (mounted) {
          const runTaggedEvents = eventsItems.filter((e) => e.meta?.extra?.run_id === run.run_id);
          const runTaggedAlerts = alertsItems.filter((a) => a.key_meta?.run_id === run.run_id);
          setEvents(runTaggedEvents.length > 0 ? runTaggedEvents : eventsItems);
          setAlerts(runTaggedAlerts.length > 0 ? runTaggedAlerts : alertsItems);
          setSnapshots(snapsResp.items ?? []);
          setSnapshotTotal(snapsResp.total ?? 0);
        }
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load related events');
      }
    })();
    return () => {
      mounted = false;
    };
  }, [run?.godown_id, run?.camera_id, snapshotPage]);

  const handleActivate = async () => {
    if (!run) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await activateTestRun(run.run_id);
      if (resp.run) setRun(resp.run);
      setStreamNonce((n) => n + 1);
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
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8001';
  const resolveMediaUrl = (url?: string | null) => {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    if (url.startsWith('/media/')) return `${apiBase}${url}`;
    return url;
  };
  const annotatedUrl = run
    ? `${apiBase}/media/annotated/${encodeURIComponent(run.godown_id)}/${encodeURIComponent(run.run_id)}/${encodeURIComponent(run.camera_id)}.mp4`
    : '';
  const streamUrl = run
    ? `/api/v1/test-runs/${encodeURIComponent(run.run_id)}/stream/${encodeURIComponent(run.camera_id)}?v=${streamNonce}`
    : '';

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
          <div className="text-lg font-semibold font-display">Live annotated feed</div>
          <div className="text-sm text-slate-600">Real-time overlay while the test run is processing.</div>
        </CardHeader>
        <CardContent>
          {run ? (
            <img
              src={streamUrl}
              alt="Live annotated feed"
              className="w-full rounded-2xl border border-white/40 bg-black/80"
            />
          ) : (
            <div className="text-sm text-slate-600">Loading live feed…</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="text-lg font-semibold font-display">Annotated video</div>
          <div className="text-sm text-slate-600">Playback of the test run with bounding boxes.</div>
        </CardHeader>
        <CardContent>
          {run ? (
            videoError ? (
              <div className="flex items-center justify-between text-sm text-slate-600">
                <span>Annotated video not available yet.</span>
                <Button variant="outline" onClick={() => setVideoError(false)}>
                  Retry
                </Button>
              </div>
            ) : (
              <video
                controls
                className="w-full rounded-2xl border border-white/40 bg-black/80"
                src={annotatedUrl}
                onError={() => setVideoError(true)}
              />
            )
          ) : (
            <div className="text-sm text-slate-600">Loading video…</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="text-lg font-semibold font-display">Detection snapshots</div>
          <div className="text-sm text-slate-600">Recent frames with bounding boxes.</div>
        </CardHeader>
        <CardContent>
          {snapshots.length > 0 ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {snapshots.map((url) => (
                  <div key={url} className="rounded-2xl border border-white/40 bg-white/70 p-3">
                    <img
                      src={url.startsWith('/media/') ? `${apiBase}${url}` : url}
                      alt="Detection snapshot"
                      className="w-full rounded-xl border border-white/60"
                    />
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
                <div>
                  Page {snapshotPage} of {Math.max(1, Math.ceil(snapshotTotal / snapshotPageSize))}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setSnapshotPage((p) => Math.max(1, p - 1))}
                    disabled={snapshotPage <= 1}
                  >
                    Prev
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setSnapshotPage((p) => p + 1)}
                    disabled={snapshotPage >= Math.ceil(snapshotTotal / snapshotPageSize)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          ) : snapshotEvents.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {snapshotEvents.map((event) => {
                const key = event.id?.toString() ?? event.event_id;
                const dims = sizes[key];
                const [x1, y1, x2, y2] = event.bbox as [number, number, number, number];
                const scaleX = dims ? 100 / dims.w : 0;
                const scaleY = dims ? 100 / dims.h : 0;
                const eventLabel =
                  event.event_type === 'UNAUTH_PERSON' && event.meta?.movement_type
                    ? `Detected: ${event.meta.movement_type}`
                    : event.event_type;
                return (
                  <div key={key} className="rounded-2xl border border-white/40 bg-white/70 p-3">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Event</div>
                    <div className="text-sm font-semibold text-slate-800">{eventLabel}</div>
                    <div className="mt-3 relative overflow-hidden rounded-xl border border-white/60 bg-slate-100">
                      <img
                        src={resolveMediaUrl(event.image_url)}
                        alt={eventLabel}
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
