'use client';

import { useEffect, useMemo, useState } from 'react';
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
import { friendlyErrorMessage } from '@/lib/friendly-error';

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
  const summaryStats = useMemo(() => {
    const snapshotsCount = snapshotTotal || snapshots.length;
    return {
      events: events.length,
      alerts: alerts.length,
      snapshots: snapshotsCount
    };
  }, [alerts.length, events.length, snapshotTotal, snapshots.length]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!runId) return;
      setError(null);
      try {
        const detail = await getTestRunDetail(runId);
        if (mounted) setRun(detail);
      } catch (e) {
        if (mounted)
          setError(
            friendlyErrorMessage(
              e,
              'Unable to load test run details. Please refresh or try again.'
            )
          );
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
        if (mounted)
          setError(
            friendlyErrorMessage(
              e,
              'Unable to load related events and alerts. Please try again later.'
            )
          );
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
      setError(
        friendlyErrorMessage(
          e,
          'Unable to activate the test run. Please try again.'
        )
      );
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
      setError(
        friendlyErrorMessage(
          e,
          'Unable to deactivate the test run. Please try again.'
        )
      );
    } finally {
      setLoading(false);
    }
  };

  if (!runId) {
    return <div className="text-sm text-slate-400">Missing run id.</div>;
  }

  const snapshotEvents = events.filter((e) => e.image_url && e.bbox && e.bbox.length === 4).slice(0, 6);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || '';
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
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Test run detail
          </div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Test Run Detail
          </div>
          <div className="text-sm text-slate-300">Inspect stream output, snapshots, and linked alerts.</div>
        </div>
        <div className="intel-banner">Run ID {runId}</div>
      </div>

      <div className="metric-grid">
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Run status</div>
          <div className="hud-value mt-2">{run?.status ?? '-'}</div>
          <div className="text-xs text-slate-400 mt-2">Godown {run?.godown_id ?? '-'}</div>
        </div>
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Events captured</div>
          <div className="hud-value mt-2">{summaryStats.events}</div>
          <div className="text-xs text-slate-400 mt-2">Latest 50 events sampled</div>
        </div>
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Open alerts</div>
          <div className="hud-value mt-2">{summaryStats.alerts}</div>
          <div className="text-xs text-slate-400 mt-2">Godown alert feed</div>
        </div>
        <div className="hud-card p-5 animate-fade-up">
          <div className="hud-label">Snapshots</div>
          <div className="hud-value mt-2">{summaryStats.snapshots}</div>
          <div className="text-xs text-slate-400 mt-2">Frame captures</div>
        </div>
      </div>

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-xl font-semibold font-display">Run metadata</div>
          <div className="text-sm text-slate-300">Activation, status, and routing context.</div>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}
          {run ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-slate-200">
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
            <div className="text-sm text-slate-400">Loading run detail…</div>
          )}
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Live annotated feed</div>
          <div className="text-sm text-slate-300">Real-time overlay while the test run is processing.</div>
        </CardHeader>
        <CardContent>
          {run ? (
            <img
              src={streamUrl}
              alt="Live annotated feed"
              className="w-full rounded-2xl border border-white/20 bg-black/80"
            />
          ) : (
            <div className="text-sm text-slate-400">Loading live feed…</div>
          )}
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Annotated video</div>
          <div className="text-sm text-slate-300">Playback of the test run with bounding boxes.</div>
        </CardHeader>
        <CardContent>
          {run ? (
            videoError ? (
              <div className="flex items-center justify-between text-sm text-slate-400">
                <span>Annotated video not available yet.</span>
                <Button variant="outline" onClick={() => setVideoError(false)}>
                  Retry
                </Button>
              </div>
            ) : (
              <video
                controls
                className="w-full rounded-2xl border border-white/20 bg-black/80"
                src={annotatedUrl}
                onError={() => setVideoError(true)}
              />
            )
          ) : (
            <div className="text-sm text-slate-400">Loading video…</div>
          )}
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Detection snapshots</div>
          <div className="text-sm text-slate-300">Recent frames with bounding boxes.</div>
        </CardHeader>
        <CardContent>
          {snapshots.length > 0 ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {snapshots.map((url) => (
                  <div key={url} className="incident-card p-3">
                    <img
                      src={url.startsWith('/media/') ? `${apiBase}${url}` : url}
                      alt="Detection snapshot"
                      className="w-full rounded-xl border border-white/20"
                    />
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-center justify-between text-sm text-slate-400">
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
                    : event.event_type === 'ANIMAL_INTRUSION' && (event.meta?.animal_species || event.meta?.animal_label)
                      ? `Animal Intrusion: ${event.meta?.animal_label ?? event.meta?.animal_species}`
                      : event.event_type;
                return (
                  <div key={key} className="incident-card p-3">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Event</div>
                    <div className="text-sm font-semibold text-slate-100">{eventLabel}</div>
                    <div className="mt-3 relative overflow-hidden rounded-xl border border-white/20 bg-slate-900">
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
            <div className="text-sm text-slate-400">No snapshots yet.</div>
          )}
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Recent events</div>
          <div className="text-sm text-slate-300">Last 50 events for this camera.</div>
        </CardHeader>
        <CardContent>
          {events.length > 0 ? <EventsTable events={events} /> : <div className="text-sm text-slate-400">No events yet.</div>}
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Open alerts</div>
          <div className="text-sm text-slate-300">Alerts for this godown during the test run window.</div>
        </CardHeader>
        <CardContent>
          {alerts.length > 0 ? <AlertsTable alerts={alerts} /> : <div className="text-sm text-slate-400">No alerts yet.</div>}
        </CardContent>
      </Card>
    </div>
  );
}
