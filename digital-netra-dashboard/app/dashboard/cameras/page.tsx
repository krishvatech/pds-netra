'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import { getSessionUser } from '@/lib/auth';
import type { Camera, CameraCreate } from '@/lib/types';
import { createCamera, deleteCamera, getCameras, updateCamera } from '@/lib/api';

type FormMode = 'create' | 'edit';

const EMPTY_FORM: CameraCreate = {
  camera_name: '',
  role: '',
  rtsp_url: '',
  is_active: true
};

export default function CamerasPage() {
  const router = useRouter();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>('create');
  const [formData, setFormData] = useState<CameraCreate>(EMPTY_FORM);
  const [activeCamera, setActiveCamera] = useState<Camera | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Camera | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  useEffect(() => {
    async function guard() {
      const user = await getSessionUser();
      if (!user) {
        router.replace('/auth/login');
        return;
      }
      await loadCameras();
    }
    guard();
  }, [router]);

  async function loadCameras() {
    setLoading(true);
    setError(null);
    try {
      const data = await getCameras();
      setCameras(data);
    } catch (err) {
      setError('Unable to load cameras right now.');
    } finally {
      setLoading(false);
    }
  }

  const activeCount = useMemo(() => cameras.filter((camera) => camera.is_active).length, [cameras]);

  function openCreate() {
    setFormMode('create');
    setFormData(EMPTY_FORM);
    setActiveCamera(null);
    setActionError(null);
    setShowForm(true);
  }

  function openEdit(camera: Camera) {
    setFormMode('edit');
    setFormData({
      camera_name: camera.camera_name,
      role: camera.role,
      rtsp_url: camera.rtsp_url,
      is_active: camera.is_active
    });
    setActiveCamera(camera);
    setActionError(null);
    setShowForm(true);
  }

  function closeForm() {
    if (saving) return;
    setShowForm(false);
    setActionError(null);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setActionError(null);

    try {
      if (formMode === 'create') {
        const created = await createCamera(formData);
        setCameras((prev) => [created, ...prev]);
      } else if (activeCamera) {
        const updated = await updateCamera(activeCamera.id, formData);
        setCameras((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      }
      setShowForm(false);
    } catch (err) {
      setActionError('Unable to save camera details. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(camera: Camera) {
    if (togglingId) return;
    setTogglingId(camera.id);
    setActionError(null);
    try {
      const updated = await updateCamera(camera.id, { is_active: !camera.is_active });
      setCameras((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setActionError('Unable to update camera status.');
    } finally {
      setTogglingId(null);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setSaving(true);
    setActionError(null);
    try {
      await deleteCamera(deleteTarget.id);
      setCameras((prev) => prev.filter((item) => item.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err) {
      setActionError('Unable to delete camera.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Fleet Live
          </div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Cameras
          </div>
          <div className="text-sm text-slate-300">
            Manage active feeds and camera roles across your facilities.
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="hud-card px-4 py-2 text-xs text-slate-300">
            Active {activeCount} / {cameras.length}
          </div>
          <button
            type="button"
            className="btn-primary rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em]"
            onClick={openCreate}
          >
            Add Camera
          </button>
        </div>
      </div>

      {error && <AlertBox variant="error">{error}</AlertBox>}
      {actionError && <AlertBox variant="warning">{actionError}</AlertBox>}

      {loading ? (
        <div className="hud-card p-6 text-sm text-slate-300">Loading cameras…</div>
      ) : cameras.length === 0 ? (
        <div className="hud-card p-6">
          <div className="text-lg font-semibold font-display">No cameras yet</div>
          <div className="text-sm text-slate-400 mt-2">
            Add your first RTSP feed to start monitoring.
          </div>
          <button
            type="button"
            className="btn-primary mt-4 rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em]"
            onClick={openCreate}
          >
            Add Camera
          </button>
        </div>
      ) : (
        <div className="table-shell">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr>
                <th className="text-left px-6">Name</th>
                <th className="text-left px-6">Role</th>
                <th className="text-left px-6">RTSP URL</th>
                <th className="text-left px-6">Status</th>
                <th className="text-right px-6">Actions</th>
              </tr>
            </thead>
            <tbody>
              {cameras.map((camera) => (
                <tr key={camera.id}>
                  <td className="px-6 font-medium text-slate-100">{camera.camera_name}</td>
                  <td className="px-6 text-slate-300">{camera.role}</td>
                  <td className="px-6 text-slate-400">
                    <div className="max-w-[320px] truncate">{camera.rtsp_url}</div>
                  </td>
                  <td className="px-6">
                    <button
                      type="button"
                      onClick={() => handleToggle(camera)}
                      className={[
                        'hud-pill',
                        camera.is_active ? 'sev-info' : 'sev-warning',
                        togglingId === camera.id ? 'opacity-60 cursor-wait' : 'cursor-pointer'
                      ].join(' ')}
                      disabled={togglingId === camera.id}
                    >
                      {camera.is_active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                  <td className="px-6">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        className="rounded-full border border-white/15 px-4 py-1.5 text-xs uppercase tracking-[0.2em] text-slate-200 hover:border-white/30"
                        onClick={() => openEdit(camera)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn-danger rounded-full px-4 py-1.5 text-xs uppercase tracking-[0.2em]"
                        onClick={() => setDeleteTarget(camera)}
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
                  {formMode === 'create' ? 'New Camera' : 'Edit Camera'}
                </div>
                <div className="text-xl font-semibold font-display text-slate-100 mt-2">
                  {formMode === 'create' ? 'Add camera' : 'Update camera'}
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
                  Camera name
                </label>
                <input
                  type="text"
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                  value={formData.camera_name}
                  onChange={(event) => setFormData((prev) => ({ ...prev, camera_name: event.target.value }))}
                  placeholder="Dock Entrance Cam 1"
                  required
                />
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80">
                    Role
                  </label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                    value={formData.role}
                    onChange={(event) => setFormData((prev) => ({ ...prev, role: event.target.value }))}
                    placeholder="Loading bay"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80">
                    Status
                  </label>
                  <button
                    type="button"
                    className={[
                      'hud-pill',
                      formData.is_active ? 'sev-info' : 'sev-warning',
                      'px-4 py-2 text-xs uppercase tracking-[0.2em]'
                    ].join(' ')}
                    onClick={() => setFormData((prev) => ({ ...prev, is_active: !prev.is_active }))}
                  >
                    {formData.is_active ? 'Active' : 'Inactive'}
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80">
                  RTSP URL
                </label>
                <input
                  type="text"
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                  value={formData.rtsp_url}
                  onChange={(event) => setFormData((prev) => ({ ...prev, rtsp_url: event.target.value }))}
                  placeholder="rtsp://user:pass@192.168.1.10:554/stream"
                  required
                />
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
                  {saving ? 'Saving…' : 'Save Camera'}
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
            <div className="text-xl font-semibold font-display text-slate-100 mt-2">Remove camera?</div>
            <div className="text-sm text-slate-300 mt-2">
              This will permanently delete <span className="font-semibold">{deleteTarget.camera_name}</span>.
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
