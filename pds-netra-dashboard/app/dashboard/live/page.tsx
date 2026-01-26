'use client';

import type { MouseEvent } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { createCamera, deleteCamera, getCameraZones, getEvents, getGodownDetail, getGodowns, getLiveCameras, updateCamera, updateCameraZones } from '@/lib/api';
import type { GodownDetail, GodownListItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { EventsTable } from '@/components/tables/EventsTable';

export default function LiveCamerasPage() {
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
  const [zonesLoading, setZonesLoading] = useState(false);
  const [zonesError, setZonesError] = useState<string | null>(null);
  const [zoneImageSize, setZoneImageSize] = useState<{ w: number; h: number } | null>(null);
  const [zoneImageNonce, setZoneImageNonce] = useState(0);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [zoneImageError, setZoneImageError] = useState(false);
  const [cameraErrors, setCameraErrors] = useState<Record<string, boolean>>({});
  const [liveCameraIds, setLiveCameraIds] = useState<string[]>([]);
  const [recentEvents, setRecentEvents] = useState<any[]>([]);
  const [newCameraId, setNewCameraId] = useState('');
  const [newCameraLabel, setNewCameraLabel] = useState('');
  const [newCameraRole, setNewCameraRole] = useState('');
  const [newCameraRtsp, setNewCameraRtsp] = useState('');
  const [addCameraError, setAddCameraError] = useState<string | null>(null);
  const [addCameraLoading, setAddCameraLoading] = useState(false);
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
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load godowns');
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
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : 'Failed to load cameras');
      }
    })();
    return () => {
      mounted = false;
    };
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
    const timer = window.setInterval(fetchEvents, 5000);
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
    if (!zoneCameraId) return;
    setZonesLoading(true);
    setZonesError(null);
    (async () => {
      try {
        const resp = await getCameraZones(zoneCameraId);
        if (!mounted) return;
        setZones(resp.zones ?? []);
      } catch (e) {
        if (!mounted) return;
        setZonesError(e instanceof Error ? e.message : 'Failed to load zones');
      } finally {
        if (mounted) setZonesLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [zoneCameraId]);
  const streamUrl = useMemo(() => {
    if (!selectedGodown || !selectedCamera) return '';
    return `/media/live/${encodeURIComponent(selectedGodown)}/${encodeURIComponent(selectedCamera)}_latest.jpg?ts=${streamNonce}`;
  }, [selectedGodown, selectedCamera, streamNonce]);
  const zoneImageUrl = useMemo(() => {
    if (!selectedGodown || !zoneCameraId) return '';
    if (liveCameraIds.length > 0 && !liveCameraIds.includes(zoneCameraId)) return '';
    return `/api/v1/live/frame/${encodeURIComponent(selectedGodown)}/${encodeURIComponent(zoneCameraId)}?z=${zoneImageNonce}`;
  }, [selectedGodown, zoneCameraId, zoneImageNonce, liveCameraIds]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setStreamNonce((n) => n + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

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
    const timer = window.setInterval(fetchLive, 5000);
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
    const polygon = zonePoints.map((p) => [
      Math.round(p.x * zoneImageSize.w),
      Math.round(p.y * zoneImageSize.h)
    ]);
    const nextZones = [
      ...zones.filter((z) => z.id !== zoneName.trim()),
      { id: zoneName.trim(), polygon }
    ];
    setZonesLoading(true);
    setZonesError(null);
    try {
      const resp = await updateCameraZones(zoneCameraId, nextZones);
      setZones(resp.zones ?? []);
    } catch (e) {
      setZonesError(e instanceof Error ? e.message : 'Failed to save zone');
    } finally {
      setZonesLoading(false);
    }
  };

  const loadZone = (zoneId: string) => {
    const z = zones.find((zone) => zone.id === zoneId);
    if (!z || !zoneImageSize) return;
    const points = z.polygon.map(([x, y]) => ({
      x: x / zoneImageSize.w,
      y: y / zoneImageSize.h
    }));
    setZoneName(zoneId);
    setZonePoints(points);
  };

  const deleteZone = async (zoneId: string) => {
    if (!zoneCameraId) return;
    const nextZones = zones.filter((zone) => zone.id !== zoneId);
    setZonesLoading(true);
    setZonesError(null);
    try {
      const resp = await updateCameraZones(zoneCameraId, nextZones);
      setZones(resp.zones ?? []);
      if (zoneName === zoneId) {
        setZoneName('zone_1');
        setZonePoints([]);
      }
    } catch (e) {
      setZonesError(e instanceof Error ? e.message : 'Failed to delete zone');
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
    } catch (e) {
      setAddCameraError(e instanceof Error ? e.message : 'Failed to add camera');
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
      await updateCamera(editingCameraId, {
        label: editLabel.trim() || undefined,
        role: editRole.trim() || undefined,
        rtsp_url: editRtsp.trim()
      });
      if (selectedGodown) {
        const detail = await getGodownDetail(selectedGodown);
        setGodownDetail(detail);
      }
      setEditingCameraId(null);
    } catch (e) {
      setEditError(e instanceof Error ? e.message : 'Failed to update camera');
    } finally {
      setEditLoading(false);
    }
  };

  const handleDeleteCamera = async (cameraId: string) => {
    if (!selectedGodown) return;
    const ok = window.confirm(`Delete camera ${cameraId}? This cannot be undone.`);
    if (!ok) return;
    setEditLoading(true);
    setEditError(null);
    try {
      await deleteCamera(cameraId);
      const detail = await getGodownDetail(selectedGodown);
      setGodownDetail(detail);
      if (selectedCamera === cameraId) {
        setSelectedCamera(detail.cameras[0]?.camera_id ?? '');
      }
      if (zoneCameraId === cameraId) {
        setZoneCameraId(detail.cameras[0]?.camera_id ?? '');
      }
    } catch (e) {
      setEditError(e instanceof Error ? e.message : 'Failed to delete camera');
    } finally {
      setEditLoading(false);
    }
  };

  const handleOpenFullscreen = (cameraId: string) => {
    setFullscreenCameraId(cameraId);
  };

  const handleCloseFullscreen = () => {
    setFullscreenCameraId(null);
  };

  return (
    <div className="space-y-5">
      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-xl font-semibold font-display">Live Cameras</div>
          <div className="text-sm text-slate-600">Annotated live frames from edge.</div>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}
          {addCameraError && <ErrorBanner message={addCameraError} onRetry={() => setAddCameraError(null)} />}
          {editError && <ErrorBanner message={editError} onRetry={() => setEditError(null)} />}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="text-sm text-slate-600">
              Godown
              <select
                className="mt-2 w-full rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-slate-800"
                value={selectedGodown}
                onChange={(e) => setSelectedGodown(e.target.value)}
              >
                {godowns.map((g, idx) => (
                  <option key={`${g.godown_id}-${idx}`} value={g.godown_id}>
                    {g.name ?? g.godown_id ?? `Godown ${idx + 1}`}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-end">
              <Button variant="outline" onClick={() => setStreamNonce((n) => n + 1)}>
                Refresh stream
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <label className="text-sm text-slate-600">
              Camera ID
              <input
                className="mt-2 w-full rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-slate-800"
                value={newCameraId}
                onChange={(e) => setNewCameraId(e.target.value)}
                placeholder="CAM_GATE_2"
              />
            </label>
            <label className="text-sm text-slate-600">
              Label
              <input
                className="mt-2 w-full rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-slate-800"
                value={newCameraLabel}
                onChange={(e) => setNewCameraLabel(e.target.value)}
                placeholder="Gate 2"
              />
            </label>
            <label className="text-sm text-slate-600">
              Role
              <input
                className="mt-2 w-full rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-slate-800"
                value={newCameraRole}
                onChange={(e) => setNewCameraRole(e.target.value)}
                placeholder="GATE"
              />
            </label>
            <label className="text-sm text-slate-600">
              RTSP URL
              <input
                className="mt-2 w-full rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-slate-800"
                value={newCameraRtsp}
                onChange={(e) => setNewCameraRtsp(e.target.value)}
                placeholder="rtsp://user:pass@ip/stream"
              />
            </label>
          </div>
          <div className="flex items-center">
            <Button onClick={handleAddCamera} disabled={addCameraLoading}>
              {addCameraLoading ? 'Adding…' : 'Add camera'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="text-lg font-semibold font-display">Live annotated feeds</div>
          <div className="text-sm text-slate-600">
            Live view for {selectedGodown || 'selected godown'} cameras.
          </div>
        </CardHeader>
        <CardContent>
          {cameras.length > 0 ? (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-2">
              {cameras.map((camera) => {
                const camUrl = `/api/v1/live/frame/${encodeURIComponent(selectedGodown)}/${encodeURIComponent(
                  camera.camera_id
                )}?ts=${streamNonce}`;
                const isLive = liveCameraIds.length === 0 || liveCameraIds.includes(camera.camera_id);
                const hasError = cameraErrors[camera.camera_id];
                const isEditing = editingCameraId === camera.camera_id;
                return (
                  <div
                    key={camera.camera_id}
                    className="relative rounded-3xl border border-white/50 bg-white/70 p-4 shadow-sm"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <div className="text-base font-semibold text-slate-900">
                          {camera.label ?? camera.camera_id}
                        </div>
                        <div className="text-xs text-slate-500">
                          {camera.camera_id} {camera.role ? `• ${camera.role}` : ''}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                            isLive && !hasError ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'
                          }`}
                        >
                          {isLive && !hasError ? 'LIVE' : 'OFFLINE'}
                        </span>
                        {!isEditing && (
                          <>
                            <Button
                              variant="outline"
                              onClick={() => handleStartEdit(camera.camera_id)}
                              aria-label={`Edit ${camera.camera_id}`}
                              title="Edit"
                            >
                              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M12 20h9" />
                                <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
                              </svg>
                            </Button>
                            <Button
                              variant="outline"
                              onClick={() => handleDeleteCamera(camera.camera_id)}
                              aria-label={`Delete ${camera.camera_id}`}
                              title="Delete"
                            >
                              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M3 6h18" />
                                <path d="M8 6V4h8v2" />
                                <path d="M10 11v6" />
                                <path d="M14 11v6" />
                                <path d="M6 6l1 14h10l1-14" />
                              </svg>
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                    {isEditing ? (
                      <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
                        <input
                          className="w-full rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-slate-800"
                          value={editLabel}
                          onChange={(e) => setEditLabel(e.target.value)}
                          placeholder="Label"
                        />
                        <input
                          className="w-full rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-slate-800"
                          value={editRole}
                          onChange={(e) => setEditRole(e.target.value)}
                          placeholder="Role"
                        />
                        <input
                          className="w-full rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-slate-800"
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
                    <div className="relative mt-3 aspect-video w-full overflow-hidden rounded-2xl border border-white/40 bg-black/85 shadow-inner">
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
                        <img
                          src={camUrl}
                          alt={`Live ${camera.camera_id}`}
                          className="h-full w-full object-contain"
                          onError={() =>
                            setCameraErrors((prev) => ({ ...prev, [camera.camera_id]: true }))
                          }
                          onLoad={() =>
                            setCameraErrors((prev) => ({ ...prev, [camera.camera_id]: false }))
                          }
                        />
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

      <Card>
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

      <Card>
        <CardHeader>
          <div className="text-lg font-semibold font-display">Zone editor</div>
          <div className="text-sm text-slate-600">Click to add polygon points, then save.</div>
        </CardHeader>
        <CardContent className="space-y-4">
          {zonesError && <ErrorBanner message={zonesError} onRetry={() => setZonesError(null)} />}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="text-sm text-slate-600">
              Camera
              <select
                className="mt-2 w-full rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-slate-800"
                value={zoneCameraId}
                onChange={(e) => setZoneCameraId(e.target.value)}
              >
                {cameras.map((c) => (
                  <option key={c.camera_id} value={c.camera_id}>
                    {c.label ?? c.camera_id}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm text-slate-600">
              Zone name
              <input
                className="mt-2 w-full rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-slate-800"
                value={zoneName}
                onChange={(e) => setZoneName(e.target.value)}
                placeholder="gate_inner"
              />
            </label>
            <div className="flex items-end gap-2">
              <Button variant="outline" onClick={() => setZonePoints((p) => p.slice(0, -1))}>
                Undo
              </Button>
              <Button variant="outline" onClick={() => setZonePoints([])}>
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
                <div key={zone.id} className="flex items-center gap-2 rounded-full border border-white/30 bg-white/60 px-3 py-1">
                  <button type="button" onClick={() => loadZone(zone.id)} className="text-slate-700">
                    {zone.id}
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteZone(zone.id)}
                    className="text-red-500 hover:text-red-600"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-slate-500">No zones saved yet.</div>
          )}

          <div className="relative w-full overflow-hidden rounded-2xl border border-white/40 bg-black/80">
            {zoneImageUrl ? (
              <div
                className="relative w-full"
                onClick={handleZoneClick}
                onMouseMove={handleZoneMove}
                onMouseUp={() => setDragIndex(null)}
                onMouseLeave={() => setDragIndex(null)}
              >
                {zoneImageError ? (
                  <div className="text-sm text-slate-600 p-4">No live frame yet. Try Refresh frame.</div>
                ) : (
                  <img
                    src={zoneImageUrl}
                    alt="Zone reference"
                    className="w-full h-auto block"
                    onError={() => setZoneImageError(true)}
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
              <div className="text-sm text-slate-600 p-4">Live frame not available for this camera.</div>
            )}
          </div>

          <div className="flex items-center gap-2 text-sm text-slate-600">
            <Button variant="outline" onClick={() => setZoneImageNonce((n) => n + 1)}>
              Refresh frame
            </Button>
            <span>{zonePoints.length} points</span>
          </div>
        </CardContent>
      </Card>

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
                <img
                  src={`/api/v1/live/frame/${encodeURIComponent(selectedGodown)}/${encodeURIComponent(fullscreenCameraId)}?ts=${streamNonce}`}
                  alt={`Live ${fullscreenCameraId}`}
                  className="max-h-full w-auto max-w-full object-contain"
                />
              </div>
            </div>,
            document.body
          )
        : null}


    </div>
  );
}
