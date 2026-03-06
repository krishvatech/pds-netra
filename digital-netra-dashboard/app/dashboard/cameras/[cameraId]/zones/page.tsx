'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import { getSessionUser, getToken } from '@/lib/auth';
import type { Camera, Zone } from '@/lib/types';
import { createZone, deleteZone, getCameras, getZones, updateZone } from '@/lib/api';

type FormMode = 'create' | 'edit';

const EMPTY_POINTS: Array<{ x: number; y: number }> = [];

type AuthedLiveImageProps = {
  requestUrl: string;
  alt: string;
  className?: string;
  refreshToken?: number;
  onStatusChange?: (ok: boolean) => void;
  onLoad?: (evt: React.SyntheticEvent<HTMLImageElement, Event>) => void;
};

function AuthedLiveImage({ requestUrl, alt, className, refreshToken = 0, onStatusChange, onLoad }: AuthedLiveImageProps) {
  const token = getToken();
  const [blobUrl, setBlobUrl] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    let activeController: AbortController | null = null;

    const run = async () => {
      if (!requestUrl) {
        setBlobUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return '';
        });
        onStatusChange?.(false);
        return;
      }
      try {
        activeController = new AbortController();
        const headers = new Headers();
        if (token) headers.set('Authorization', `Bearer ${token}`);
        const resp = await fetch(`${requestUrl}${requestUrl.includes('?') ? '&' : '?'}t=${Date.now()}`, {
          headers,
          cache: 'no-store',
          signal: activeController.signal
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
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
      }
    };

    run();
    return () => {
      cancelled = true;
      if (activeController) activeController.abort();
    };
  }, [requestUrl, refreshToken, token, onStatusChange]);

  if (!blobUrl) return null;
  return <img src={blobUrl} alt={alt} className={className} onLoad={onLoad} />;
}

export default function ZonesPage() {
  const router = useRouter();
  const params = useParams<{ cameraId: string }>();
  const cameraId = params?.cameraId as string;

  const [camera, setCamera] = useState<Camera | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>('create');
  const [zoneName, setZoneName] = useState('');
  const [zoneActive, setZoneActive] = useState(true);
  const [zonePoints, setZonePoints] = useState<Array<{ x: number; y: number }>>(EMPTY_POINTS);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [zoneImageSize, setZoneImageSize] = useState<{ w: number; h: number } | null>(null);
  const [zoneImageError, setZoneImageError] = useState(false);
  const [zoneImageNonce, setZoneImageNonce] = useState(0);
  const [activeZone, setActiveZone] = useState<Zone | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Zone | null>(null);

  useEffect(() => {
    async function guard() {
      const user = await getSessionUser();
      if (!user) {
        router.replace('/auth/login');
        return;
      }
      await loadAll();
    }
    guard();
  }, [router]);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [cameraList, zoneList] = await Promise.all([getCameras(), getZones(cameraId)]);
      setCamera(cameraList.find((item) => item.id === cameraId) || null);
      setZones(zoneList);
    } catch {
      setError('Unable to load zones right now.');
    } finally {
      setLoading(false);
    }
  }

  const zoneCount = useMemo(() => zones.length, [zones]);

  function openCreate() {
    setFormMode('create');
    setActiveZone(null);
    setZoneName('');
    setZoneActive(true);
    setZonePoints(EMPTY_POINTS);
    setActionError(null);
    setShowForm(true);
  }

  function openEdit(zone: Zone) {
    setFormMode('edit');
    setActiveZone(zone);
    setZoneName(zone.zone_name);
    setZoneActive(zone.is_active);
    const points = zone.polygon.map(([px, py]) => {
      const x = px > 1 && zoneImageSize ? px / zoneImageSize.w : px;
      const y = py > 1 && zoneImageSize ? py / zoneImageSize.h : py;
      return { x, y };
    });
    setZonePoints(points);
    setActionError(null);
    setShowForm(true);
  }

  function closeForm() {
    if (saving) return;
    setShowForm(false);
    setActionError(null);
  }

  const zoneImageUrl = useMemo(() => {
    if (!cameraId) return '';
    return `/api/v1/live/frame/${cameraId}?z=${zoneImageNonce}`;
  }, [cameraId, zoneImageNonce]);

  const handleZoneClick = (evt: React.MouseEvent<HTMLDivElement>) => {
    if (!zoneImageSize) return;
    const rect = evt.currentTarget.getBoundingClientRect();
    const x = (evt.clientX - rect.left) / rect.width;
    const y = (evt.clientY - rect.top) / rect.height;
    setZonePoints((prev) => [...prev, { x, y }]);
  };

  const handleZoneMove = (evt: React.MouseEvent<HTMLDivElement>) => {
    if (dragIndex === null || !zoneImageSize) return;
    const rect = evt.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (evt.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (evt.clientY - rect.top) / rect.height));
    setZonePoints((prev) => prev.map((p, idx) => (idx === dragIndex ? { x, y } : p)));
  };

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setActionError(null);

    if (zonePoints.length < 3) {
      setActionError('Add at least 3 points to save a zone.');
      setSaving(false);
      return;
    }
    const polygon = zonePoints.map((p) => [p.x, p.y]);

    try {
      if (formMode === 'create') {
        const created = await createZone(cameraId, {
          zone_name: zoneName,
          polygon,
          is_active: zoneActive
        });
        setZones((prev) => [created, ...prev]);
      } else if (activeZone) {
        const updated = await updateZone(cameraId, activeZone.id, {
          zone_name: zoneName,
          polygon,
          is_active: zoneActive
        });
    setZones((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      }
      setShowForm(false);
    } catch {
      setActionError('Unable to save zone.');
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(zone: Zone) {
    try {
      const updated = await updateZone(cameraId, zone.id, { is_active: !zone.is_active });
      setZones((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch {
      setActionError('Unable to update zone status.');
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setSaving(true);
    setActionError(null);
    try {
      await deleteZone(cameraId, deleteTarget.id);
      setZones((prev) => prev.filter((item) => item.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch {
      setActionError('Unable to delete zone.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Zones</div>
          <div className="text-3xl font-semibold font-display text-slate-100">
            {camera?.camera_name || 'Camera'}
          </div>
          <div className="text-sm text-slate-400">Define polygon regions for analytics and rules.</div>
        </div>
        <div className="flex items-center gap-3">
          <div className="hud-card px-4 py-2 text-xs text-slate-300">Total {zoneCount}</div>
          <button
            type="button"
            className="btn-primary rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em]"
            onClick={openCreate}
          >
            Add Zone
          </button>
          <Link
            href="/dashboard/cameras"
            className="rounded-full border border-white/15 px-4 py-2 text-xs uppercase tracking-[0.2em] text-slate-200 hover:border-white/30"
          >
            Back
          </Link>
        </div>
      </div>

      {error && <AlertBox variant="error">{error}</AlertBox>}
      {actionError && <AlertBox variant="warning">{actionError}</AlertBox>}

      {loading ? (
        <div className="hud-card p-6 text-sm text-slate-300">Loading zones…</div>
      ) : zones.length === 0 ? (
        <div className="hud-card p-6">
          <div className="text-lg font-semibold font-display">No zones yet</div>
          <div className="text-sm text-slate-400 mt-2">Create your first polygon zone.</div>
        </div>
      ) : (
        <div className="table-shell">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr>
                <th className="text-left px-6">Zone Name</th>
                <th className="text-left px-6">Active</th>
                <th className="text-left px-6">Polygon</th>
                <th className="text-right px-6">Actions</th>
              </tr>
            </thead>
            <tbody>
              {zones.map((zone) => (
                <tr key={zone.id}>
                  <td className="px-6 text-slate-100 font-medium">{zone.zone_name}</td>
                  <td className="px-6">
                    <button
                      type="button"
                      className={['hud-pill', zone.is_active ? 'sev-info' : 'sev-warning'].join(' ')}
                      onClick={() => handleToggle(zone)}
                    >
                      {zone.is_active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                  <td className="px-6 text-slate-400">{zone.polygon.length} points</td>
                  <td className="px-6">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        className="rounded-full border border-white/15 px-4 py-1.5 text-xs uppercase tracking-[0.2em] text-slate-200 hover:border-white/30"
                        onClick={() => openEdit(zone)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn-danger rounded-full px-4 py-1.5 text-xs uppercase tracking-[0.2em]"
                        onClick={() => setDeleteTarget(zone)}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 py-6 backdrop-blur-sm">
          <div className="hud-card modal-shell p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-[0.3em] text-slate-400">
                  {formMode === 'create' ? 'New Zone' : 'Edit Zone'}
                </div>
                <div className="text-xl font-semibold font-display text-slate-100 mt-2">
                  {formMode === 'create' ? 'Add zone' : 'Update zone'}
                </div>
              </div>
              <button
                type="button"
                className="rounded-full border border-white/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-300 hover:border-white/30"
                onClick={closeForm}
              >
                Close
              </button>
            </div>

            <form onSubmit={handleSubmit} className="modal-body mt-6 space-y-4">
              <div className="space-y-2">
                <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80">
                  Zone name
                </label>
                <input
                  type="text"
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                  value={zoneName}
                  onChange={(event) => setZoneName(event.target.value)}
                  required
                />
              </div>

              <div className="flex items-center gap-3 text-sm text-slate-300">
                <input
                  id="zoneActive"
                  type="checkbox"
                  checked={zoneActive}
                  onChange={(event) => setZoneActive(event.target.checked)}
                />
                <label htmlFor="zoneActive">Active</label>
              </div>

              <div className="space-y-2">
                <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80">
                  Draw polygon
                </label>
                <div className="rounded-2xl border border-white/10 bg-black/80 p-3">
                  {zoneImageUrl ? (
                    <div
                      className="relative w-full"
                      onClick={handleZoneClick}
                      onMouseMove={handleZoneMove}
                      onMouseUp={() => setDragIndex(null)}
                      onMouseLeave={() => setDragIndex(null)}
                    >
                      <AuthedLiveImage
                        requestUrl={zoneImageUrl}
                        alt="Zone reference"
                        className="w-full h-auto block rounded-xl"
                        refreshToken={zoneImageNonce}
                        onStatusChange={(ok) => setZoneImageError(!ok)}
                        onLoad={(e) => {
                          const img = e.currentTarget;
                          setZoneImageSize({ w: img.naturalWidth, h: img.naturalHeight });
                          setZoneImageError(false);
                        }}
                      />
                      {zoneImageError ? (
                        <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-400 bg-black/60">
                          No live frame yet. Refresh frame.
                        </div>
                      ) : null}
                      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
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
                    <div className="text-sm text-slate-400">Live frame not available for this camera.</div>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  <span>{zonePoints.length} points</span>
                  <button
                    type="button"
                    className="rounded-full border border-white/15 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-200 hover:border-white/30"
                    onClick={() => setZonePoints((prev) => prev.slice(0, -1))}
                  >
                    Undo
                  </button>
                  <button
                    type="button"
                    className="rounded-full border border-white/15 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-200 hover:border-white/30"
                    onClick={() => setZonePoints([])}
                  >
                    Clear
                  </button>
                  <button
                    type="button"
                    className="rounded-full border border-white/15 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-200 hover:border-white/30"
                    onClick={() => setZoneImageNonce((n) => n + 1)}
                  >
                    Refresh frame
                  </button>
                </div>
              </div>

              {actionError && <AlertBox variant="warning">{actionError}</AlertBox>}

              <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  className="rounded-full border border-white/15 px-4 py-2 text-xs uppercase tracking-[0.2em] text-slate-200 hover:border-white/30"
                  onClick={closeForm}
                  disabled={saving}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em] disabled:opacity-60"
                  disabled={saving}
                >
                  {saving ? 'Saving…' : 'Save Zone'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 py-6 backdrop-blur-sm">
          <div className="hud-card modal-shell p-6">
            <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Confirm delete</div>
            <div className="text-xl font-semibold font-display text-slate-100 mt-2">Remove zone?</div>
            <div className="text-sm text-slate-300 mt-2">
              This will permanently delete <span className="font-semibold">{deleteTarget.zone_name}</span>.
            </div>

            {actionError && <AlertBox variant="warning" className="mt-4">{actionError}</AlertBox>}

            <div className="mt-6 flex flex-wrap items-center justify-end gap-3">
              <button
                type="button"
                className="rounded-full border border-white/15 px-4 py-2 text-xs uppercase tracking-[0.2em] text-slate-200 hover:border-white/30"
                onClick={() => setDeleteTarget(null)}
                disabled={saving}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-danger rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em] disabled:opacity-60"
                onClick={confirmDelete}
                disabled={saving}
              >
                {saving ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
