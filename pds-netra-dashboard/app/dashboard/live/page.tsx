'use client';

import type { MouseEvent } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { getCameraZones, getGodownDetail, getGodowns, getLiveCameras, updateCameraZones } from '@/lib/api';
import type { GodownDetail, GodownListItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';

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

  return (
    <div className="space-y-5">
      <Card className="animate-fade-up">
        <CardHeader>
          <div className="text-xl font-semibold font-display">Live Cameras</div>
          <div className="text-sm text-slate-600">Annotated live frames from edge.</div>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}
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
            <div className="grid grid-cols-1 gap-8">
              {cameras.map((camera) => {
                const camUrl = `/api/v1/live/frame/${encodeURIComponent(selectedGodown)}/${encodeURIComponent(
                  camera.camera_id
                )}?ts=${streamNonce}`;
                if (cameraErrors[camera.camera_id] || (liveCameraIds.length > 0 && !liveCameraIds.includes(camera.camera_id))) {
                  return null;
                }
                return (
                  <div key={camera.camera_id} className="space-y-3">
                    <div className="text-base font-semibold text-slate-800">
                      {camera.label ?? camera.camera_id}
                    </div>
                    <div className="aspect-video w-full overflow-hidden rounded-3xl border border-white/40 bg-black/80 shadow-inner">
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
    </div>
  );
}
