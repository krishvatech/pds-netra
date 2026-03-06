'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import {
  approveCamera,
  createCamera,
  createEdgeDevice,
  deleteCamera,
  deleteEdgeDevice,
  getCameras,
  getEdgeDevices,
  getRuleTypes,
  getUser,
  getUserRuleTypes,
  setUserRuleTypes,
  unassignCamera,
  updateCamera,
  updateEdgeDevice,
  updateUser
} from '@/lib/api';
import { getSessionUser } from '@/lib/auth';
import type {
  AdminUserUpdate,
  Camera,
  CameraCreate,
  CameraUpdate,
  EdgeDevice,
  EdgeDeviceUpdate,
  RuleType,
  User
} from '@/lib/types';

function formatName(user: User) {
  const full = `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim();
  return full || user.email || 'Unknown';
}

function formatDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatApprovalStatus(status: string) {
  if (status === 'approved') return 'Approved';
  if (status === 'not_approved') return 'Not approved';
  return 'Pending';
}

function approvalBadgeClass(status: string) {
  if (status === 'approved') return 'sev-info';
  if (status === 'not_approved') return 'sev-critical';
  return 'sev-warning';
}

type ProfileForm = {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  is_admin: boolean;
  is_active: boolean;
  password: string;
  confirm_password: string;
};

const EMPTY_PROFILE: ProfileForm = {
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  is_admin: false,
  is_active: true,
  password: '',
  confirm_password: ''
};

type EdgeForm = {
  name: string;
  api_key: string;
  location: string;
  ip: string;
  password: string;
  is_active: boolean;
};

const EMPTY_EDGE: EdgeForm = {
  name: '',
  api_key: '',
  location: '',
  ip: '',
  password: '',
  is_active: true
};

type CameraForm = {
  camera_name: string;
  role: string;
  rtsp_url: string;
  is_active: boolean;
};

const EMPTY_CAMERA: CameraForm = {
  camera_name: '',
  role: '',
  rtsp_url: '',
  is_active: true
};

function Modal({
  open,
  title,
  onClose,
  children
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4">
      <div className="hud-card w-full max-w-2xl p-6 shadow-2xl">
        <div className="flex items-center justify-between gap-4">
          <div className="text-lg font-semibold text-slate-100">{title}</div>
          <button
            type="button"
            className="text-xs text-slate-400 hover:text-slate-200"
            onClick={onClose}
          >
            Close
          </button>
        </div>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}

function IconButton({
  label,
  onClick,
  children
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-white/5 text-slate-200 transition hover:border-white/30 hover:bg-white/10"
    >
      {children}
    </button>
  );
}

export default function UserDetailPage() {
  const router = useRouter();
  const params = useParams<{ userId?: string | string[] }>();
  const rawUserId = params?.userId;
  const userId = Array.isArray(rawUserId) ? rawUserId[0] : rawUserId;

  const [sessionUser, setSessionUser] = useState<User | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<ProfileForm>(EMPTY_PROFILE);
  const [edges, setEdges] = useState<EdgeDevice[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [ruleTypes, setRuleTypes] = useState<RuleType[]>([]);
  const [assignedRuleTypeIds, setAssignedRuleTypeIds] = useState<Set<string>>(new Set());

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null);
  const [showProfileModal, setShowProfileModal] = useState(false);

  const [edgeFormMode, setEdgeFormMode] = useState<'create' | 'edit'>('create');
  const [edgeForm, setEdgeForm] = useState<EdgeForm>(EMPTY_EDGE);
  const [activeEdge, setActiveEdge] = useState<EdgeDevice | null>(null);
  const [edgeSaving, setEdgeSaving] = useState(false);
  const [edgeError, setEdgeError] = useState<string | null>(null);
  const [edgeSuccess, setEdgeSuccess] = useState<string | null>(null);
  const [showEdgeModal, setShowEdgeModal] = useState(false);

  const [cameraFormMode, setCameraFormMode] = useState<'create' | 'edit'>('create');
  const [activeCamera, setActiveCamera] = useState<Camera | null>(null);
  const [cameraForm, setCameraForm] = useState<CameraForm>(EMPTY_CAMERA);
  const [cameraSaving, setCameraSaving] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraSuccess, setCameraSuccess] = useState<string | null>(null);
  const [approvalEdgeByCameraId, setApprovalEdgeByCameraId] = useState<Record<string, string>>({});
  const [approvalBusy, setApprovalBusy] = useState<string | null>(null);
  const [unassignBusy, setUnassignBusy] = useState<string | null>(null);
  const [showCameraModal, setShowCameraModal] = useState(false);

  const [rulesSaving, setRulesSaving] = useState(false);
  const [rulesError, setRulesError] = useState<string | null>(null);
  const [rulesSuccess, setRulesSuccess] = useState<string | null>(null);
  const [showRulesModal, setShowRulesModal] = useState(false);
  const [ruleDraft, setRuleDraft] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!userId) return;
    async function guardAndLoad() {
      const session = await getSessionUser();
      if (!session) {
        router.replace('/auth/login');
        return;
      }
      if (!session.is_admin) {
        router.replace('/dashboard');
        return;
      }
      setSessionUser(session);
      await loadAll(userId);
    }
    guardAndLoad();
  }, [router, userId]);

  const isSelf = useMemo(() => Boolean(sessionUser && user && sessionUser.id === user.id), [sessionUser, user]);
  const assignedRuleTypes = useMemo(
    () => ruleTypes.filter((ruleType) => assignedRuleTypeIds.has(ruleType.id)),
    [ruleTypes, assignedRuleTypeIds]
  );

  async function loadAll(targetUserId: string) {
    setLoading(true);
    setError(null);
    setProfileError(null);
    setProfileSuccess(null);
    setEdgeError(null);
    setEdgeSuccess(null);
    setCameraError(null);
    setCameraSuccess(null);
    setRulesError(null);
    setRulesSuccess(null);

    try {
      const [userData, edgeData, cameraData, ruleTypesData, userRuleTypesData] = await Promise.all([
        getUser(targetUserId),
        getEdgeDevices(targetUserId),
        getCameras({ userId: targetUserId }),
        getRuleTypes(),
        getUserRuleTypes(targetUserId)
      ]);
      setUser(userData);
      setEdges(edgeData);
      setCameras(cameraData);
      setRuleTypes(ruleTypesData);
      setAssignedRuleTypeIds(new Set(userRuleTypesData.map((item) => item.rule_type_id)));
      setProfile({
        first_name: userData.first_name || '',
        last_name: userData.last_name || '',
        email: userData.email || '',
        phone: userData.phone || '',
        is_admin: userData.is_admin,
        is_active: userData.is_active,
        password: '',
        confirm_password: ''
      });
      setEdgeForm(EMPTY_EDGE);
      setEdgeFormMode('create');
      setActiveEdge(null);
      setCameraForm(EMPTY_CAMERA);
      setCameraFormMode('create');
      setActiveCamera(null);
    } catch (err) {
      setError('Unable to load user details right now.');
    } finally {
      setLoading(false);
    }
  }

  function updateProfileField<K extends keyof ProfileForm>(field: K, value: ProfileForm[K]) {
    setProfile((prev) => ({ ...prev, [field]: value }));
  }

  async function handleProfileSave() {
    if (!user || !userId || profileSaving) return;
    setProfileError(null);
    setProfileSuccess(null);

    const payload: AdminUserUpdate = {};
    const nextFirst = profile.first_name.trim();
    const nextLast = profile.last_name.trim();
    const nextEmail = profile.email.trim();
    const nextPhone = profile.phone.trim();

    if (!nextFirst || !nextLast || !nextEmail) {
      setProfileError('First name, last name, and email are required.');
      return;
    }

    if (nextFirst !== user.first_name) payload.first_name = nextFirst;
    if (nextLast !== user.last_name) payload.last_name = nextLast;
    if (nextEmail !== user.email) payload.email = nextEmail;

    const normalizedPhone = nextPhone ? nextPhone : null;
    if ((user.phone || null) !== normalizedPhone) payload.phone = normalizedPhone;

    if (!isSelf) {
      if (profile.is_admin !== user.is_admin) payload.is_admin = profile.is_admin;
      if (profile.is_active !== user.is_active) payload.is_active = profile.is_active;
    }

    if (profile.password || profile.confirm_password) {
      if (profile.password !== profile.confirm_password) {
        setProfileError('Passwords do not match.');
        return;
      }
      payload.password = profile.password;
      payload.confirm_password = profile.confirm_password;
    }

    if (Object.keys(payload).length === 0) {
      setProfileError('No changes to save.');
      return;
    }

    try {
      setProfileSaving(true);
      const updated = await updateUser(userId, payload);
      setUser(updated);
      setProfile({
        first_name: updated.first_name || '',
        last_name: updated.last_name || '',
        email: updated.email || '',
        phone: updated.phone || '',
        is_admin: updated.is_admin,
        is_active: updated.is_active,
        password: '',
        confirm_password: ''
      });
      setProfileSuccess('User profile updated.');
    } catch (err) {
      setProfileError('Unable to save profile changes.');
    } finally {
      setProfileSaving(false);
    }
  }

  function openProfileModal() {
    setProfileError(null);
    setProfileSuccess(null);
    setShowProfileModal(true);
  }

  function closeProfileModal() {
    if (profileSaving) return;
    setShowProfileModal(false);
  }

  function openEdgeCreate() {
    if (edgeSaving) return;
    setEdgeFormMode('create');
    setActiveEdge(null);
    setEdgeForm(EMPTY_EDGE);
    setEdgeError(null);
    setEdgeSuccess(null);
    setShowEdgeModal(true);
  }

  function openEdgeEdit(edge: EdgeDevice) {
    if (edgeSaving) return;
    setEdgeFormMode('edit');
    setActiveEdge(edge);
    setEdgeForm({
      name: edge.name,
      api_key: edge.api_key,
      location: edge.location,
      ip: edge.ip,
      password: '',
      is_active: edge.is_active
    });
    setEdgeError(null);
    setEdgeSuccess(null);
    setShowEdgeModal(true);
  }

  function closeEdgeModal() {
    if (edgeSaving) return;
    setShowEdgeModal(false);
  }

  function updateEdgeField<K extends keyof EdgeForm>(field: K, value: EdgeForm[K]) {
    setEdgeForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleEdgeSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!userId || edgeSaving) return;
    setEdgeError(null);
    setEdgeSuccess(null);

    const base = {
      name: edgeForm.name.trim(),
      api_key: edgeForm.api_key.trim(),
      location: edgeForm.location.trim(),
      ip: edgeForm.ip.trim(),
      is_active: edgeForm.is_active
    };

    if (!base.name || !base.api_key || !base.location || !base.ip) {
      setEdgeError('All fields except password are required.');
      return;
    }

    try {
      setEdgeSaving(true);
      if (edgeFormMode === 'create') {
        if (!edgeForm.password.trim()) {
          setEdgeError('Password is required for new edge devices.');
          return;
        }
        const created = await createEdgeDevice({
          ...base,
          password: edgeForm.password.trim(),
          user_id: userId
        });
        setEdges((prev) => [created, ...prev]);
        setEdgeForm(EMPTY_EDGE);
        setEdgeFormMode('create');
        setActiveEdge(null);
        setEdgeSuccess('Edge device created.');
        setShowEdgeModal(false);
      } else if (activeEdge) {
        const payload: EdgeDeviceUpdate = { ...base };
        if (edgeForm.password.trim()) {
          payload.password = edgeForm.password.trim();
        }
        const updated = await updateEdgeDevice(activeEdge.id, payload);
        setEdges((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        setEdgeForm(EMPTY_EDGE);
        setEdgeFormMode('create');
        setActiveEdge(null);
        setEdgeSuccess('Edge device updated.');
        setShowEdgeModal(false);
      }
    } catch (err) {
      setEdgeError('Unable to save edge device.');
    } finally {
      setEdgeSaving(false);
    }
  }

  async function handleEdgeDelete(edge: EdgeDevice) {
    if (edgeSaving) return;
    const ok = window.confirm(`Delete edge device "${edge.name}"? This cannot be undone.`);
    if (!ok) return;
    setEdgeError(null);
    setEdgeSuccess(null);
    try {
      setEdgeSaving(true);
      await deleteEdgeDevice(edge.id);
      setEdges((prev) => prev.filter((item) => item.id !== edge.id));
      setEdgeSuccess('Edge device deleted.');
    } catch (err) {
      setEdgeError('Unable to delete edge device.');
    } finally {
      setEdgeSaving(false);
    }
  }

  function openCameraCreate() {
    if (cameraSaving) return;
    setCameraFormMode('create');
    setActiveCamera(null);
    setCameraForm(EMPTY_CAMERA);
    setCameraError(null);
    setCameraSuccess(null);
    setShowCameraModal(true);
  }

  function openCameraEdit(camera: Camera) {
    if (cameraSaving) return;
    setCameraFormMode('edit');
    setActiveCamera(camera);
    setCameraForm({
      camera_name: camera.camera_name,
      role: camera.role,
      rtsp_url: '',
      is_active: camera.is_active
    });
    setCameraError(null);
    setCameraSuccess(null);
    setShowCameraModal(true);
  }

  function closeCameraModal() {
    if (cameraSaving) return;
    setShowCameraModal(false);
  }

  function updateCameraField<K extends keyof CameraForm>(field: K, value: CameraForm[K]) {
    setCameraForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleCameraSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!userId || cameraSaving) return;
    setCameraError(null);
    setCameraSuccess(null);

    const nextName = cameraForm.camera_name.trim();
    const nextRole = cameraForm.role.trim();

    if (!nextName || !nextRole) {
      setCameraError('Camera name and role are required.');
      return;
    }

    try {
      setCameraSaving(true);
      if (cameraFormMode === 'create') {
        if (!cameraForm.rtsp_url.trim()) {
          setCameraError('RTSP URL is required.');
          return;
        }
        const payload: CameraCreate = {
          camera_name: nextName,
          role: nextRole,
          rtsp_url: cameraForm.rtsp_url.trim(),
          is_active: cameraForm.is_active,
          user_id: userId
        };
        const created = await createCamera(payload);
        setCameras((prev) => [created, ...prev]);
        setCameraForm(EMPTY_CAMERA);
        setCameraFormMode('create');
        setActiveCamera(null);
        setCameraSuccess('Camera created.');
        setShowCameraModal(false);
      } else if (activeCamera) {
        const payload: CameraUpdate = {};
        if (nextName !== activeCamera.camera_name) payload.camera_name = nextName;
        if (nextRole !== activeCamera.role) payload.role = nextRole;
        if (cameraForm.rtsp_url.trim()) payload.rtsp_url = cameraForm.rtsp_url.trim();
        if (cameraForm.is_active !== activeCamera.is_active) payload.is_active = cameraForm.is_active;

        if (Object.keys(payload).length === 0) {
          setCameraError('No changes to save.');
          return;
        }

        const updated = await updateCamera(activeCamera.id, payload);
        setCameras((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        setActiveCamera(null);
        setCameraForm(EMPTY_CAMERA);
        setCameraSuccess('Camera updated.');
        setShowCameraModal(false);
      }
    } catch (err) {
      setCameraError('Unable to save camera.');
    } finally {
      setCameraSaving(false);
    }
  }

  async function handleCameraDelete(camera: Camera) {
    if (cameraSaving) return;
    const ok = window.confirm(`Delete camera "${camera.camera_name}"? This cannot be undone.`);
    if (!ok) return;
    setCameraError(null);
    setCameraSuccess(null);
    try {
      setCameraSaving(true);
      await deleteCamera(camera.id);
      setCameras((prev) => prev.filter((item) => item.id !== camera.id));
      setCameraSuccess('Camera deleted.');
    } catch (err) {
      setCameraError('Unable to delete camera.');
    } finally {
      setCameraSaving(false);
    }
  }

  function updateApprovalEdge(cameraId: string, edgeId: string) {
    setApprovalEdgeByCameraId((prev) => ({ ...prev, [cameraId]: edgeId }));
  }

  async function handleApprove(camera: Camera) {
    if (approvalBusy) return;
    const fallbackEdge = edges[0]?.id || '';
    const selectedEdge = approvalEdgeByCameraId[camera.id] || fallbackEdge;
    if (!selectedEdge) {
      setCameraError('Assign an edge before approving.');
      return;
    }
    setCameraError(null);
    setCameraSuccess(null);
    try {
      setApprovalBusy(camera.id);
      const updated = await approveCamera(camera.id, selectedEdge);
      setCameras((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setCameraSuccess('Camera approved.');
    } catch (err) {
      setCameraError('Unable to approve camera.');
    } finally {
      setApprovalBusy(null);
    }
  }

  async function handleUnassign(camera: Camera) {
    if (unassignBusy) return;
    const ok = window.confirm(`Unassign camera "${camera.camera_name}" from edge?`);
    if (!ok) return;
    setCameraError(null);
    setCameraSuccess(null);
    try {
      setUnassignBusy(camera.id);
      const updated = await unassignCamera(camera.id);
      setCameras((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setCameraSuccess('Camera unassigned.');
    } catch (err) {
      setCameraError('Unable to unassign camera.');
    } finally {
      setUnassignBusy(null);
    }
  }

  function openRulesModal() {
    setRuleDraft(new Set(assignedRuleTypeIds));
    setRulesError(null);
    setRulesSuccess(null);
    setShowRulesModal(true);
  }

  function closeRulesModal() {
    if (rulesSaving) return;
    setShowRulesModal(false);
  }

  function toggleRuleDraft(ruleTypeId: string) {
    setRuleDraft((prev) => {
      const next = new Set(prev);
      if (next.has(ruleTypeId)) {
        next.delete(ruleTypeId);
      } else {
        next.add(ruleTypeId);
      }
      return next;
    });
  }

  async function handleSaveRules(nextIds?: Set<string>) {
    if (!userId || rulesSaving) return;
    setRulesError(null);
    setRulesSuccess(null);
    const payloadIds = nextIds ? Array.from(nextIds) : Array.from(assignedRuleTypeIds);
    try {
      setRulesSaving(true);
      const updated = await setUserRuleTypes(userId, payloadIds);
      setAssignedRuleTypeIds(new Set(updated.map((item) => item.rule_type_id)));
      setRulesSuccess('Rule access updated.');
      setShowRulesModal(false);
    } catch (err) {
      setRulesError('Unable to save rule access.');
    } finally {
      setRulesSaving(false);
    }
  }

  async function handleRuleRemove(ruleTypeId: string) {
    const next = new Set(assignedRuleTypeIds);
    next.delete(ruleTypeId);
    await handleSaveRules(next);
  }

  if (!userId) {
    return <div className="hud-card p-6 text-sm text-slate-300">User id is missing.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Administration
          </div>
          <div className="text-3xl sm:text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            User Overview
          </div>
          <div className="text-sm text-slate-300">Manage user assets and account profile.</div>
        </div>
        <div className="flex w-full flex-wrap items-center gap-3 lg:w-auto">
          <button
            type="button"
            className="btn-outline w-full rounded-full px-4 py-2 text-xs font-semibold text-slate-900 sm:w-auto"
            onClick={() => router.push('/dashboard/users')}
          >
            Back to users
          </button>
        </div>
      </div>

      {error && <AlertBox variant="error">{error}</AlertBox>}

      {loading ? (
        <div className="hud-card p-6 text-sm text-slate-300">Loading user profile…</div>
      ) : !user ? (
        <div className="hud-card p-6 text-sm text-slate-300">User not found.</div>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,2.1fr)_minmax(0,1fr)]">
            <div className="space-y-6">
              <div className="space-y-4 rounded-2xl border border-white/10 bg-slate-950/40 p-5 backdrop-blur-xl shadow-[0_25px_60px_-40px_rgba(15,23,42,0.95)]">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xl font-semibold text-slate-100">Assigned edge devices</div>
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-400">{edges.length} total</div>
                  </div>
                  <button
                    type="button"
                    className="btn-primary rounded-full px-4 py-2 text-xs font-semibold"
                    onClick={openEdgeCreate}
                  >
                    Add edge
                  </button>
                </div>

                {edgeError && <AlertBox variant="error">{edgeError}</AlertBox>}
                {edgeSuccess && <AlertBox variant="success">{edgeSuccess}</AlertBox>}

                {edges.length === 0 ? (
                  <div className="hud-card p-5 text-sm text-slate-400">No edge devices assigned.</div>
                ) : (
                  <div className="space-y-3">
                    {edges.map((edge) => (
                      <div key={edge.id} className="hud-card p-4">
                        <div className="flex flex-wrap items-center justify-between gap-4">
                          <div>
                            <div className="text-sm font-semibold text-slate-100">{edge.name}</div>
                            <div className="text-xs text-slate-400">{edge.location} · {edge.ip}</div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={['hud-pill', edge.is_active ? 'sev-info' : 'sev-warning'].join(' ')}>
                              {edge.is_active ? 'Active' : 'Inactive'}
                            </span>
                            <IconButton label="Edit edge" onClick={() => openEdgeEdit(edge)}>
                              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M4 20h4l10-10-4-4L4 16v4Z" />
                                <path d="M14 6l4 4" />
                              </svg>
                            </IconButton>
                            <IconButton label="Delete edge" onClick={() => handleEdgeDelete(edge)}>
                              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M3 6h18" />
                                <path d="M8 6V4h8v2" />
                                <path d="M7 6l1 14h8l1-14" />
                              </svg>
                            </IconButton>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-4 rounded-2xl border border-white/10 bg-slate-950/40 p-5 backdrop-blur-xl shadow-[0_25px_60px_-40px_rgba(15,23,42,0.95)]">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xl font-semibold text-slate-100">Registered cameras</div>
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-400">{cameras.length} total</div>
                  </div>
                  <button
                    type="button"
                    className="btn-primary rounded-full px-4 py-2 text-xs font-semibold"
                    onClick={openCameraCreate}
                  >
                    Add camera
                  </button>
                </div>

                {cameraError && <AlertBox variant="error">{cameraError}</AlertBox>}
                {cameraSuccess && <AlertBox variant="success">{cameraSuccess}</AlertBox>}

                {cameras.length === 0 ? (
                  <div className="hud-card p-5 text-sm text-slate-400">No cameras registered.</div>
                ) : (
                  <div className="space-y-3">
                    {cameras.map((camera) => {
                      const selectedEdge = approvalEdgeByCameraId[camera.id] || edges[0]?.id || '';
                      const edgeName = camera.edge_id
                        ? edges.find((edge) => edge.id === camera.edge_id)?.name || 'Unknown'
                        : 'None';
                      return (
                        <div key={camera.id} className="hud-card p-4 space-y-3">
                          <div className="flex flex-wrap items-start justify-between gap-4">
                            <div>
                              <div className="text-sm font-semibold text-slate-100">{camera.camera_name}</div>
                              <div className="text-xs text-slate-400">{camera.role}</div>
                              <div className="text-xs text-slate-500 mt-1">Edge: {edgeName}</div>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className={['hud-pill', approvalBadgeClass(camera.approval_status)].join(' ')}>
                                {formatApprovalStatus(camera.approval_status)}
                              </span>
                              <span className={['hud-pill', camera.is_active ? 'sev-info' : 'sev-warning'].join(' ')}>
                                {camera.is_active ? 'Active' : 'Inactive'}
                              </span>
                              <IconButton label="Edit camera" onClick={() => openCameraEdit(camera)}>
                                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M4 20h4l10-10-4-4L4 16v4Z" />
                                  <path d="M14 6l4 4" />
                                </svg>
                              </IconButton>
                              <IconButton label="Delete camera" onClick={() => handleCameraDelete(camera)}>
                                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M3 6h18" />
                                  <path d="M8 6V4h8v2" />
                                  <path d="M7 6l1 14h8l1-14" />
                                </svg>
                              </IconButton>
                            </div>
                          </div>
                          {camera.approval_status !== 'approved' && (
                            <div className="flex flex-wrap items-center gap-3">
                              <select
                                className="w-full rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs text-slate-100 shadow-inner focus:border-sky-300/60 focus:outline-none sm:w-56"
                                value={selectedEdge}
                                onChange={(event) => updateApprovalEdge(camera.id, event.target.value)}
                              >
                                {edges.length === 0 ? (
                                  <option value="">No edges available</option>
                                ) : (
                                  edges.map((edge) => (
                                    <option key={edge.id} value={edge.id} className="bg-slate-900">
                                      {edge.name}
                                    </option>
                                  ))
                                )}
                              </select>
                              <button
                                type="button"
                                className="btn-primary rounded-full px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                                onClick={() => handleApprove(camera)}
                                disabled={approvalBusy === camera.id || edges.length === 0}
                              >
                                {approvalBusy === camera.id ? 'Approving…' : 'Approve'}
                              </button>
                            </div>
                          )}
                          {camera.approval_status === 'approved' && camera.edge_id && (
                          <button
                            type="button"
                            className="hud-pill sev-critical rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] disabled:cursor-not-allowed disabled:opacity-60"
                            onClick={() => handleUnassign(camera)}
                            disabled={unassignBusy === camera.id}
                          >
                            {unassignBusy === camera.id ? 'Unassigning…' : 'Unassign edge'}
                          </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="space-y-4 rounded-2xl border border-white/10 bg-slate-950/40 p-5 backdrop-blur-xl shadow-[0_25px_60px_-40px_rgba(15,23,42,0.95)]">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xl font-semibold text-slate-100">Granted rule types</div>
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-400">{assignedRuleTypes.length} total</div>
                  </div>
                  <button
                    type="button"
                    className="btn-primary rounded-full px-4 py-2 text-xs font-semibold"
                    onClick={openRulesModal}
                  >
                    Add rules
                  </button>
                </div>

                {rulesError && <AlertBox variant="error">{rulesError}</AlertBox>}
                {rulesSuccess && <AlertBox variant="success">{rulesSuccess}</AlertBox>}

                {assignedRuleTypes.length === 0 ? (
                  <div className="hud-card p-5 text-sm text-slate-400">No rule types granted.</div>
                ) : (
                  <div className="space-y-3">
                    {assignedRuleTypes.map((ruleType) => (
                      <div key={ruleType.id} className="hud-card p-4">
                        <div className="flex flex-wrap items-center justify-between gap-4">
                          <div>
                            <div className="text-sm font-semibold text-slate-100">{ruleType.rule_type_name}</div>
                            <div className="text-xs text-slate-400">{ruleType.rule_type_slug}</div>
                          </div>
                          <div className="flex items-center gap-2">
                            <IconButton label="Remove rule" onClick={() => handleRuleRemove(ruleType.id)}>
                              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M3 6h18" />
                                <path d="M8 6V4h8v2" />
                                <path d="M7 6l1 14h8l1-14" />
                              </svg>
                            </IconButton>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-6">
              <div className="hud-card p-6 space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-400">User profile</div>
                    <div className="mt-2 text-2xl font-semibold text-slate-100">{formatName(user)}</div>
                    <div className="text-xs text-slate-400">Joined {formatDate(user.created_at)}</div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={['hud-pill', profile.is_admin ? 'sev-warning' : 'sev-info'].join(' ')}>
                      {profile.is_admin ? 'Admin' : 'Operator'}
                    </span>
                    <span className={['hud-pill', profile.is_active ? 'sev-info' : 'sev-warning'].join(' ')}>
                      {profile.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>

                {profileError && <AlertBox variant="error">{profileError}</AlertBox>}
                {profileSuccess && <AlertBox variant="success">{profileSuccess}</AlertBox>}

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm">
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-400">First name</div>
                    <div className="mt-2 text-slate-100">{profile.first_name}</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm">
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Last name</div>
                    <div className="mt-2 text-slate-100">{profile.last_name}</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm">
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Email</div>
                    <div className="mt-2 text-slate-100">{profile.email}</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm">
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Phone</div>
                    <div className="mt-2 text-slate-100">{profile.phone || 'Not set'}</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm">
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Role</div>
                    <div className="mt-2 text-slate-100">{profile.is_admin ? 'Administrator' : 'Operator'}</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm">
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Status</div>
                    <div className="mt-2 text-slate-100">{profile.is_active ? 'Active' : 'Inactive'}</div>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    className="btn-primary rounded-full px-5 py-2 text-sm font-semibold"
                    onClick={openProfileModal}
                  >
                    Edit profile
                  </button>
                </div>
              </div>
            </div>
          </div>

          <Modal
            open={showEdgeModal}
            title={edgeFormMode === 'create' ? 'Add edge device' : 'Edit edge device'}
            onClose={closeEdgeModal}
          >
            <form className="space-y-4" onSubmit={handleEdgeSave}>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <input
                  type="text"
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                  placeholder="Edge name"
                  value={edgeForm.name}
                  onChange={(event) => updateEdgeField('name', event.target.value)}
                />
                <input
                  type="text"
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                  placeholder="API key"
                  value={edgeForm.api_key}
                  onChange={(event) => updateEdgeField('api_key', event.target.value)}
                />
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <input
                  type="text"
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                  placeholder="Location"
                  value={edgeForm.location}
                  onChange={(event) => updateEdgeField('location', event.target.value)}
                />
                <input
                  type="text"
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                  placeholder="IP address"
                  value={edgeForm.ip}
                  onChange={(event) => updateEdgeField('ip', event.target.value)}
                />
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <input
                  type="password"
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                  placeholder={edgeFormMode === 'create' ? 'Edge password' : 'New password (optional)'}
                  value={edgeForm.password}
                  onChange={(event) => updateEdgeField('password', event.target.value)}
                />
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-white/30 bg-white/10"
                    checked={edgeForm.is_active}
                    onChange={(event) => updateEdgeField('is_active', event.target.checked)}
                  />
                  Active edge
                </label>
              </div>
              <div>
                <button
                  type="submit"
                  className="btn-primary rounded-full px-4 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={edgeSaving}
                >
                  {edgeSaving ? 'Saving…' : edgeFormMode === 'create' ? 'Create edge' : 'Save edge'}
                </button>
              </div>
            </form>
          </Modal>

          <Modal
            open={showCameraModal}
            title={cameraFormMode === 'create' ? 'Add camera' : 'Edit camera'}
            onClose={closeCameraModal}
          >
            <form className="space-y-4" onSubmit={handleCameraSave}>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <input
                  type="text"
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                  placeholder="Camera name"
                  value={cameraForm.camera_name}
                  onChange={(event) => updateCameraField('camera_name', event.target.value)}
                />
                <input
                  type="text"
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                  placeholder="Role"
                  value={cameraForm.role}
                  onChange={(event) => updateCameraField('role', event.target.value)}
                />
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <input
                  type="text"
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                  placeholder="RTSP URL"
                  value={cameraForm.rtsp_url}
                  onChange={(event) => updateCameraField('rtsp_url', event.target.value)}
                />
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-white/30 bg-white/10"
                    checked={cameraForm.is_active}
                    onChange={(event) => updateCameraField('is_active', event.target.checked)}
                  />
                  Active camera
                </label>
              </div>
              <div>
                <button
                  type="submit"
                  className="btn-primary rounded-full px-4 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={cameraSaving}
                >
                  {cameraSaving ? 'Saving…' : cameraFormMode === 'create' ? 'Create camera' : 'Save camera'}
                </button>
              </div>
            </form>
          </Modal>

          <Modal open={showRulesModal} title="Manage rule access" onClose={closeRulesModal}>
            <div className="space-y-4">
              {ruleTypes.length === 0 ? (
                <div className="text-sm text-slate-400">No rule types configured.</div>
              ) : (
                <div className="grid gap-3 md:grid-cols-2">
                  {ruleTypes.map((ruleType) => {
                    const isSelected = ruleDraft.has(ruleType.id);
                    return (
                      <button
                        key={ruleType.id}
                        type="button"
                        onClick={() => toggleRuleDraft(ruleType.id)}
                        className={[
                          'rounded-xl border px-4 py-3 text-left text-sm transition',
                          isSelected
                            ? 'border-emerald-400/50 bg-emerald-400/10 text-slate-100'
                            : 'border-white/10 bg-white/5 text-slate-300 hover:border-white/20'
                        ].join(' ')}
                      >
                        <div className="font-semibold">{ruleType.rule_type_name}</div>
                        <div className="text-xs text-slate-400">{ruleType.rule_type_slug}</div>
                      </button>
                    );
                  })}
                </div>
              )}
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  className="btn-primary rounded-full px-4 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => handleSaveRules(ruleDraft)}
                  disabled={rulesSaving}
                >
                  {rulesSaving ? 'Saving…' : 'Save access'}
                </button>
              </div>
            </div>
          </Modal>

          <Modal open={showProfileModal} title="Edit user profile" onClose={closeProfileModal}>
            <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); handleProfileSave(); }}>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="hud-label" htmlFor="modalFirstName">First name</label>
                  <input
                    id="modalFirstName"
                    type="text"
                    className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                    value={profile.first_name}
                    onChange={(event) => updateProfileField('first_name', event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="hud-label" htmlFor="modalLastName">Last name</label>
                  <input
                    id="modalLastName"
                    type="text"
                    className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                    value={profile.last_name}
                    onChange={(event) => updateProfileField('last_name', event.target.value)}
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="hud-label" htmlFor="modalEmail">Email</label>
                  <input
                    id="modalEmail"
                    type="email"
                    className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                    value={profile.email}
                    onChange={(event) => updateProfileField('email', event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="hud-label" htmlFor="modalPhone">Phone number</label>
                  <input
                    id="modalPhone"
                    type="tel"
                    className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                    value={profile.phone}
                    onChange={(event) => updateProfileField('phone', event.target.value)}
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="hud-label" htmlFor="modalPassword">New password</label>
                  <input
                    id="modalPassword"
                    type="password"
                    className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                    value={profile.password}
                    onChange={(event) => updateProfileField('password', event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="hud-label" htmlFor="modalConfirmPassword">Confirm password</label>
                  <input
                    id="modalConfirmPassword"
                    type="password"
                    className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none"
                    value={profile.confirm_password}
                    onChange={(event) => updateProfileField('confirm_password', event.target.value)}
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-white/30 bg-white/10"
                    checked={profile.is_admin}
                    onChange={(event) => updateProfileField('is_admin', event.target.checked)}
                    disabled={isSelf}
                  />
                  Admin access
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-400">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-white/30 bg-white/10"
                    checked={profile.is_active}
                    onChange={(event) => updateProfileField('is_active', event.target.checked)}
                    disabled={isSelf}
                  />
                  Account active
                </label>
              </div>
              {isSelf && (
                <div className="text-xs text-slate-500">
                  You cannot change your own admin status or deactivate yourself.
                </div>
              )}
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="submit"
                  className="btn-primary rounded-full px-4 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={profileSaving}
                >
                  {profileSaving ? 'Saving…' : 'Save changes'}
                </button>
              </div>
            </form>
          </Modal>
        </>
      )}
    </div>
  );
}
