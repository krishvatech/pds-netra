'use client';

import type { MouseEvent, SyntheticEvent } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { createCamera, deleteCamera, getCameraZones, getEvents, getGodownDetail, getGodowns, getLiveCameras, updateCamera, updateCameraZones } from '@/lib/api';
import { getUser } from '@/lib/auth';
import type { GodownDetail, GodownListItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { ConfirmDeletePopover } from '@/components/ui/dialog';
import { EventsTable } from '@/components/tables/EventsTable';
import { friendlyErrorMessage } from '@/lib/friendly-error';

type AuthedLiveImageProps = {
  requestUrl: string;
  alt: string;
  className?: string;
  pollMs?: number;
  hiddenPollMs?: number;
  refreshToken?: number;
  onStatusChange?: (ok: boolean) => void;
  onLoad?: (evt: SyntheticEvent<HTMLImageElement, Event>) => void;
  onFrameMeta?: (meta: { ageSeconds: number | null; capturedAtUtc: string | null } | null) => void;
};

function buildLiveHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const user = getUser();
  if (user?.role) headers['X-User-Role'] = user.role;
  if (user?.godown_id) headers['X-User-Godown'] = String(user.godown_id);
  if (user?.district) headers['X-User-District'] = String(user.district);
  if (user?.name) headers['X-User-Name'] = String(user.name);
  return headers;
}

function appendCacheBust(url: string): string {
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}t=${Date.now()}`;
}

function AuthedLiveImage({
  requestUrl,
  alt,
  className,
  pollMs = 1000,
  hiddenPollMs = 5000,
  refreshToken = 0,
  onStatusChange,
  onLoad,
  onFrameMeta
}: AuthedLiveImageProps) {
  const [blobUrl, setBlobUrl] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    let activeController: AbortController | null = null;

    const sleep = (ms: number) =>
      new Promise<void>((resolve) => {
        window.setTimeout(() => resolve(), ms);
      });

    const run = async () => {
      if (!requestUrl) {
        setBlobUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return '';
        });
        onStatusChange?.(false);
        onFrameMeta?.(null);
        return;
      }

      const headers = buildLiveHeaders();
      while (!cancelled) {
        if (typeof document !== 'undefined' && document.hidden) {
          if (hiddenPollMs <= 0) return;
          await sleep(Math.max(hiddenPollMs, pollMs || 0));
          continue;
        }
        try {
          activeController = new AbortController();
          const resp = await fetch(appendCacheBust(requestUrl), {
            headers,
            cache: 'no-store',
            signal: activeController.signal
          });
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
          const capturedAtHeader = resp.headers.get('X-Frame-Captured-At');
          const ageHeader = resp.headers.get('X-Frame-Age-Seconds');
          let ageSeconds: number | null = null;
          if (ageHeader !== null) {
            const parsed = Number(ageHeader);
            if (Number.isFinite(parsed) && parsed >= 0) {
              ageSeconds = parsed;
            }
          }
          onFrameMeta?.({
            ageSeconds,
            capturedAtUtc: capturedAtHeader || null
          });
          const blob = await resp.blob();
          const nextUrl = URL.createObjectURL(blob);
          if (cancelled) {
            URL.revokeObjectURL(nextUrl);
            return;
          }
          setBlobUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev);
            return nextUrl;
          });
          onStatusChange?.(true);
        } catch {
          if (cancelled) return;
          setBlobUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev);
            return '';
          });
          onStatusChange?.(false);
          onFrameMeta?.(null);
        }
        if (pollMs <= 0) {
          return;
        }
        await sleep(pollMs);
      }
    };

    run();

    return () => {
      cancelled = true;
      if (activeController) activeController.abort();
    };
  }, [requestUrl, pollMs, hiddenPollMs, refreshToken]);

  if (!blobUrl) return null;
  return <img src={blobUrl} alt={alt} className={className} onLoad={onLoad} />;
}

function formatFrameAge(ageSeconds: number | null | undefined): string {
  if (ageSeconds === null || ageSeconds === undefined || !Number.isFinite(ageSeconds)) return 'Age: --';
  if (ageSeconds < 1) return 'Age: <1s';
  if (ageSeconds < 60) return `Age: ${Math.round(ageSeconds)}s`;
  const minutes = Math.floor(ageSeconds / 60);
  const seconds = Math.round(ageSeconds % 60);
  return `Age: ${minutes}m ${seconds}s`;
}

function formatCapturedTime(capturedAtUtc: string | null | undefined): string {
  if (!capturedAtUtc) return 'Captured: --';
  const d = new Date(capturedAtUtc);
  if (Number.isNaN(d.getTime())) return 'Captured: --';
  return `Captured: ${d.toLocaleTimeString()}`;
}

function frameAgeClass(ageSeconds: number | null | undefined): string {
  if (ageSeconds === null || ageSeconds === undefined || !Number.isFinite(ageSeconds)) return 'text-slate-200';
  if (ageSeconds <= 5) return 'text-emerald-300';
  if (ageSeconds <= 20) return 'text-amber-300';
  return 'text-rose-300';
}

const LIVE_STALE_THRESHOLD_SECONDS = (() => {
  const raw = process.env.NEXT_PUBLIC_LIVE_STALE_THRESHOLD_SECONDS ?? '30';
  const parsed = Number(raw);
  if (Number.isFinite(parsed) && parsed >= 0) return parsed;
  return 30;
})();

function isFrameStale(ageSeconds: number | null | undefined): boolean {
  if (ageSeconds === null || ageSeconds === undefined || !Number.isFinite(ageSeconds)) return false;
  return ageSeconds >= LIVE_STALE_THRESHOLD_SECONDS;
}

function ZoneOverlay({ zones }: { zones: any[] }) {
  if (!zones || zones.length === 0) return null;

  return (
    <svg
      className="absolute inset-0 h-full w-full pointer-events-none"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
    >
      {zones.map((z, i) => {
        const pts = (z?.polygon ?? [])
          .map(([x, y]: [number, number]) => `${x * 100},${y * 100}`)
          .join(' ');
        if (!pts) return null;

        return (
          <polygon
            key={z?.id ?? i}
            points={pts}
            fill="rgba(59, 130, 246, 0.10)"
            stroke="rgba(59, 130, 246, 0.95)"
            strokeWidth="0.6"
          />
        );
      })}
    </svg>
  );
}

export default function LiveCamerasPage() {
  const inlineErrorClass = 'text-xs text-red-400';
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [selectedGodown, setSelectedGodown] = useState<string>('');
  const [godownDetail, setGodownDetail] = useState<GodownDetail | null>(null);
  const [selectedCamera, setSelectedCamera] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [streamNonce, setStreamNonce] = useState(0);
  const [zoneCameraId, setZoneCameraId] = useState<string>('');
  const [zoneName, setZoneName] = useState<string>('zone_1');
  const [zonePoints, setZonePoints] = useState<Array<{ x: number; y: number }>>([]);
  const [zones, setZones] = useState<Array<{ id: string; polygon: number[][] }>>([]);
  const [zonesByCamera, setZonesByCamera] = useState<Record<string, any[]>>({});
  const [zonesLoading, setZonesLoading] = useState(false);
  const [zonesError, setZonesError] = useState<string | null>(null);
  const [zoneImageSize, setZoneImageSize] = useState<{ w: number; h: number } | null>(null);
  const [zoneImageNonce, setZoneImageNonce] = useState(0);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [zoneImageError, setZoneImageError] = useState(false);
  const [cameraErrors, setCameraErrors] = useState<Record<string, boolean>>({});
  const [cameraFrameMeta, setCameraFrameMeta] = useState<Record<string, { ageSeconds: number | null; capturedAtUtc: string | null }>>({});
  const [liveCameraIds, setLiveCameraIds] = useState<string[]>([]);
  const [recentEvents, setRecentEvents] = useState<any[]>([]);
  const [newCameraId, setNewCameraId] = useState('');
  const [newCameraLabel, setNewCameraLabel] = useState('');
  const [newCameraRole, setNewCameraRole] = useState('');
  const [newCameraRtsp, setNewCameraRtsp] = useState('');
  const [addCameraError, setAddCameraError] = useState<string | null>(null);
  const [addCameraLoading, setAddCameraLoading] = useState(false);
  const [showAddCameraDialog, setShowAddCameraDialog] = useState(false);
  const [editingCameraId, setEditingCameraId] = useState<string | null>(null);
  const [editLabel, setEditLabel] = useState('');
  const [editRole, setEditRole] = useState('');
  const [editRtsp, setEditRtsp] = useState('');
  const [editError, setEditError] = useState<string | null>(null);
  const [editLoading, setEditLoading] = useState(false);
  const [fullscreenCameraId, setFullscreenCameraId] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const resp = await getGodowns({ page: 1, page_size: 200 });
        const items = Array.isArray(resp) ? resp : resp.items;
        if (!mounted) return;
        setGodowns(items);
        if (items.length > 0 && !selectedGodown) {
          setSelectedGodown(items[0].godown_id);
        }
      } catch (_e) {
        if (mounted) setError('Unable to load godowns; please refresh.');
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    if (!selectedGodown) return;
    (async () => {
      try {
        const detail = await getGodownDetail(selectedGodown);
        if (!mounted) return;
        setGodownDetail(detail);
        if (detail.cameras.length > 0) {
          setSelectedCamera((prev) => prev || detail.cameras[0].camera_id);
          setZoneCameraId((prev) => prev || detail.cameras[0].camera_id);
        }
      } catch (_e) {
        if (mounted) setError('Unable to load cameras for this godown; try again.');
      }
    })();
    return () => {
      mounted = false;
    };
  }, [selectedGodown]);

  useEffect(() => {
    setCameraFrameMeta({});
  }, [selectedGodown]);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    if (fullscreenCameraId) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = prev;
      };
    }
  }, [fullscreenCameraId]);

  useEffect(() => {
    let mounted = true;
    if (!selectedGodown) return;
    const fetchEvents = async () => {
      try {
        const resp = await getEvents({ godown_id: selectedGodown, page: 1, page_size: 20 });
        const items = Array.isArray(resp) ? resp : resp.items;
        if (!mounted) return;
        setRecentEvents(items);
      } catch {
        if (mounted) setRecentEvents([]);
      }
    };
    fetchEvents();
    const timer = window.setInterval(fetchEvents, 10000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [selectedGodown]);

  const cameras = useMemo(() => {
    const list = godownDetail?.cameras ? [...godownDetail.cameras] : [];
    const rank = (role?: string | null) => {
      const r = (role || '').toUpperCase();
      if (r === 'GATE') return 0;
      if (r === 'PERIMETER') return 1;
      if (r === 'AISLE') return 2;
      return 3;
    };
    return list.sort((a, b) => {
      const diff = rank(a.role) - rank(b.role);
      if (diff !== 0) return diff;
      return String(a.label ?? a.camera_id).localeCompare(String(b.label ?? b.camera_id));
    });
  }, [godownDetail]);

  useEffect(() => {
    let mounted = true;
    if (!selectedGodown || cameras.length === 0) {
      setZonesByCamera({});
      return;
    }

    (async () => {
      try {
        const results = await Promise.all(
          cameras.map(async (cam) => {
            try {
              const resp = await getCameraZones(cam.camera_id, selectedGodown);
              return [cam.camera_id, resp?.zones ?? []] as const;
            } catch {
              return [cam.camera_id, []] as const;
            }
          })
        );

        if (!mounted) return;

        const map: Record<string, any[]> = {};
        for (const [camId, zs] of results) map[camId] = zs;
        setZonesByCamera(map);
      } catch {
        if (mounted) setZonesByCamera({});
      }
    })();

    return () => {
      mounted = false;
    };
  }, [selectedGodown, cameras]);

  useEffect(() => {
    let mounted = true;
    if (!zoneCameraId) return;
    setZonesLoading(true);
    setZonesError(null);
    (async () => {
      try {
        const resp = await getCameraZones(zoneCameraId, selectedGodown);
        if (!mounted) return;
        setZones(resp.zones ?? []);
      } catch (e) {
        if (!mounted) return;
        setZonesError(
          friendlyErrorMessage(
            e,
            'Unable to load camera zones right now. Please try again.'
          )
        );
      } finally {
        if (mounted) setZonesLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [zoneCameraId, selectedGodown]);
  const zoneImageUrl = useMemo(() => {
    if (!selectedGodown || !zoneCameraId) return '';
    if (liveCameraIds.length > 0 && !liveCameraIds.includes(zoneCameraId)) return '';
    return `/api/v1/live/frame/${encodeURIComponent(selectedGodown)}/${encodeURIComponent(zoneCameraId)}?z=${zoneImageNonce}`;
  }, [selectedGodown, zoneCameraId, zoneImageNonce, liveCameraIds]);

  useEffect(() => {
    if (zonePoints.length >= 3) {
      setZonesError(null);
    }
  }, [zonePoints.length]);

  useEffect(() => {
    let mounted = true;
    if (!selectedGodown) return;
    const fetchLive = async () => {
      try {
        const resp = await getLiveCameras(selectedGodown);
        if (mounted) setLiveCameraIds(resp.cameras ?? []);
      } catch {
        if (mounted) setLiveCameraIds([]);
      }
    };
    fetchLive();
    const timer = window.setInterval(fetchLive, 10000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [selectedGodown]);

  useEffect(() => {
    if (!liveCameraIds.length) return;
    if (!zoneCameraId || !liveCameraIds.includes(zoneCameraId)) {
      setZoneCameraId(liveCameraIds[0]);
      setZoneImageNonce((n) => n + 1);
    }
  }, [liveCameraIds, zoneCameraId]);

  const handleZoneClick = (evt: MouseEvent<HTMLDivElement>) => {
    if (!zoneImageSize) return;
    const rect = evt.currentTarget.getBoundingClientRect();
    const x = (evt.clientX - rect.left) / rect.width;
    const y = (evt.clientY - rect.top) / rect.height;
    setZonePoints((prev) => [...prev, { x, y }]);
  };

  const handleZoneMove = (evt: MouseEvent<HTMLDivElement>) => {
    if (dragIndex === null || !zoneImageSize) return;
    const rect = evt.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (evt.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (evt.clientY - rect.top) / rect.height));
    setZonePoints((prev) => prev.map((p, idx) => (idx === dragIndex ? { x, y } : p)));
  };

  const handleSaveZone = async () => {
    if (!zoneCameraId || !zoneImageSize || zonePoints.length < 3) {
      setZonesError('Add at least 3 points to save a zone.');
      return;
    }
    const polygon = zonePoints.map((p) => [p.x, p.y]);
    const nextZones = [
      ...zones.filter((z) => z.id !== zoneName.trim()),
      { id: zoneName.trim(), polygon }
    ];
    setZonesLoading(true);
    setZonesError(null);
    try {
      const resp = await updateCameraZones(zoneCameraId, selectedGodown, nextZones);
      setZones(resp.zones ?? []);
    } catch (_e) {
      setZonesError('Unable to save zone; please try again.');
    } finally {
      setZonesLoading(false);
    }
  };

  const loadZone = (zoneId: string) => {
    const z = zones.find((zone) => zone.id === zoneId);
    if (!z || !zoneImageSize) return;
    const points = z.polygon.map(([px, py]) => {
      // Backward compatibility: if value > 1, assume it's absolute pixels and normalize it.
      // New zones are saved as normalized (0-1).
      const x = px > 1 ? px / zoneImageSize.w : px;
      const y = py > 1 ? py / zoneImageSize.h : py;
      return { x, y };
    });
    setZoneName(zoneId);
    setZonePoints(points);
  };

  const deleteZone = async (zoneId: string) => {
    if (!zoneCameraId) return;
    const nextZones = zones.filter((zone) => zone.id !== zoneId);
    setZonesLoading(true);
    setZonesError(null);
    try {
      const resp = await updateCameraZones(zoneCameraId, selectedGodown, nextZones);
      setZones(resp.zones ?? []);
      if (zoneName === zoneId) {
        setZoneName('zone_1');
        setZonePoints([]);
      }
    } catch (_e) {
      setZonesError('Unable to delete zone; please try again.');
    } finally {
      setZonesLoading(false);
    }
  };

  const handleAddCamera = async () => {
    const cameraId = newCameraId.trim();
    const rtspUrl = newCameraRtsp.trim();
    if (!selectedGodown) {
      setAddCameraError('Select a godown first.');
      return;
    }
    if (!cameraId || !rtspUrl) {
      setAddCameraError('Camera ID and RTSP URL are required.');
      return;
    }
    setAddCameraLoading(true);
    setAddCameraError(null);
    try {
      await createCamera({
        camera_id: cameraId,
        godown_id: selectedGodown,
        label: newCameraLabel.trim() || undefined,
        role: newCameraRole.trim() || undefined,
        rtsp_url: rtspUrl,
        is_active: true
      });
      const detail = await getGodownDetail(selectedGodown);
      setGodownDetail(detail);
      setSelectedCamera(cameraId);
      setZoneCameraId(cameraId);
      setNewCameraId('');
      setNewCameraLabel('');
      setNewCameraRole('');
      setNewCameraRtsp('');
      setShowAddCameraDialog(false);
    } catch (_e) {
      setAddCameraError('Unable to add camera; verify details and try again.');
    } finally {
      setAddCameraLoading(false);
    }
  };

  const handleStartEdit = (cameraId: string) => {
    const cam = cameras.find((c) => c.camera_id === cameraId);
    if (!cam) return;
    setEditingCameraId(cameraId);
    setEditLabel(cam.label ?? '');
    setEditRole(cam.role ?? '');
    setEditRtsp(cam.rtsp_url ?? '');
    setEditError(null);
  };

  const handleCancelEdit = () => {
    setEditingCameraId(null);
    setEditLabel('');
    setEditRole('');
    setEditRtsp('');
    setEditError(null);
  };

  const handleSaveEdit = async () => {
    if (!editingCameraId) return;
    if (!editRtsp.trim()) {
      setEditError('RTSP URL is required.');
      return;
    }
    setEditLoading(true);
    setEditError(null);
    try {
      await updateCamera(
        editingCameraId,
        {
          label: editLabel.trim() || undefined,
          role: editRole.trim() || undefined,
          rtsp_url: editRtsp.trim()
        },
        selectedGodown
      );
      if (selectedGodown) {
        const detail = await getGodownDetail(selectedGodown);
        setGodownDetail(detail);
      }
      setEditingCameraId(null);
    } catch (_e) {
      setEditError('Unable to update the camera; please try again.');
    } finally {
      setEditLoading(false);
    }
  };

  const handleDeleteCamera = async (cameraId: string) => {
    if (!selectedGodown) return;
    setEditLoading(true);
    setEditError(null);
    try {
      await deleteCamera(cameraId, selectedGodown);
      const detail = await getGodownDetail(selectedGodown);
      setGodownDetail(detail);
      if (selectedCamera === cameraId) {
        setSelectedCamera(detail.cameras[0]?.camera_id ?? '');
      }
      if (zoneCameraId === cameraId) {
        setZoneCameraId(detail.cameras[0]?.camera_id ?? '');
      }
    } catch (_e) {
      setEditError('Unable to delete the camera; please try again.');
    } finally {
      setEditLoading(false);
    }
  };

  const handleOpenFullscreen = (cameraId: string) => {
    setFullscreenCameraId(cameraId);
    if (process.env.NODE_ENV !== 'production') {
      console.log('fullscreenCameraId', cameraId);
    }
  };

  const handleCloseFullscreen = () => {
    setFullscreenCameraId(null);
  };

  return (
    <div className="space-y-5 pt-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">Live Cameras</div>
          <div className="text-sm text-slate-300">Annotated live frames from edge.</div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="intel-banner">Streaming {selectedGodown || 'selected godown'}</div>
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Live stream
          </div>
        </div>
      </div>

      <Card className="hud-card">
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-lg font-semibold font-display">Live annotated feeds</div>
              <div className="text-sm text-slate-600">
                Live view for {selectedGodown || 'selected godown'} cameras.
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Select
                value={selectedGodown}
                onChange={(e) => setSelectedGodown(e.target.value)}
                options={godowns.map((g, idx) => ({
                  label: g.name ?? g.godown_id ?? `Godown ${idx + 1}`,
                  value: g.godown_id
                }))}
              />
              <Button className="btn-refresh" variant="outline" onClick={() => setStreamNonce((n) => n + 1)}>
                Refresh stream
              </Button>
              <Button onClick={() => { setAddCameraError(null); setShowAddCameraDialog(true); }}>
                + Add camera
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {cameras.length > 0 ? (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-2">
              {cameras.map((camera) => {
                const camUrl = `/api/v1/live/frame/${encodeURIComponent(selectedGodown)}/${encodeURIComponent(
                  camera.camera_id
                )}`;
                const isLive = liveCameraIds.length === 0 || liveCameraIds.includes(camera.camera_id);
                const hasError = cameraErrors[camera.camera_id];
                const frameMeta = cameraFrameMeta[camera.camera_id];
                const ageLabelClass = frameAgeClass(frameMeta?.ageSeconds);
                const stale = isFrameStale(frameMeta?.ageSeconds);
                const isEditing = editingCameraId === camera.camera_id;
                return (
                  <div
                    key={camera.camera_id}
                    className="incident-card relative p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <div className="text-base font-semibold text-slate-100">
                          {camera.label ?? camera.camera_id}
                        </div>
                        <div className="text-xs text-slate-400 flex flex-wrap items-center gap-2">
                          <span>{camera.camera_id}</span>
                          {camera.role ? (
                            <>
                              <span className="text-slate-500">•</span>
                              <span>{camera.role}</span>
                            </>
                          ) : null}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`hud-pill ${isLive && !hasError ? 'text-emerald-200 border-emerald-400/40' : ''}`}>
                          {isLive && !hasError ? 'LIVE' : 'OFFLINE'}
                        </span>
                        {!isEditing && (
                          <>
                            <button
                              type="button"
                              className="inline-flex h-8 w-8 items-center justify-center rounded-xl border border-white/20 bg-white/10 transition hover:bg-white/20 hover:border-white/40"
                              onClick={() => handleStartEdit(camera.camera_id)}
                              aria-label={`Edit ${camera.camera_id}`}
                              title="Edit"
                            >
                              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="#ffffff" strokeWidth="2">
                                <path d="M12 20h9" />
                                <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
                              </svg>
                            </button>
                            <ConfirmDeletePopover
                              title="Delete Camera"
                              description={`Are you sure you want to delete camera ${camera.camera_id}? This cannot be undone.`}
                              confirmText="Delete"
                              onConfirm={() => handleDeleteCamera(camera.camera_id)}
                              isBusy={editLoading}
                            >
                              <button
                                type="button"
                                className="inline-flex h-8 w-8 items-center justify-center rounded-xl border border-rose-500/40 bg-rose-500/10 transition hover:bg-rose-500/25 hover:border-rose-400/60"
                                aria-label={`Delete ${camera.camera_id}`}
                                title="Delete"
                              >
                                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="#fda4af" strokeWidth="2">
                                  <path d="M3 6h18" />
                                  <path d="M8 6V4h8v2" />
                                  <path d="M10 11v6" />
                                  <path d="M14 11v6" />
                                  <path d="M6 6l1 14h10l1-14" />
                                </svg>
                              </button>
                            </ConfirmDeletePopover>
                          </>
                        )}
                      </div>
                    </div>
                    {isEditing ? (
                      <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
                        <input
                          className="w-full rounded-xl px-3 py-2 text-sm input-field"
                          value={editLabel}
                          onChange={(e) => setEditLabel(e.target.value)}
                          placeholder="Label"
                        />
                        <input
                          className="w-full rounded-xl px-3 py-2 text-sm input-field"
                          value={editRole}
                          onChange={(e) => setEditRole(e.target.value)}
                          placeholder="Role"
                        />
                        <input
                          className="w-full rounded-xl px-3 py-2 text-sm input-field"
                          value={editRtsp}
                          onChange={(e) => setEditRtsp(e.target.value)}
                          placeholder="RTSP URL"
                        />
                        <div className="flex items-center gap-2 md:col-span-3">
                          <Button onClick={handleSaveEdit} disabled={editLoading}>
                            {editLoading ? 'Saving…' : 'Save'}
                          </Button>
                          <Button variant="outline" onClick={handleCancelEdit} disabled={editLoading}>
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : null}
                    {process.env.NODE_ENV !== 'production' && (
                      <div className="mt-2 text-xs text-white/70">
                        id={String((camera as any).id)} cam_id={String(camera.camera_id)} zones={(zonesByCamera[camera.camera_id] ?? []).length}
                      </div>
                    )}
                    <div className="relative mt-3 aspect-video w-full overflow-hidden rounded-2xl border border-white/40 bg-black/85 shadow-inner">
                      <div className={`absolute left-3 top-3 z-[2] rounded-md border border-white/30 bg-black/60 px-2 py-1 text-[11px] ${ageLabelClass}`}>
                        <div>{formatFrameAge(frameMeta?.ageSeconds)}</div>
                        <div>{formatCapturedTime(frameMeta?.capturedAtUtc)}</div>
                      </div>
                      {stale ? (
                        <div className="absolute left-3 top-16 z-[2] rounded-md border border-rose-300/80 bg-rose-600/90 px-2 py-1 text-[11px] font-semibold tracking-wide text-white">
                          STALE
                        </div>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => handleOpenFullscreen(camera.camera_id)}
                        className="absolute right-3 top-3 rounded-full border border-white/60 bg-black/50 p-2 text-white/90 shadow-sm transition hover:bg-black/70"
                        aria-label={`Open full screen for ${camera.camera_id}`}
                        title="Full screen"
                      >
                        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5" />
                        </svg>
                      </button>
                      {isLive && !hasError ? (
                        <div className="relative h-full w-full">
                          <AuthedLiveImage
                            requestUrl={camUrl}
                            alt={`Live ${camera.camera_id}`}
                            className="h-full w-full object-contain"
                            pollMs={fullscreenCameraId === camera.camera_id ? 0 : 1500}
                            hiddenPollMs={8000}
                            refreshToken={streamNonce}
                            onStatusChange={(ok) =>
                              setCameraErrors((prev) => ({ ...prev, [camera.camera_id]: !ok }))
                            }
                            onFrameMeta={(meta) =>
                              setCameraFrameMeta((prev) => ({
                                ...prev,
                                [camera.camera_id]: meta ?? { ageSeconds: null, capturedAtUtc: null }
                              }))
                            }
                          />
                          <ZoneOverlay zones={zonesByCamera[camera.camera_id] ?? []} />
                        </div>
                      ) : (
                        <div className="flex h-full w-full items-center justify-center text-sm text-slate-300">
                          Live feed not available yet.
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-sm text-slate-600">No cameras available for this godown.</div>
          )}
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Recent events</div>
          <div className="text-sm text-slate-600">Latest events for the selected godown.</div>
        </CardHeader>
        <CardContent>
          {recentEvents.length > 0 ? (
            <EventsTable events={recentEvents} showGodown={false} />
          ) : (
            <div className="text-sm text-slate-600">No recent events.</div>
          )}
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display text-slate-100">Zone editor</div>
          <div className="text-sm text-slate-400">Click to add polygon points, then save.</div>
        </CardHeader>
        <CardContent className="space-y-4">
          {zonesError && <p className={inlineErrorClass}>{zonesError}</p>}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="text-sm text-slate-400">
              Camera
              <div className="mt-2">
                <Select
                  value={zoneCameraId}
                  onChange={(e) => setZoneCameraId(e.target.value)}
                  options={cameras.map((c) => ({
                    label: c.label ?? c.camera_id,
                    value: c.camera_id
                  }))}
                />
              </div>
            </label>
            <label className="text-sm text-slate-400">
              Zone name
              <input
                className="mt-2 w-full rounded-xl px-3 py-2 text-sm input-field"
                value={zoneName}
                onChange={(e) => setZoneName(e.target.value)}
                placeholder="gate_inner"
              />
            </label>
            <div className="flex items-end gap-2">
              <Button variant="outline" className="text-slate-800 border-slate-300" onClick={() => setZonePoints((p) => p.slice(0, -1))}>
                Undo
              </Button>
              <Button variant="outline" className="text-slate-800 border-slate-300" onClick={() => setZonePoints([])}>
                Clear
              </Button>
              <Button onClick={handleSaveZone} disabled={zonesLoading}>
                Save zone
              </Button>
            </div>
          </div>

          {zones.length > 0 ? (
            <div className="flex flex-wrap gap-2 text-xs">
              {zones.map((zone) => (
                <div key={zone.id} className="flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1">
                  <button type="button" onClick={() => loadZone(zone.id)} className="text-slate-200 hover:text-white">
                    {zone.id}
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteZone(zone.id)}
                    className="text-rose-400 hover:text-rose-300"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-slate-500">No zones saved yet.</div>
          )}

          <div className="relative w-full overflow-hidden rounded-2xl border border-white/10 bg-black/80">
            {zoneImageUrl ? (
              <div
                className="relative w-full"
                onClick={handleZoneClick}
                onMouseMove={handleZoneMove}
                onMouseUp={() => setDragIndex(null)}
                onMouseLeave={() => setDragIndex(null)}
              >
                {zoneImageError ? (
                  <div className="text-sm text-slate-400 p-4">No live frame yet. Try Refresh frame.</div>
                ) : (
                  <AuthedLiveImage
                    requestUrl={zoneImageUrl}
                    alt="Zone reference"
                    className="w-full h-auto block"
                    pollMs={0}
                    onStatusChange={(ok) => setZoneImageError(!ok)}
                    onLoad={(e) => {
                      const img = e.currentTarget;
                      setZoneImageSize({ w: img.naturalWidth, h: img.naturalHeight });
                      setZoneImageError(false);
                    }}
                  />
                )}
                <svg
                  className="absolute inset-0 h-full w-full"
                  viewBox="0 0 100 100"
                  preserveAspectRatio="none"
                >
                  {zonePoints.length > 0 && (
                    <>
                      <polygon
                        points={zonePoints.map((p) => `${p.x * 100},${p.y * 100}`).join(' ')}
                        fill="rgba(245, 158, 11, 0.18)"
                        stroke="#f59e0b"
                        strokeWidth="0.6"
                      />
                      {zonePoints.map((p, idx) => (
                        <circle
                          key={`${p.x}-${p.y}-${idx}`}
                          cx={p.x * 100}
                          cy={p.y * 100}
                          r="1.6"
                          fill="#f59e0b"
                          onMouseDown={(evt) => {
                            evt.stopPropagation();
                            setDragIndex(idx);
                          }}
                        />
                      ))}
                    </>
                  )}
                </svg>
              </div>
            ) : (
              <div className="text-sm text-slate-400 p-4">Live frame not available for this camera.</div>
            )}
          </div>

          <div className="flex items-center gap-3 text-sm text-slate-400">
            <Button className="btn-refresh" variant="outline" onClick={() => setZoneImageNonce((n) => n + 1)}>
              Refresh frame
            </Button>
            <span>{zonePoints.length} points</span>
          </div>
        </CardContent>
      </Card>

      {showAddCameraDialog && (
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setShowAddCameraDialog(false); }}
        >
          <div className="hud-card w-full max-w-lg rounded-2xl p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-lg font-semibold font-display">Add camera</div>
                <div className="text-sm text-slate-500">Register a new camera to the selected godown.</div>
              </div>
              <button
                type="button"
                onClick={() => setShowAddCameraDialog(false)}
                className="rounded-full p-1 text-slate-400 hover:text-slate-200 transition"
                aria-label="Close"
              >
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
            {addCameraError && <p className={inlineErrorClass}>{addCameraError}</p>}
            <div className="grid grid-cols-1 gap-3">
              <label className="text-sm text-slate-600">
                Camera ID
                <input
                  className="mt-1 w-full rounded-xl px-3 py-2 text-sm input-field"
                  value={newCameraId}
                  onChange={(e) => setNewCameraId(e.target.value)}
                  placeholder="CAM_GATE_2"
                />
              </label>
              <label className="text-sm text-slate-600">
                Label
                <input
                  className="mt-1 w-full rounded-xl px-3 py-2 text-sm input-field"
                  value={newCameraLabel}
                  onChange={(e) => setNewCameraLabel(e.target.value)}
                  placeholder="Gate 2"
                />
              </label>
              <label className="text-sm text-slate-600">
                Role
                <input
                  className="mt-1 w-full rounded-xl px-3 py-2 text-sm input-field"
                  value={newCameraRole}
                  onChange={(e) => setNewCameraRole(e.target.value)}
                  placeholder="GATE"
                />
              </label>
              <label className="text-sm text-slate-600">
                RTSP URL
                <input
                  className="mt-1 w-full rounded-xl px-3 py-2 text-sm input-field"
                  value={newCameraRtsp}
                  onChange={(e) => setNewCameraRtsp(e.target.value)}
                  placeholder="rtsp://user:pass@ip/stream"
                />
              </label>
            </div>
            <div className="flex items-center justify-end gap-2 pt-1">
              <Button variant="outline" onClick={() => setShowAddCameraDialog(false)} disabled={addCameraLoading}>
                Cancel
              </Button>
              <Button onClick={handleAddCamera} disabled={addCameraLoading}>
                {addCameraLoading ? 'Adding…' : 'Set'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {fullscreenCameraId
        ? createPortal(
          <div className="fixed inset-0 z-[9999] h-screen w-screen bg-black/95 overflow-hidden">
            <div className="absolute inset-x-0 top-0 z-10 flex items-center justify-between px-6 py-4">
              <div className="text-sm font-semibold text-white">{fullscreenCameraId}</div>
              <Button variant="outline" onClick={handleCloseFullscreen}>
                Close
              </Button>
            </div>
            <div className="absolute inset-0 flex items-center justify-center px-6 pb-6 pt-16">
              <div className="relative max-h-full w-auto max-w-full">
                <AuthedLiveImage
                  requestUrl={`/api/v1/live/frame/${encodeURIComponent(selectedGodown)}/${encodeURIComponent(fullscreenCameraId)}`}
                  alt={`Live ${fullscreenCameraId}`}
                  className="max-h-full w-auto max-w-full object-contain"
                  pollMs={1500}
                  hiddenPollMs={8000}
                  refreshToken={streamNonce}
                  onFrameMeta={(meta) =>
                    setCameraFrameMeta((prev) => ({
                      ...prev,
                      [fullscreenCameraId]: meta ?? { ageSeconds: null, capturedAtUtc: null }
                    }))
                  }
                />
                <ZoneOverlay zones={zonesByCamera[fullscreenCameraId] ?? []} />
              </div>
            </div>
            <div className="absolute left-6 top-14 z-10 rounded-md border border-white/30 bg-black/60 px-2 py-1 text-xs text-slate-200">
              <div className={frameAgeClass(cameraFrameMeta[fullscreenCameraId]?.ageSeconds)}>
                {formatFrameAge(cameraFrameMeta[fullscreenCameraId]?.ageSeconds)}
              </div>
              <div>{formatCapturedTime(cameraFrameMeta[fullscreenCameraId]?.capturedAtUtc)}</div>
            </div>
            {isFrameStale(cameraFrameMeta[fullscreenCameraId]?.ageSeconds) ? (
              <div className="absolute left-6 top-28 z-10 rounded-md border border-rose-300/80 bg-rose-600/90 px-2 py-1 text-xs font-semibold tracking-wide text-white">
                STALE
              </div>
            ) : null}
          </div>,
          document.body
        )
        : null}

    </div>
  );
}
