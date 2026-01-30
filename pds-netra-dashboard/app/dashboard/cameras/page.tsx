'use client';

import { useEffect, useMemo, useState } from 'react';
import type { CameraInfo, CameraModules, GodownListItem } from '@/lib/types';
import { createCamera, deleteCamera, getCameras, getGodowns, updateCamera } from '@/lib/api';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { ErrorBanner } from '@/components/ui/error-banner';
import { ToastStack, type ToastItem } from '@/components/ui/toast';
import { ConfirmDialog } from '@/components/ui/dialog';

const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

const mockCameras: CameraInfo[] = [
  {
    camera_id: 'CAM_GATE_1',
    label: 'Gate ANPR',
    role: 'GATE_ANPR',
    rtsp_url: 'rtsp://example/gate',
    is_active: true,
    modules: {
      anpr_enabled: true,
      gate_entry_exit_enabled: true,
      person_after_hours_enabled: false,
      animal_detection_enabled: false,
      fire_detection_enabled: false,
      health_monitoring_enabled: true
    }
  },
  {
    camera_id: 'CAM_AISLE_3',
    label: 'Aisle 3',
    role: 'SECURITY',
    rtsp_url: 'rtsp://example/aisle',
    is_active: true,
    modules: {
      anpr_enabled: false,
      gate_entry_exit_enabled: false,
      person_after_hours_enabled: true,
      animal_detection_enabled: true,
      fire_detection_enabled: false,
      health_monitoring_enabled: true
    }
  }
];

const moduleLabels: Array<{ key: keyof CameraModules; label: string }> = [
  { key: 'anpr_enabled', label: 'ANPR' },
  { key: 'gate_entry_exit_enabled', label: 'Gate Entry/Exit' },
  { key: 'person_after_hours_enabled', label: 'After-hours' },
  { key: 'animal_detection_enabled', label: 'Animals' },
  { key: 'fire_detection_enabled', label: 'Fire' },
  { key: 'health_monitoring_enabled', label: 'Health' }
];

function defaultModulesForRole(role?: string | null): CameraModules {
  const normalized = (role ?? '').toUpperCase();
  if (normalized === 'GATE_ANPR') {
    return {
      anpr_enabled: true,
      gate_entry_exit_enabled: true,
      person_after_hours_enabled: false,
      animal_detection_enabled: false,
      fire_detection_enabled: false,
      health_monitoring_enabled: true
    };
  }
  if (normalized === 'HEALTH_ONLY') {
    return {
      anpr_enabled: false,
      gate_entry_exit_enabled: false,
      person_after_hours_enabled: false,
      animal_detection_enabled: false,
      fire_detection_enabled: false,
      health_monitoring_enabled: true
    };
  }
  return {
    anpr_enabled: false,
    gate_entry_exit_enabled: false,
    person_after_hours_enabled: true,
    animal_detection_enabled: true,
    fire_detection_enabled: true,
    health_monitoring_enabled: true
  };
}

function formatRole(role?: string | null): string {
  if (!role) return 'SECURITY';
  return role.replaceAll('_', ' ');
}

function makeCameraKey(cameraId: string, godownId?: string | null) {
  return `${cameraId}__${godownId ?? ''}`;
}

export default function CamerasPage() {
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [filterGodown, setFilterGodown] = useState('');
  const [filterRole, setFilterRole] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [query, setQuery] = useState('');
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const [showForm, setShowForm] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [form, setForm] = useState<{
    camera_id: string;
    godown_id: string;
    label: string;
    role: string;
    rtsp_url: string;
    is_active: boolean;
    modules: CameraModules;
  }>(() => ({
    camera_id: '',
    godown_id: '',
    label: '',
    role: 'SECURITY',
    rtsp_url: '',
    is_active: true,
    modules: defaultModulesForRole('SECURITY')
  }));

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<{ camera_id: string; godown_id?: string | null } | null>(null);

  const roleOptions = useMemo(
    () => [
      { label: 'All roles', value: '' },
      { label: 'GATE_ANPR', value: 'GATE_ANPR' },
      { label: 'SECURITY', value: 'SECURITY' },
      { label: 'HEALTH_ONLY', value: 'HEALTH_ONLY' }
    ],
    []
  );

  const statusOptions = useMemo(
    () => [
      { label: 'All', value: '' },
      { label: 'Active', value: 'active' },
      { label: 'Inactive', value: 'inactive' }
    ],
    []
  );

  function pushToast(toast: Omit<ToastItem, 'id'>) {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((items) => [...items, { id, ...toast }]);
  }

  const apiFilters = useMemo(() => {
    const p: Record<string, string | boolean> = {};
    if (filterGodown.trim()) p.godown_id = filterGodown.trim();
    if (filterRole) p.role = filterRole;
    if (filterStatus) p.is_active = filterStatus === 'active';
    return p;
  }, [filterGodown, filterRole, filterStatus]);

  async function loadCameras(options?: { showToast?: boolean }) {
    setError(null);
    setLoading(true);
    try {
      if (MOCK_MODE) {
        setCameras(mockCameras);
        if (options?.showToast) {
          pushToast({ type: 'info', title: 'Mock refreshed', message: `Loaded ${mockCameras.length} cameras` });
        }
        return;
      }
      const rows = await getCameras(apiFilters);
      setCameras(rows ?? []);
      if (options?.showToast) {
        pushToast({ type: 'info', title: 'Cameras refreshed', message: `Loaded ${rows?.length ?? 0} cameras` });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load cameras');
    } finally {
      setLoading(false);
    }
  }

  async function loadGodowns() {
    try {
      const data = await getGodowns();
      setGodowns(Array.isArray(data) ? data : data.items);
    } catch {
      setGodowns([]);
    }
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!mounted) return;
      await loadGodowns();
      await loadCameras();
    })();
    return () => {
      mounted = false;
    };
  }, [apiFilters]);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return cameras;
    return cameras.filter((camera) => {
      const label = `${camera.camera_id} ${camera.label ?? ''}`.toLowerCase();
      return label.includes(term);
    });
  }, [cameras, query]);

  const godownOptions = useMemo(() => {
    const opts = [{ label: 'Select godown', value: '' }];
    for (const g of godowns) {
      opts.push({ label: `${g.name ?? g.godown_id} (${g.godown_id})`, value: String(g.godown_id) });
    }
    return opts;
  }, [godowns]);

  function resetForm(next?: Partial<typeof form>) {
    setForm({
      camera_id: '',
      godown_id: filterGodown.trim() || '',
      label: '',
      role: 'SECURITY',
      rtsp_url: '',
      is_active: true,
      modules: defaultModulesForRole('SECURITY'),
      ...(next ?? {})
    });
    setFormError(null);
    setFormSuccess(null);
  }

  function startAdd() {
    setEditingKey(null);
    resetForm();
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function startEdit(cam: CameraInfo) {
    setEditingKey(makeCameraKey(cam.camera_id, cam.godown_id));
    resetForm({
      camera_id: cam.camera_id,
      godown_id: String(cam.godown_id ?? ''),
      label: String(cam.label ?? ''),
      role: String(cam.role ?? 'SECURITY'),
      rtsp_url: String(cam.rtsp_url ?? ''),
      is_active: Boolean(cam.is_active ?? true),
      modules: (cam.modules ?? defaultModulesForRole(cam.role)) as CameraModules
    });
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function requestDelete(cam: CameraInfo) {
    setPendingDelete({ camera_id: cam.camera_id, godown_id: cam.godown_id });
    setConfirmOpen(true);
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setFormLoading(true);
    setFormError(null);
    try {
      if (MOCK_MODE) {
        setCameras((items) =>
          items.filter(
            (c) =>
              makeCameraKey(c.camera_id, c.godown_id) !== makeCameraKey(pendingDelete.camera_id, pendingDelete.godown_id)
          )
        );
        pushToast({ type: 'info', title: 'Mock delete', message: `Deleted ${pendingDelete.camera_id}` });
      } else {
        await deleteCamera(pendingDelete.camera_id, pendingDelete.godown_id ?? undefined);
        pushToast({ type: 'success', title: 'Camera deleted', message: `${pendingDelete.camera_id} removed` });
        await loadCameras();
      }
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Failed to delete camera');
    } finally {
      setFormLoading(false);
      setConfirmOpen(false);
      setPendingDelete(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const cameraId = form.camera_id.trim();
    const godownId = form.godown_id.trim();
    const rtsp = form.rtsp_url.trim();

    if (!cameraId) return setFormError('Camera ID is required.');
    if (!godownId) return setFormError('Godown is required.');
    if (!rtsp) return setFormError('RTSP URL is required.');

    setFormLoading(true);
    setFormError(null);
    setFormSuccess(null);

    try {
      const payloadBase = {
        label: form.label.trim() || undefined,
        role: form.role.trim() || undefined,
        rtsp_url: rtsp,
        is_active: form.is_active,
        modules: form.modules
      };

      if (MOCK_MODE) {
        if (editingKey) {
          setCameras((items) =>
            items.map((c) =>
              makeCameraKey(c.camera_id, c.godown_id) === editingKey
                ? { ...c, ...payloadBase, camera_id: cameraId, godown_id: godownId }
                : c
            )
          );
          setFormSuccess('Mock updated.');
          pushToast({ type: 'info', title: 'Mock update', message: `Updated ${cameraId}` });
        } else {
          setCameras((items) => [
            ...items,
            {
              camera_id: cameraId,
              godown_id: godownId,
              ...payloadBase
            }
          ]);
          setFormSuccess('Mock created.');
          pushToast({ type: 'info', title: 'Mock create', message: `Created ${cameraId}` });
        }
      } else {
        if (editingKey) {
          await updateCamera(cameraId, payloadBase, godownId);
          setFormSuccess('Camera updated successfully.');
          pushToast({ type: 'success', title: 'Camera updated', message: `${cameraId} saved` });
        } else {
          await createCamera({
            camera_id: cameraId,
            godown_id: godownId,
            ...payloadBase
          });
          setFormSuccess('Camera created successfully.');
          pushToast({ type: 'success', title: 'Camera created', message: `${cameraId} added` });
        }
        await loadCameras();
      }

      setTimeout(() => setFormSuccess(null), 2500);
      setShowForm(false);
      setEditingKey(null);
      resetForm();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Failed to save camera');
    } finally {
      setFormLoading(false);
    }
  }

  const moduleToggleList = useMemo(() => moduleLabels, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Configuration
          </div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">Cameras</div>
          <div className="text-sm text-slate-300">Add, edit, and delete camera RTSP + module routing.</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => loadCameras({ showToast: true })}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-md transition-colors text-sm font-medium"
            disabled={loading}
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
          <button
            onClick={() => {
              if (showForm) {
                setShowForm(false);
                setEditingKey(null);
                resetForm();
              } else {
                startAdd();
              }
            }}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors text-sm font-medium"
          >
            {showForm ? 'Cancel' : 'Add Camera'}
          </button>
        </div>
      </div>

      {showForm && (
        <Card className="animate-fade-up hud-card border-blue-500/30">
          <CardHeader>
            <div className="text-lg font-semibold font-display">
              {editingKey ? `Edit Camera: ${form.camera_id}` : 'Add New Camera'}
            </div>
            <div className="text-sm text-slate-300">
              {editingKey ? 'Update camera routing and RTSP.' : 'Register a new camera under a godown.'}
            </div>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="space-y-1">
                  <label className="text-xs text-slate-400">Camera ID (Required)</label>
                  <input
                    type="text"
                    required
                    disabled={!!editingKey}
                    placeholder="e.g. CAM_GATE_1"
                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
                    value={form.camera_id}
                    onChange={(e) => setForm((s) => ({ ...s, camera_id: e.target.value }))}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-slate-400">Godown (Required)</label>
                  {godownOptions.length > 1 ? (
                    <Select
                      value={form.godown_id}
                      onChange={(e) => setForm((s) => ({ ...s, godown_id: e.target.value }))}
                      options={godownOptions}
                    />
                  ) : (
                    <input
                      type="text"
                      required
                      disabled={!!editingKey}
                      placeholder="e.g. GDN_001"
                      className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
                      value={form.godown_id}
                      onChange={(e) => setForm((s) => ({ ...s, godown_id: e.target.value }))}
                    />
                  )}
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-slate-400">Label</label>
                  <input
                    type="text"
                    placeholder="e.g. Gate ANPR"
                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                    value={form.label}
                    onChange={(e) => setForm((s) => ({ ...s, label: e.target.value }))}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-slate-400">Role</label>
                  <Select
                    value={form.role}
                    onChange={(e) => {
                      const nextRole = e.target.value;
                      setForm((s) => ({
                        ...s,
                        role: nextRole,
                        modules: s.modules && Object.keys(s.modules).length ? s.modules : defaultModulesForRole(nextRole)
                      }));
                    }}
                    options={roleOptions.filter((r) => r.value !== '')}
                  />
                </div>

                <div className="space-y-1 md:col-span-2 lg:col-span-3">
                  <label className="text-xs text-slate-400">RTSP URL (Required)</label>
                  <input
                    type="text"
                    required
                    placeholder="rtsp://user:pass@ip/stream"
                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                    value={form.rtsp_url}
                    onChange={(e) => setForm((s) => ({ ...s, rtsp_url: e.target.value }))}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-slate-400">Status</label>
                  <select
                    className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                    value={form.is_active ? 'true' : 'false'}
                    onChange={(e) => setForm((s) => ({ ...s, is_active: e.target.value === 'true' }))}
                  >
                    <option value="true">Active</option>
                    <option value="false">Inactive</option>
                  </select>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-medium text-slate-200">Modules</div>
                    <div className="text-xs text-slate-400">Toggle what detections this camera should run.</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setForm((s) => ({ ...s, modules: defaultModulesForRole(s.role) }))}
                    className="text-xs text-blue-300 hover:text-blue-200"
                  >
                    Use role defaults
                  </button>
                </div>

                <div className="mt-3 grid grid-cols-2 md:grid-cols-3 gap-3">
                  {moduleToggleList.map((m) => (
                    <label key={m.key} className="flex items-center gap-2 text-sm text-slate-200">
                      <input
                        type="checkbox"
                        checked={Boolean(form.modules?.[m.key])}
                        onChange={(e) =>
                          setForm((s) => ({
                            ...s,
                            modules: { ...(s.modules ?? {}), [m.key]: e.target.checked }
                          }))
                        }
                      />
                      <span className="text-slate-300">{m.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {formError && <ErrorBanner message={formError} />}
              {formSuccess && (
                <div className="text-sm text-green-400 bg-green-400/10 border border-green-400/20 rounded px-3 py-2">
                  {formSuccess}
                </div>
              )}

              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={formLoading}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 text-white rounded-md transition-colors text-sm font-medium"
                >
                  {formLoading ? (editingKey ? 'Updating...' : 'Creating...') : editingKey ? 'Update Camera' : 'Create Camera'}
                </button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card className="animate-fade-up hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Filters</div>
          <div className="text-sm text-slate-300">Filter cameras by godown, role, and status.</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <div className="text-xs text-slate-600 mb-1">Godown ID</div>
              <input
                className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                value={filterGodown}
                onChange={(e) => setFilterGodown(e.target.value)}
                placeholder="GDN_001"
              />
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Role</div>
              <Select value={filterRole} onChange={(e) => setFilterRole(e.target.value)} options={roleOptions} />
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Status</div>
              <Select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} options={statusOptions} />
            </div>
            <div>
              <div className="text-xs text-slate-600 mb-1">Search</div>
              <input
                className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="CAM_GATE_1"
              />
            </div>
          </div>

          {error ? (
            <div className="mt-4">
              <ErrorBanner message={error} />
            </div>
          ) : null}

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left py-3 px-2 text-slate-400 font-medium">Camera</th>
                  <th className="text-left py-3 px-2 text-slate-400 font-medium">Godown</th>
                  <th className="text-left py-3 px-2 text-slate-400 font-medium">Role</th>
                  <th className="text-left py-3 px-2 text-slate-400 font-medium">Modules</th>
                  <th className="text-left py-3 px-2 text-slate-400 font-medium">Status</th>
                  <th className="text-right py-3 px-2 text-slate-400 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {!filtered.length ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-slate-500">
                      No cameras found for the selected filters.
                    </td>
                  </tr>
                ) : (
                  filtered.map((camera) => {
                    const modules = camera.modules ?? defaultModulesForRole(camera.role);
                    const enabledModules = moduleLabels.filter((entry) => modules?.[entry.key]);
                    const derived = camera.modules == null;
                    return (
                      <tr
                        key={makeCameraKey(camera.camera_id, camera.godown_id)}
                        className="border-b border-slate-800 hover:bg-slate-800/50"
                      >
                        <td className="py-3 px-2">
                          <div className="font-semibold text-slate-100">{camera.label ?? camera.camera_id}</div>
                          <div className="text-xs text-slate-400 font-mono">{camera.camera_id}</div>
                          {camera.rtsp_url ? (
                            <div className="text-[11px] text-slate-500 mt-1 break-all">{camera.rtsp_url}</div>
                          ) : null}
                        </td>
                        <td className="py-3 px-2 text-slate-300 text-xs">{camera.godown_id ?? '—'}</td>
                        <td className="py-3 px-2">
                          <span className="px-2 py-1 bg-slate-700 rounded text-xs text-slate-200">
                            {formatRole(camera.role)}
                          </span>
                        </td>
                        <td className="py-3 px-2">
                          <div className="flex flex-wrap gap-1">
                            {enabledModules.length ? (
                              enabledModules.map((entry) => (
                                <Badge key={entry.key} variant="outline" className="border-slate-700 text-slate-200">
                                  {entry.label}
                                </Badge>
                              ))
                            ) : (
                              <span className="text-xs text-slate-600">No modules</span>
                            )}
                          </div>
                          {derived ? (
                            <div className="text-[11px] text-slate-500 mt-1">Derived from role defaults</div>
                          ) : null}
                        </td>
                        <td className="py-3 px-2">
                          {camera.is_active ? (
                            <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs">Active</span>
                          ) : (
                            <span className="px-2 py-1 bg-slate-700 text-slate-400 rounded text-xs">Inactive</span>
                          )}
                        </td>
                        <td className="py-3 px-2 text-right space-x-2">
                          <button onClick={() => startEdit(camera)} className="text-blue-400 hover:text-blue-300 text-xs">
                            Edit
                          </button>
                          <button onClick={() => requestDelete(camera)} className="text-red-400 hover:text-red-300 text-xs">
                            Delete
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <ToastStack items={toasts} onDismiss={(id) => setToasts((items) => items.filter((t) => t.id !== id))} />

      <ConfirmDialog
        open={confirmOpen}
        title={pendingDelete ? `Delete camera ${pendingDelete.camera_id}?` : 'Delete camera'}
        message={
          pendingDelete
            ? `This will remove the camera configuration for godown ${pendingDelete.godown_id ?? '—'}. This cannot be undone.`
            : undefined
        }
        confirmLabel="Delete"
        confirmVariant="danger"
        isBusy={formLoading}
        onCancel={() => {
          if (formLoading) return;
          setConfirmOpen(false);
          setPendingDelete(null);
        }}
        onConfirm={confirmDelete}
      />
    </div>
  );
}