'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import { getSessionUser } from '@/lib/auth';
import type { Camera, CameraCreate, EdgeDevice, User } from '@/lib/types';
import { approveCamera, createCamera, deleteCamera, getCameras, getEdgeDevices, updateCamera, verifyPassword } from '@/lib/api';

type FormMode = 'create' | 'edit';
type RevealTarget = { type: 'camera'; id: string } | { type: 'form' };

function maskRtspUrl(url: string) {
  if (!url) return url;
  const match = url.match(/^(rtsps?:\/\/)([^@]+)@(.+)$/i);
  if (!match) return url;
  const maskedCredentials = match[2].includes(':') ? '***:***' : '***';
  return `${match[1]}${maskedCredentials}@${match[3]}`;
}

function EyeIcon({ revealed }: { revealed: boolean }) {
  if (revealed) {
    return (
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M1 1l22 22" />
        <path d="M6.6 6.6C3.7 8.5 2 12 2 12s4 7 10 7c2 0 3.8-.6 5.2-1.5" />
        <path d="M9.9 9.9A3 3 0 0 0 12 15a3 3 0 0 0 2.1-.9" />
        <path d="M9.3 4.2A10.5 10.5 0 0 1 12 5c6 0 10 7 10 7s-1.2 2.1-3.3 3.9" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function formatOwnerName(camera: Camera) {
  const full = `${camera.owner_first_name ?? ''} ${camera.owner_last_name ?? ''}`.trim();
  return full || 'Unknown';
}

function formatApprovalStatus(camera: Camera) {
  return camera.approval_status === 'approved' ? 'Approved' : 'Pending approval';
}

const EMPTY_FORM: CameraCreate = {
  camera_name: '',
  role: '',
  rtsp_url: '',
  is_active: true
};

export default function CamerasPage() {
  const router = useRouter();
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [user, setUser] = useState<User | null>(null);
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
  const [revealedCameraIds, setRevealedCameraIds] = useState<Record<string, boolean>>({});
  const [isFormRtspRevealed, setIsFormRtspRevealed] = useState(true);
  const [revealTarget, setRevealTarget] = useState<RevealTarget | null>(null);
  const [revealPassword, setRevealPassword] = useState('');
  const [revealError, setRevealError] = useState<string | null>(null);
  const [revealLoading, setRevealLoading] = useState(false);
  const [approvalTarget, setApprovalTarget] = useState<Camera | null>(null);
  const [approvalEdges, setApprovalEdges] = useState<EdgeDevice[]>([]);
  const [approvalEdgeId, setApprovalEdgeId] = useState<string>('');
  const [approvalLoading, setApprovalLoading] = useState(false);
  const [approvalSaving, setApprovalSaving] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);

  useEffect(() => {
    async function guard() {
      const sessionUser = await getSessionUser();
      if (!sessionUser) {
        router.replace('/auth/login');
        return;
      }
      setUser(sessionUser);
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
  const canManage = Boolean(user && !user.is_admin);
  const canReveal = canManage;
  const showOwner = Boolean(user?.is_admin);
  const canApprove = Boolean(user?.is_admin);

  function openCreate() {
    if (!canManage) return;
    setFormMode('create');
    setFormData(EMPTY_FORM);
    setActiveCamera(null);
    setActionError(null);
    setIsFormRtspRevealed(true);
    setShowForm(true);
  }

  function openEdit(camera: Camera) {
    if (!canManage) return;
    setFormMode('edit');
    setFormData({
      camera_name: camera.camera_name,
      role: camera.role,
      rtsp_url: camera.rtsp_url,
      is_active: camera.is_active
    });
    setActiveCamera(camera);
    setActionError(null);
    setIsFormRtspRevealed(false);
    setShowForm(true);
  }

  function closeForm() {
    if (saving) return;
    setShowForm(false);
    setActionError(null);
    setIsFormRtspRevealed(true);
  }

  function requestReveal(target: RevealTarget) {
    if (!canManage) return;
    setRevealTarget(target);
    setRevealPassword('');
    setRevealError(null);
  }

  function hideCameraRtsp(cameraId: string) {
    setRevealedCameraIds((prev) => {
      const next = { ...prev };
      delete next[cameraId];
      return next;
    });
  }

  function hideFormRtsp() {
    setIsFormRtspRevealed(false);
  }

  async function handleRevealSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (revealLoading) return;
    setRevealLoading(true);
    setRevealError(null);
    try {
      const result = await verifyPassword({ password: revealPassword });
      if (!result.valid) {
        setRevealError('Incorrect password. Please try again.');
        return;
      }
      if (revealTarget?.type === 'camera') {
        setRevealedCameraIds((prev) => ({ ...prev, [revealTarget.id]: true }));
      } else if (revealTarget?.type === 'form') {
        setIsFormRtspRevealed(true);
      }
      setRevealTarget(null);
      setRevealPassword('');
      setRevealError(null);
    } catch (err) {
      setRevealError('Unable to verify password. Please try again.');
    } finally {
      setRevealLoading(false);
    }
  }

  async function openApprove(camera: Camera) {
    if (!canApprove) return;
    setApprovalTarget(camera);
    setApprovalEdges([]);
    setApprovalEdgeId('');
    setApprovalError(null);
    setApprovalLoading(true);
    try {
      const edges = await getEdgeDevices(camera.user_id);
      setApprovalEdges(edges);
      if (edges.length === 1) {
        setApprovalEdgeId(edges[0].id);
      }
    } catch (err) {
      setApprovalError('Unable to load edge devices for this user.');
    } finally {
      setApprovalLoading(false);
    }
  }

  function closeApprove() {
    setApprovalTarget(null);
    setApprovalEdges([]);
    setApprovalEdgeId('');
    setApprovalError(null);
  }

  async function submitApprove(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!approvalTarget || !approvalEdgeId) return;
    setApprovalSaving(true);
    setApprovalError(null);
    try {
      const updated = await approveCamera(approvalTarget.id, approvalEdgeId);
      setCameras((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      closeApprove();
    } catch (err) {
      setApprovalError('Unable to approve camera. Please try again.');
    } finally {
      setApprovalSaving(false);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManage) return;
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
    if (!canManage) return;
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
    if (!canManage) return;
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
          <div className="text-3xl sm:text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Cameras
          </div>
          <div className="text-sm text-slate-300">
            Manage active feeds and camera roles across your facilities.
          </div>
        </div>
        <div className="flex w-full flex-wrap items-center gap-3 lg:w-auto">
          <div className="hud-card w-full px-4 py-2 text-center text-xs text-slate-300 sm:w-auto">
            Active {activeCount} / {cameras.length}
          </div>
          {canManage && (
            <button
              type="button"
              className="btn-primary w-full rounded-full px-5 py-2 text-center text-xs font-semibold uppercase tracking-[0.25em] sm:w-auto"
              onClick={openCreate}
            >
              Add Camera
            </button>
          )}
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
          {canManage && (
            <button
              type="button"
              className="btn-primary mt-4 rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em]"
              onClick={openCreate}
            >
              Add Camera
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="grid gap-3 md:hidden">
            {cameras.map((camera) => (
              <div key={camera.id} className="hud-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.3em] text-slate-500">Camera</div>
                    <div className="text-lg font-semibold text-slate-100">{camera.camera_name}</div>
                    <div className="text-xs text-slate-400 mt-1">{camera.role}</div>
                    {showOwner && (
                      <div className="text-xs text-slate-400 mt-1">
                        User: <span className="text-slate-200">{formatOwnerName(camera)}</span>
                      </div>
                    )}
                    <div className="mt-2">
                      <span
                        className={[
                          'hud-pill',
                          camera.approval_status === 'approved' ? 'sev-info' : 'sev-warning'
                        ].join(' ')}
                      >
                        {formatApprovalStatus(camera)}
                      </span>
                    </div>
                  </div>
                  {canManage && (
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        aria-label="Edit camera"
                        className="flex h-8 w-8 items-center justify-center rounded-full border border-white/15 text-slate-200 hover:border-white/30 hover:text-white"
                        onClick={() => openEdit(camera)}
                      >
                        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M12 20h9" />
                          <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        aria-label="Delete camera"
                        className="flex h-8 w-8 items-center justify-center rounded-full border border-red-400/30 text-red-300 hover:border-red-400/60 hover:text-red-200"
                        onClick={() => setDeleteTarget(camera)}
                      >
                        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M3 6h18" />
                          <path d="M8 6V4h8v2" />
                          <path d="M10 11v6M14 11v6" />
                          <path d="M6 6l1 14h10l1-14" />
                        </svg>
                      </button>
                    </div>
                  )}
                </div>
                <div className="mt-2 flex items-center gap-2 text-xs text-slate-400">
                  <div className="break-all">
                    {canReveal && revealedCameraIds[camera.id]
                      ? camera.rtsp_url
                      : maskRtspUrl(camera.rtsp_url)}
                  </div>
                  {canReveal && (
                    <button
                      type="button"
                      aria-label={revealedCameraIds[camera.id] ? 'Hide RTSP URL' : 'Reveal RTSP URL'}
                      className="flex h-7 w-7 items-center justify-center rounded-full border border-white/15 text-slate-200 hover:border-white/30 hover:text-white"
                      onClick={() =>
                        revealedCameraIds[camera.id]
                          ? hideCameraRtsp(camera.id)
                          : requestReveal({ type: 'camera', id: camera.id })
                      }
                    >
                      <EyeIcon revealed={revealedCameraIds[camera.id]} />
                    </button>
                  )}
                </div>
                <div className="mt-3">
                  {!canManage ? (
                    <span
                      className={['hud-pill', camera.is_active ? 'sev-info' : 'sev-warning'].join(' ')}
                    >
                      {camera.is_active ? 'Active' : 'Inactive'}
                    </span>
                  ) : (
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
                  )}
                </div>
                {canApprove && camera.approval_status !== 'approved' && (
                  <div className="mt-3">
                    <button
                      type="button"
                      className="btn-primary w-full rounded-full px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.3em]"
                      onClick={() => openApprove(camera)}
                    >
                      Approve & Assign Edge
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="hidden md:block table-shell table-shell-no-scroll">
            <table className="w-full table-fixed text-sm">
              <thead>
                <tr>
                  <th className="text-left px-6 w-[16%]">Name</th>
                  {showOwner && <th className="text-left px-6 w-[16%]">User</th>}
                  <th className={['text-left px-6', showOwner ? 'w-[12%]' : 'w-[14%]'].join(' ')}>Role</th>
                  <th className={['text-left px-6', showOwner ? 'w-[28%]' : 'w-[34%]'].join(' ')}>RTSP URL</th>
                  <th className={['text-left px-6', showOwner ? 'w-[14%]' : 'w-[12%]'].join(' ')}>Approval</th>
                  <th className={['text-left px-6', showOwner ? 'w-[10%]' : 'w-[10%]'].join(' ')}>Status</th>
                  {(canManage || canApprove) && <th className="text-right px-6 w-[12%]">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {cameras.map((camera) => (
                  <tr key={camera.id}>
                    <td className="px-6 font-medium text-slate-100 w-[16%]">{camera.camera_name}</td>
                    {showOwner && (
                      <td className="px-6 text-slate-300 w-[16%]">
                        {formatOwnerName(camera)}
                      </td>
                    )}
                    <td className={['px-6 text-slate-300', showOwner ? 'w-[12%]' : 'w-[14%]'].join(' ')}>{camera.role}</td>
                    <td className={['px-6 text-slate-400', showOwner ? 'w-[28%]' : 'w-[34%]'].join(' ')}>
                      <div className="flex items-center gap-2">
                        <div className="w-full truncate">
                          {canReveal && revealedCameraIds[camera.id]
                            ? camera.rtsp_url
                            : maskRtspUrl(camera.rtsp_url)}
                        </div>
                        {canReveal && (
                          <button
                            type="button"
                            aria-label={revealedCameraIds[camera.id] ? 'Hide RTSP URL' : 'Reveal RTSP URL'}
                            className="flex h-7 w-7 items-center justify-center rounded-full border border-white/15 text-slate-200 hover:border-white/30 hover:text-white"
                            onClick={() =>
                              revealedCameraIds[camera.id]
                                ? hideCameraRtsp(camera.id)
                                : requestReveal({ type: 'camera', id: camera.id })
                            }
                          >
                            <EyeIcon revealed={revealedCameraIds[camera.id]} />
                          </button>
                        )}
                      </div>
                    </td>
                    <td className={['px-6', showOwner ? 'w-[14%]' : 'w-[12%]'].join(' ')}>
                      <span
                        className={[
                          'hud-pill w-full justify-center',
                          camera.approval_status === 'approved' ? 'sev-info' : 'sev-warning'
                        ].join(' ')}
                      >
                        {formatApprovalStatus(camera)}
                      </span>
                    </td>
                    <td className={['px-6', showOwner ? 'w-[10%]' : 'w-[10%]'].join(' ')}>
                      <span
                        className={[
                          'hud-pill w-full justify-center',
                          camera.is_active ? 'sev-info' : 'sev-warning'
                        ].join(' ')}
                        title="Edit camera to change status"
                      >
                        {camera.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    {(canManage || canApprove) && (
                      <td className="px-6">
                        <div className="flex items-center justify-end gap-2">
                          {canManage && (
                            <>
                              <button
                                type="button"
                                aria-label="Edit camera"
                                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/15 text-slate-200 hover:border-white/30 hover:text-white"
                                onClick={() => openEdit(camera)}
                              >
                                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M12 20h9" />
                                  <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
                                </svg>
                              </button>
                              <button
                                type="button"
                                aria-label="Delete camera"
                                className="flex h-8 w-8 items-center justify-center rounded-full border border-red-400/30 text-red-300 hover:border-red-400/60 hover:text-red-200"
                                onClick={() => setDeleteTarget(camera)}
                              >
                                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M3 6h18" />
                                  <path d="M8 6V4h8v2" />
                                  <path d="M10 11v6M14 11v6" />
                                  <path d="M6 6l1 14h10l1-14" />
                                </svg>
                              </button>
                            </>
                          )}
                          {canApprove && camera.approval_status !== 'approved' && (
                            <button
                              type="button"
                              className="btn-primary rounded-full px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.3em]"
                              onClick={() => openApprove(camera)}
                            >
                              Approve
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
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
                aria-label="Close"
                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 text-slate-300 hover:border-white/30 hover:text-slate-100"
                onClick={closeForm}
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
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
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className={[
                      'px-4 py-2 text-xs uppercase tracking-[0.2em] rounded-full border transition',
                      formData.is_active
                        ? 'border-sky-300/60 bg-sky-300/10 text-sky-200'
                        : 'border-white/10 bg-white/5 text-slate-300 hover:border-white/30'
                    ].join(' ')}
                    onClick={() => setFormData((prev) => ({ ...prev, is_active: true }))}
                    aria-pressed={formData.is_active}
                  >
                    Active
                  </button>
                  <button
                    type="button"
                    className={[
                      'px-4 py-2 text-xs uppercase tracking-[0.2em] rounded-full border transition',
                      !formData.is_active
                        ? 'border-amber-300/60 bg-amber-300/10 text-amber-200'
                        : 'border-white/10 bg-white/5 text-slate-300 hover:border-white/30'
                    ].join(' ')}
                    onClick={() => setFormData((prev) => ({ ...prev, is_active: false }))}
                    aria-pressed={!formData.is_active}
                  >
                    Inactive
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80">
                  RTSP URL
                </label>
                <div className="relative">
                  <input
                    type="text"
                    className={[
                      'w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 pr-12 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20',
                      formMode === 'edit' && !isFormRtspRevealed ? 'cursor-not-allowed text-slate-400' : ''
                    ].join(' ')}
                    value={
                      formMode === 'edit' && !isFormRtspRevealed
                        ? maskRtspUrl(formData.rtsp_url)
                        : formData.rtsp_url
                    }
                    onChange={(event) => setFormData((prev) => ({ ...prev, rtsp_url: event.target.value }))}
                    placeholder="rtsp://user:pass@192.168.1.10:554/stream"
                    readOnly={formMode === 'edit' && !isFormRtspRevealed}
                    required
                  />
                  {formMode === 'edit' && (
                    <button
                      type="button"
                      aria-label={isFormRtspRevealed ? 'Hide RTSP URL' : 'Reveal RTSP URL'}
                      className="absolute right-3 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full border border-white/15 text-slate-200 hover:border-white/30 hover:text-white"
                      onClick={() =>
                        isFormRtspRevealed ? hideFormRtsp() : requestReveal({ type: 'form' })
                      }
                    >
                      <EyeIcon revealed={isFormRtspRevealed} />
                    </button>
                  )}
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

      {approvalTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 py-6 backdrop-blur-sm">
          <div className="hud-card modal-shell p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Camera approval</div>
                <div className="text-xl font-semibold font-display text-slate-100 mt-2">
                  Assign edge device
                </div>
                <div className="text-sm text-slate-300 mt-2">
                  Select an edge device for <span className="font-semibold">{approvalTarget.camera_name}</span>.
                </div>
              </div>
              <button
                type="button"
                aria-label="Close"
                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 text-slate-300 hover:border-white/30 hover:text-slate-100"
                onClick={closeApprove}
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={submitApprove} className="mt-6 space-y-4">
              {approvalLoading ? (
                <div className="text-sm text-slate-300">Loading available edge devices…</div>
              ) : (
                <div className="space-y-2">
                  <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80">
                    Edge device
                  </label>
                  <select
                    className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                    value={approvalEdgeId}
                    onChange={(event) => setApprovalEdgeId(event.target.value)}
                    disabled={approvalEdges.length === 0}
                    required
                  >
                    <option value="" disabled>
                      {approvalEdges.length === 0 ? 'No edge devices found' : 'Select edge device'}
                    </option>
                    {approvalEdges.map((edge) => (
                      <option key={edge.id} value={edge.id}>
                        {edge.name} · {edge.ip}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {approvalError && <AlertBox variant="warning">{approvalError}</AlertBox>}

              <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  className="rounded-full border border-white/15 px-4 py-2 text-xs uppercase tracking-[0.2em] text-slate-200 hover:border-white/30"
                  onClick={closeApprove}
                  disabled={approvalSaving}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em] disabled:opacity-60"
                  disabled={approvalSaving || approvalLoading || approvalEdges.length === 0 || !approvalEdgeId}
                >
                  {approvalSaving ? 'Approving…' : 'Approve camera'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {revealTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 py-6 backdrop-blur-sm">
          <div className="hud-card modal-shell p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Security check</div>
                <div className="text-xl font-semibold font-display text-slate-100 mt-2">Reveal RTSP URL</div>
              </div>
              <button
                type="button"
                aria-label="Close"
                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 text-slate-300 hover:border-white/30 hover:text-slate-100"
                onClick={() => setRevealTarget(null)}
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleRevealSubmit} className="mt-6 space-y-4">
              <div className="space-y-2">
                <label className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-300/80">
                  Password
                </label>
                <input
                  type="password"
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                  value={revealPassword}
                  onChange={(event) => setRevealPassword(event.target.value)}
                  placeholder="Enter reveal password"
                  required
                />
              </div>

              {revealError && <AlertBox variant="warning">{revealError}</AlertBox>}

              <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  className="rounded-full border border-white/15 px-4 py-2 text-xs uppercase tracking-[0.2em] text-slate-200 hover:border-white/30"
                  onClick={() => setRevealTarget(null)}
                  disabled={revealLoading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em] disabled:opacity-60"
                  disabled={revealLoading}
                >
                  {revealLoading ? 'Checking…' : 'Reveal'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
