'use client';

import { useEffect, useMemo, useState } from 'react';
import type { NotificationEndpoint } from '@/lib/types';
import { createNotificationEndpoint, deleteNotificationEndpoint, getNotificationEndpoints, updateNotificationEndpoint } from '@/lib/api';
import { getUser } from '@/lib/auth';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { ConfirmDialog } from '@/components/ui/dialog';
import { ToastStack, type ToastItem } from '@/components/ui/toast';
import { formatUtc } from '@/lib/formatters';

const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

const mockEndpoints: NotificationEndpoint[] = [
  {
    id: 'ENDPOINT-001',
    scope: 'HQ',
    godown_id: null,
    channel: 'EMAIL',
    target: 'hq.alerts@example.com',
    is_enabled: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  },
  {
    id: 'ENDPOINT-002',
    scope: 'GODOWN_MANAGER',
    godown_id: 'GDN_SAMPLE',
    channel: 'WHATSAPP',
    target: '+91XXXXXXXXXX',
    is_enabled: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
];

export default function NotificationsPage() {
  const [endpoints, setEndpoints] = useState<NotificationEndpoint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [confirmTitle, setConfirmTitle] = useState('');
  const [confirmMessage, setConfirmMessage] = useState('');
  const [confirmLabel, setConfirmLabel] = useState('Confirm');
  const [confirmVariant, setConfirmVariant] = useState<'default' | 'danger'>('default');
  const [pendingAction, setPendingAction] = useState<'disable' | 'delete' | null>(null);
  const [pendingEndpoint, setPendingEndpoint] = useState<NotificationEndpoint | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const [filterScope, setFilterScope] = useState('');
  const [filterChannel, setFilterChannel] = useState('');
  const [filterGodown, setFilterGodown] = useState('');

  const [form, setForm] = useState({
    scope: 'HQ',
    godown_id: '',
    channel: 'EMAIL',
    target: '',
    is_enabled: true
  });

  useEffect(() => {
    const user = getUser();
    if (!filterGodown && user?.godown_id) {
      setFilterGodown(String(user.godown_id));
    }
    if (form.scope === 'GODOWN_MANAGER' && !form.godown_id && user?.godown_id) {
      setForm((prev) => ({ ...prev, godown_id: String(user.godown_id) }));
    }
  }, [filterGodown, form.scope, form.godown_id]);

  const targetValidation = useMemo(() => {
    const trimmed = form.target.trim();
    if (!trimmed) return 'Target is required';
    if (form.channel === 'EMAIL') {
      const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed);
      return emailOk ? '' : 'Enter a valid email address';
    }
    if (form.channel === 'WHATSAPP' || form.channel === 'VOICE') {
      const phoneOk = /^\+?[1-9]\d{7,14}$/.test(trimmed);
      return phoneOk ? '' : 'Enter a valid phone number (E.164)';
    }
    return '';
  }, [form.channel, form.target]);

  const godownValidation = useMemo(() => {
    if (form.scope !== 'GODOWN_MANAGER') return '';
    return form.godown_id.trim() ? '' : 'Godown ID is required for Godown Manager scope';
  }, [form.scope, form.godown_id]);

  const params = useMemo(() => {
    const p: Record<string, string> = {};
    if (filterScope) p.scope = filterScope;
    if (filterChannel) p.channel = filterChannel;
    if (filterGodown) p.godown_id = filterGodown.trim();
    return p;
  }, [filterScope, filterChannel, filterGodown]);

  function pushToast(toast: Omit<ToastItem, 'id'>) {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((items) => [...items, { id, ...toast }]);
  }

  async function loadEndpoints(options?: { showToast?: boolean }) {
    setError(null);
    try {
      if (MOCK_MODE) {
        setEndpoints(mockEndpoints);
        return;
      }
      const rows = await getNotificationEndpoints(params);
      setEndpoints(rows ?? []);
      if (options?.showToast) {
        pushToast({
          type: 'info',
          title: 'Endpoints refreshed',
          message: `Loaded ${rows?.length ?? 0} endpoints`
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load endpoints');
    }
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!mounted) return;
      await loadEndpoints({ showToast: false });
    })();
    return () => { mounted = false; };
  }, [params]);

  async function submitEndpoint() {
    setError(null);
    if (targetValidation || godownValidation) {
      setError(targetValidation || godownValidation);
      return;
    }
    setSaving(true);
    try {
      if (!MOCK_MODE) {
        if (editingId) {
          await updateNotificationEndpoint(editingId, {
            scope: form.scope,
            godown_id: form.scope === 'GODOWN_MANAGER' ? form.godown_id.trim() : null,
            channel: form.channel,
            target: form.target.trim(),
            is_enabled: form.is_enabled
          });
        } else {
          await createNotificationEndpoint({
            scope: form.scope,
            godown_id: form.scope === 'GODOWN_MANAGER' ? form.godown_id.trim() : null,
            channel: form.channel,
            target: form.target.trim(),
            is_enabled: form.is_enabled
          });
        }
      }
      pushToast({
        type: 'success',
        title: editingId ? 'Endpoint updated' : 'Endpoint created',
        message: `${form.channel} → ${form.target.trim()}`
      });
      setForm({ scope: 'HQ', godown_id: '', channel: 'EMAIL', target: '', is_enabled: true });
      setEditingId(null);
      await loadEndpoints();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save endpoint');
    } finally {
      setSaving(false);
    }
  }

  async function toggleEndpoint(endpoint: NotificationEndpoint) {
    setError(null);
    try {
      if (endpoint.is_enabled) {
        setPendingEndpoint(endpoint);
        setPendingAction('disable');
        setConfirmTitle('Disable notification?');
        setConfirmMessage(`Disable ${endpoint.channel} delivery for ${endpoint.target}?`);
        setConfirmLabel('Disable');
        setConfirmVariant('default');
        setConfirmOpen(true);
        return;
      }
      if (!MOCK_MODE) await updateNotificationEndpoint(endpoint.id, { is_enabled: true });
      pushToast({
        type: 'success',
        title: 'Endpoint enabled',
        message: `${endpoint.channel} → ${endpoint.target}`
      });
      await loadEndpoints();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update endpoint');
    }
  }

  function beginEdit(endpoint: NotificationEndpoint) {
    setForm({
      scope: endpoint.scope,
      godown_id: endpoint.godown_id ?? '',
      channel: endpoint.channel,
      target: endpoint.target,
      is_enabled: endpoint.is_enabled
    });
    setEditingId(endpoint.id);
  }

  function cancelEdit() {
    setForm({ scope: 'HQ', godown_id: '', channel: 'EMAIL', target: '', is_enabled: true });
    setEditingId(null);
  }

  function closeConfirm(force = false) {
    if (confirmBusy && !force) return;
    setConfirmOpen(false);
    setPendingAction(null);
    setPendingEndpoint(null);
  }

  async function removeEndpoint(endpoint: NotificationEndpoint) {
    setError(null);
    setPendingEndpoint(endpoint);
    setPendingAction('delete');
    setConfirmTitle('Delete endpoint?');
    setConfirmMessage(`Delete ${endpoint.channel} destination for ${endpoint.target}? This cannot be undone.`);
    setConfirmLabel('Delete');
    setConfirmVariant('danger');
    setConfirmOpen(true);
  }

  async function handleConfirm() {
    if (!pendingEndpoint || !pendingAction) {
      closeConfirm(false);
      return;
    }
    setConfirmBusy(true);
    try {
      if (pendingAction === 'disable') {
        if (!MOCK_MODE) {
          await updateNotificationEndpoint(pendingEndpoint.id, { is_enabled: false });
        }
        pushToast({
          type: 'info',
          title: 'Endpoint disabled',
          message: `${pendingEndpoint.channel} → ${pendingEndpoint.target}`
        });
      } else if (pendingAction === 'delete') {
        if (!MOCK_MODE) {
          await deleteNotificationEndpoint(pendingEndpoint.id);
        }
        if (editingId === pendingEndpoint.id) cancelEdit();
        pushToast({
          type: 'success',
          title: 'Endpoint deleted',
          message: `${pendingEndpoint.channel} → ${pendingEndpoint.target}`
        });
      }
      await loadEndpoints();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Action failed');
    } finally {
      setConfirmBusy(false);
      closeConfirm(true);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">Admin controls</div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Notification Routing
          </div>
          <div className="text-sm text-slate-300">Manage HQ + godown recipients for WhatsApp, Email, and Voice alerts.</div>
        </div>
        <div className="intel-banner">HQ only</div>
      </div>

      {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">{editingId ? 'Edit endpoint' : 'Add endpoint'}</div>
        </CardHeader>
        <CardContent>
          {editingId && (
            <div className="mb-3 text-sm text-amber-200">
              Editing endpoint <span className="font-mono">{editingId}</span>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <div>
              <Label>Scope</Label>
              <Select
                value={form.scope}
                onChange={(e) => setForm((s) => ({ ...s, scope: e.target.value }))}
                options={[
                  { label: 'HQ', value: 'HQ' },
                  { label: 'Godown Manager', value: 'GODOWN_MANAGER' }
                ]}
              />
            </div>
            <div>
              <Label>Godown ID</Label>
              <Input
                value={form.godown_id}
                onChange={(e) => setForm((s) => ({ ...s, godown_id: e.target.value }))}
                placeholder="Auto (from login)"
                disabled={form.scope !== 'GODOWN_MANAGER'}
              />
              {godownValidation && form.scope === 'GODOWN_MANAGER' && (
                <div className="mt-1 text-xs text-rose-300">{godownValidation}</div>
              )}
            </div>
            <div>
              <Label>Channel</Label>
              <Select
                value={form.channel}
                onChange={(e) => setForm((s) => ({ ...s, channel: e.target.value }))}
                options={[
                  { label: 'Email', value: 'EMAIL' },
                  { label: 'WhatsApp', value: 'WHATSAPP' },
                  { label: 'Voice Call', value: 'VOICE' }
                ]}
              />
            </div>
            <div>
              <Label>Target</Label>
              <Input
                value={form.target}
                onChange={(e) => setForm((s) => ({ ...s, target: e.target.value }))}
                placeholder={form.channel === 'EMAIL' ? 'name@example.com' : '+91XXXXXXXXXX'}
              />
              <div className="mt-1 text-[11px] text-slate-400">
                {form.channel === 'EMAIL'
                  ? 'Format: name@example.com'
                  : 'Format: E.164, e.g., +91XXXXXXXXXX'}
              </div>
              {targetValidation && (
                <div className="mt-1 text-xs text-rose-300">{targetValidation}</div>
              )}
            </div>
            <div className="flex items-end gap-3">
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="checkbox"
                  checked={form.is_enabled}
                  onChange={(e) => setForm((s) => ({ ...s, is_enabled: e.target.checked }))}
                />
                Enabled
              </label>
              <Button onClick={submitEndpoint} disabled={saving || Boolean(targetValidation) || Boolean(godownValidation)}>
                {saving ? 'Saving...' : editingId ? 'Update' : 'Create'}
              </Button>
              {editingId && (
                <Button variant="outline" onClick={cancelEdit}>
                  Cancel
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmOpen}
        title={confirmTitle}
        message={confirmMessage}
        confirmLabel={confirmLabel}
        confirmVariant={confirmVariant}
        isBusy={confirmBusy}
        onCancel={() => closeConfirm(false)}
        onConfirm={handleConfirm}
      />

      <ToastStack
        items={toasts}
        onDismiss={(id) => setToasts((items) => items.filter((t) => t.id !== id))}
      />

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Endpoints</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
            <div>
              <Label>Scope</Label>
              <Select
                value={filterScope}
                onChange={(e) => setFilterScope(e.target.value)}
                options={[
                  { label: 'All', value: '' },
                  { label: 'HQ', value: 'HQ' },
                  { label: 'Godown Manager', value: 'GODOWN_MANAGER' }
                ]}
              />
            </div>
            <div>
              <Label>Channel</Label>
              <Select
                value={filterChannel}
                onChange={(e) => setFilterChannel(e.target.value)}
                options={[
                  { label: 'All', value: '' },
                  { label: 'Email', value: 'EMAIL' },
                  { label: 'WhatsApp', value: 'WHATSAPP' },
                  { label: 'Voice Call', value: 'VOICE' }
                ]}
              />
            </div>
            <div>
              <Label>Godown</Label>
              <Input value={filterGodown} onChange={(e) => setFilterGodown(e.target.value)} placeholder="Auto (from login)" />
            </div>
            <div className="flex items-end">
              <Button className="btn-refresh" variant="outline" onClick={() => loadEndpoints({ showToast: true })}>Refresh</Button>
            </div>
          </div>

          <div className="table-shell overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400">
                  <th className="py-2 pr-3">Scope</th>
                  <th className="py-2 pr-3">Godown</th>
                  <th className="py-2 pr-3">Channel</th>
                  <th className="py-2 pr-3">Target</th>
                  <th className="py-2 pr-3">Enabled</th>
                  <th className="py-2 pr-3">Updated</th>
                  <th className="py-2 pr-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {endpoints.map((ep) => (
                  <tr key={ep.id} className={`border-t border-white/10 ${ep.is_enabled ? '' : 'opacity-60'}`}>
                    <td className="py-2 pr-3">{ep.scope === 'GODOWN_MANAGER' ? 'Godown Manager' : ep.scope}</td>
                    <td className="py-2 pr-3">{ep.godown_id ?? '-'}</td>
                    <td className="py-2 pr-3">{ep.channel}</td>
                    <td className="py-2 pr-3">{ep.target}</td>
                    <td className="py-2 pr-3">{ep.is_enabled ? 'Yes' : 'No'}</td>
                    <td className="py-2 pr-3">{formatUtc(ep.updated_at)}</td>
                    <td className="py-2 pr-3">
                      <div className="flex flex-wrap gap-2">
                        <Button variant="outline" onClick={() => beginEdit(ep)}>Edit</Button>
                        <Button variant="outline" onClick={() => toggleEndpoint(ep)}>
                          {ep.is_enabled ? 'Disable' : 'Enable'}
                        </Button>
                        <Button variant="danger" onClick={() => removeEndpoint(ep)}>
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {endpoints.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-slate-500">No endpoints found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}