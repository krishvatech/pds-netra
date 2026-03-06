'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import {
  createEdgeDevice,
  deleteEdgeDevice,
  getEdgeDevices,
  getUsers,
  updateEdgeDevice
} from '@/lib/api';
import { getSessionUser } from '@/lib/auth';
import type { EdgeDevice, EdgeDeviceUpdate, User } from '@/lib/types';

type FormMode = 'create' | 'edit';

type EdgeForm = {
  name: string;
  api_key: string;
  location: string;
  ip: string;
  password: string;
  user_id: string;
  is_active: boolean;
};

const EMPTY_FORM: EdgeForm = {
  name: '',
  api_key: '',
  location: '',
  ip: '',
  password: '',
  user_id: '',
  is_active: true
};

function formatDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatUserName(user?: User) {
  if (!user) return 'Unknown';
  return `${user.first_name} ${user.last_name}`.trim() || user.email || 'Unknown';
}

export default function EdgeDevicesPage() {
  const router = useRouter();
  const [edges, setEdges] = useState<EdgeDevice[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [formMode, setFormMode] = useState<FormMode>('create');
  const [activeEdge, setActiveEdge] = useState<EdgeDevice | null>(null);
  const [formData, setFormData] = useState<EdgeForm>(EMPTY_FORM);

  useEffect(() => {
    async function guardAndLoad() {
      const sessionUser = await getSessionUser();
      if (!sessionUser) {
        router.replace('/auth/login');
        return;
      }
      if (!sessionUser.is_admin) {
        router.replace('/dashboard');
        return;
      }
      await loadAll();
    }
    guardAndLoad();
  }, [router]);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [edgesData, usersData] = await Promise.all([getEdgeDevices(), getUsers()]);
      setEdges(edgesData);
      setUsers(usersData);
    } catch (err) {
      setError('Unable to load edge devices right now.');
    } finally {
      setLoading(false);
    }
  }

  const totalCount = useMemo(() => edges.length, [edges]);
  const activeCount = useMemo(() => edges.filter((edge) => edge.is_active).length, [edges]);
  const userMap = useMemo(() => {
    const map = new Map<string, User>();
    users.forEach((user) => map.set(user.id, user));
    return map;
  }, [users]);

  function updateField<K extends keyof EdgeForm>(field: K, value: EdgeForm[K]) {
    setFormData((prev) => ({ ...prev, [field]: value }));
  }

  function openCreate() {
    if (saving) return;
    setFormMode('create');
    setActiveEdge(null);
    setFormData(EMPTY_FORM);
    setActionError(null);
    setSuccess(null);
  }

  function openEdit(edge: EdgeDevice) {
    if (saving) return;
    setFormMode('edit');
    setActiveEdge(edge);
    setFormData({
      name: edge.name,
      api_key: edge.api_key,
      location: edge.location,
      ip: edge.ip,
      password: '',
      user_id: edge.user_id,
      is_active: edge.is_active
    });
    setActionError(null);
    setSuccess(null);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    setActionError(null);
    setSuccess(null);

    const payloadBase = {
      name: formData.name.trim(),
      api_key: formData.api_key.trim(),
      location: formData.location.trim(),
      ip: formData.ip.trim(),
      user_id: formData.user_id,
      is_active: formData.is_active
    };

    if (!payloadBase.name || !payloadBase.api_key || !payloadBase.location || !payloadBase.ip || !payloadBase.user_id) {
      setActionError('All fields except password are required.');
      return;
    }

    try {
      setSaving(true);
      if (formMode === 'create') {
        if (!formData.password.trim()) {
          setActionError('Password is required for new edge devices.');
          return;
        }
        const created = await createEdgeDevice({
          ...payloadBase,
          password: formData.password.trim()
        });
        setEdges((prev) => [created, ...prev]);
        setFormData(EMPTY_FORM);
        setSuccess('Edge device created.');
      } else if (activeEdge) {
        const updatePayload: EdgeDeviceUpdate = { ...payloadBase };
        if (formData.password.trim()) {
          updatePayload.password = formData.password.trim();
        }
        const updated = await updateEdgeDevice(activeEdge.id, updatePayload);
        setEdges((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        setFormMode('create');
        setActiveEdge(null);
        setFormData(EMPTY_FORM);
        setSuccess('Edge device updated.');
      }
    } catch (err) {
      setActionError('Unable to save edge device. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(edge: EdgeDevice) {
    if (saving) return;
    const ok = window.confirm(`Delete edge device "${edge.name}"? This cannot be undone.`);
    if (!ok) return;
    setActionError(null);
    setSuccess(null);
    try {
      setSaving(true);
      await deleteEdgeDevice(edge.id);
      setEdges((prev) => prev.filter((item) => item.id !== edge.id));
      if (activeEdge?.id === edge.id) {
        setFormMode('create');
        setActiveEdge(null);
        setFormData(EMPTY_FORM);
      }
      setSuccess('Edge device deleted.');
    } catch (err) {
      setActionError('Unable to delete edge device. Please try again.');
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
            Administration
          </div>
          <div className="text-3xl sm:text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Edge Devices
          </div>
          <div className="text-sm text-slate-300">Assign edge gateways to operators and cameras.</div>
        </div>
        <div className="flex w-full flex-wrap items-center gap-3 lg:w-auto">
          <div className="hud-card w-full px-4 py-2 text-center text-xs text-slate-300 sm:w-auto">
            Active {activeCount} / {totalCount}
          </div>
        </div>
      </div>

      {error && <AlertBox variant="error">{error}</AlertBox>}

      <div className="hud-card p-6">
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="hud-label" htmlFor="edgeName">Edge name</label>
              <input
                id="edgeName"
                type="text"
                className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                placeholder="Warehouse Edge 01"
                value={formData.name}
                onChange={(event) => updateField('name', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="hud-label" htmlFor="edgeApiKey">API key</label>
              <input
                id="edgeApiKey"
                type="text"
                className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                placeholder="edge_live_key_123"
                value={formData.api_key}
                onChange={(event) => updateField('api_key', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="hud-label" htmlFor="edgeLocation">Location</label>
              <input
                id="edgeLocation"
                type="text"
                className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                placeholder="Dock 3, Building A"
                value={formData.location}
                onChange={(event) => updateField('location', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="hud-label" htmlFor="edgeIp">IP address</label>
              <input
                id="edgeIp"
                type="text"
                className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                placeholder="192.168.1.20"
                value={formData.ip}
                onChange={(event) => updateField('ip', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="hud-label" htmlFor="edgePassword">
                {formMode === 'create' ? 'Password' : 'Password (leave blank to keep unchanged)'}
              </label>
              <input
                id="edgePassword"
                type="password"
                className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-400/70 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                placeholder={formMode === 'create' ? 'Enter device password' : '••••••'}
                value={formData.password}
                onChange={(event) => updateField('password', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="hud-label" htmlFor="edgeUser">Assign user</label>
              <select
                id="edgeUser"
                className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                value={formData.user_id}
                onChange={(event) => updateField('user_id', event.target.value)}
              >
                <option value="">Select user</option>
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {formatUserName(user)} · {user.email}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className={[
                'px-4 py-2 text-xs uppercase tracking-[0.2em] rounded-full border transition',
                formData.is_active
                  ? 'border-sky-300/60 bg-sky-300/10 text-sky-200'
                  : 'border-white/10 bg-white/5 text-slate-300 hover:border-white/30'
              ].join(' ')}
              onClick={() => updateField('is_active', true)}
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
              onClick={() => updateField('is_active', false)}
              aria-pressed={!formData.is_active}
            >
              Inactive
            </button>
          </div>

          {actionError && <AlertBox variant="error">{actionError}</AlertBox>}
          {success && <AlertBox variant="success">{success}</AlertBox>}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              className="btn-primary rounded-full px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={saving}
            >
              {saving ? 'Saving…' : formMode === 'create' ? 'Add Edge Device' : 'Update Edge Device'}
            </button>
            {formMode === 'edit' && (
              <button
                type="button"
                className="rounded-full border border-white/10 bg-white/5 px-5 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-200 hover:border-white/20 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
                onClick={openCreate}
                disabled={saving}
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      </div>

      {loading ? (
        <div className="hud-card p-6 text-sm text-slate-300">Loading edge devices…</div>
      ) : edges.length === 0 ? (
        <div className="hud-card p-6 text-sm text-slate-300">No edge devices created yet.</div>
      ) : (
        <div className="table-shell table-shell-no-scroll hidden md:block">
          <table className="w-full table-fixed text-sm">
            <thead>
              <tr>
                <th className="text-left px-6 w-[20%]">Name</th>
                <th className="text-left px-6 w-[20%]">User</th>
                <th className="text-left px-6 w-[15%]">IP</th>
                <th className="text-left px-6 w-[20%]">Location</th>
                <th className="text-left px-6 w-[10%]">Status</th>
                <th className="text-right px-6 w-[15%]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {edges.map((edge) => (
                <tr key={edge.id}>
                  <td className="px-6 font-medium text-slate-100 w-[20%]">{edge.name}</td>
                  <td className="px-6 text-slate-400 w-[20%]">
                    {formatUserName(userMap.get(edge.user_id))}
                  </td>
                  <td className="px-6 text-slate-400 w-[15%]">{edge.ip}</td>
                  <td className="px-6 text-slate-400 w-[20%]">{edge.location}</td>
                  <td className="px-6 w-[10%]">
                    <span className={['hud-pill w-full justify-center', edge.is_active ? 'sev-info' : 'sev-warning'].join(' ')}>
                      {edge.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 text-right w-[15%]">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200 hover:border-white/20 hover:bg-white/10"
                        onClick={() => openEdit(edge)}
                        disabled={saving}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs text-red-200 hover:border-red-500/60 hover:bg-red-500/20"
                        onClick={() => handleDelete(edge)}
                        disabled={saving}
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

      {!loading && edges.length > 0 && (
        <div className="space-y-3 md:hidden">
          {edges.map((edge) => (
            <div key={edge.id} className="hud-card p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Edge device</div>
                  <div className="mt-1 text-base font-semibold text-slate-100">{edge.name}</div>
                  <div className="text-xs text-slate-400">{edge.ip}</div>
                  <div className="text-xs text-slate-400">{edge.location}</div>
                  <div className="text-xs text-slate-400">
                    User: {formatUserName(userMap.get(edge.user_id))}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span className={['hud-pill', edge.is_active ? 'sev-info' : 'sev-warning'].join(' ')}>
                    {edge.is_active ? 'Active' : 'Inactive'}
                  </span>
                  <span className="text-xs text-slate-500">Created {formatDate(edge.created_at)}</span>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-2">
                <button
                  type="button"
                  className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200 hover:border-white/20 hover:bg-white/10"
                  onClick={() => openEdit(edge)}
                  disabled={saving}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs text-red-200 hover:border-red-500/60 hover:bg-red-500/20"
                  onClick={() => handleDelete(edge)}
                  disabled={saving}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
