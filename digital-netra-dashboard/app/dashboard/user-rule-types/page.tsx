'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import { getRuleTypes, getUserRuleTypes, getUsers, setUserRuleTypes } from '@/lib/api';
import { getSessionUser } from '@/lib/auth';
import type { RuleType, User } from '@/lib/types';

function formatName(user: User) {
  const full = `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim();
  return full || user.email || 'Unknown';
}

export default function UserRuleTypesPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [ruleTypes, setRuleTypes] = useState<RuleType[]>([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [assignedRuleTypeIds, setAssignedRuleTypeIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [loadingAssignments, setLoadingAssignments] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

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

  const assignableUsers = useMemo(() => users.filter((user) => !user.is_admin), [users]);
  const selectedUser = useMemo(
    () => assignableUsers.find((user) => user.id === selectedUserId) || null,
    [assignableUsers, selectedUserId]
  );
  const assignedCount = assignedRuleTypeIds.size;

  async function loadAll() {
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const [usersData, ruleTypesData] = await Promise.all([getUsers(), getRuleTypes()]);
      setUsers(usersData);
      setRuleTypes(ruleTypesData);

      const assignable = usersData.filter((user) => !user.is_admin);
      if (assignable.length > 0) {
        const initialUserId = assignable[0].id;
        setSelectedUserId(initialUserId);
        await loadAssignments(initialUserId);
      } else {
        setSelectedUserId('');
        setAssignedRuleTypeIds(new Set());
      }
    } catch (err) {
      setError('Unable to load user access data right now.');
    } finally {
      setLoading(false);
    }
  }

  async function loadAssignments(userId: string) {
    if (!userId) return;
    setLoadingAssignments(true);
    setError(null);
    try {
      const data = await getUserRuleTypes(userId);
      setAssignedRuleTypeIds(new Set(data.map((item) => item.rule_type_id)));
    } catch (err) {
      setError('Unable to load rule access for this user.');
    } finally {
      setLoadingAssignments(false);
    }
  }

  function handleUserChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const nextUserId = event.target.value;
    setSelectedUserId(nextUserId);
    setSuccess(null);
    setError(null);
    if (nextUserId) {
      loadAssignments(nextUserId);
    } else {
      setAssignedRuleTypeIds(new Set());
    }
  }

  function toggleRuleType(ruleTypeId: string) {
    setAssignedRuleTypeIds((prev) => {
      const next = new Set(prev);
      if (next.has(ruleTypeId)) {
        next.delete(ruleTypeId);
      } else {
        next.add(ruleTypeId);
      }
      return next;
    });
  }

  async function handleSave() {
    if (!selectedUserId || saving) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await setUserRuleTypes(selectedUserId, Array.from(assignedRuleTypeIds));
      setAssignedRuleTypeIds(new Set(updated.map((item) => item.rule_type_id)));
      setSuccess('User rule access updated.');
    } catch (err) {
      setError('Unable to save rule access. Please try again.');
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
            User Rule Access
          </div>
          <div className="text-sm text-slate-300">Grant or revoke rule type access for each operator.</div>
        </div>
        <div className="flex w-full flex-wrap items-center gap-3 lg:w-auto">
          <div className="hud-card w-full px-4 py-2 text-center text-xs text-slate-300 sm:w-auto">
            Assigned {assignedCount} / {ruleTypes.length}
          </div>
          <button
            type="button"
            className="btn-primary w-full rounded-full px-5 py-2 text-center text-xs font-semibold uppercase tracking-[0.25em] sm:w-auto"
            onClick={handleSave}
            disabled={saving || !selectedUserId || loadingAssignments}
          >
            {saving ? 'Saving…' : 'Save Access'}
          </button>
        </div>
      </div>

      {error && <AlertBox variant="error">{error}</AlertBox>}
      {success && <AlertBox variant="success">{success}</AlertBox>}

      {loading ? (
        <div className="hud-card p-6 text-sm text-slate-300">Loading user access…</div>
      ) : assignableUsers.length === 0 ? (
        <div className="hud-card p-6">
          <div className="text-lg font-semibold font-display">No operators available</div>
          <div className="text-sm text-slate-400 mt-2">Create a non-admin user to manage rule access.</div>
        </div>
      ) : ruleTypes.length === 0 ? (
        <div className="hud-card p-6">
          <div className="text-lg font-semibold font-display">No rule types found</div>
          <div className="text-sm text-slate-400 mt-2">Create rule types first, then grant access.</div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="hud-card p-5">
            <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Operator</div>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-lg font-semibold text-slate-100">
                  {selectedUser ? formatName(selectedUser) : 'Select an operator'}
                </div>
                {selectedUser && <div className="text-xs text-slate-400">{selectedUser.email}</div>}
              </div>
              <div className="w-full sm:w-72">
                <select
                  className="w-full rounded-lg border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-slate-100 shadow-inner focus:border-sky-300/60 focus:outline-none focus:ring-2 focus:ring-sky-300/20"
                  value={selectedUserId}
                  onChange={handleUserChange}
                >
                  {assignableUsers.map((user) => (
                    <option key={user.id} value={user.id} className="bg-slate-900">
                      {formatName(user)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {loadingAssignments ? (
            <div className="hud-card p-6 text-sm text-slate-300">Loading rule access…</div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {ruleTypes.map((ruleType) => {
                const isAssigned = assignedRuleTypeIds.has(ruleType.id);
                return (
                  <button
                    key={ruleType.id}
                    type="button"
                    onClick={() => toggleRuleType(ruleType.id)}
                    className={[
                      'hud-card group flex flex-col items-start gap-3 rounded-2xl border px-4 py-4 text-left transition',
                      isAssigned
                        ? 'border-emerald-400/40 bg-emerald-400/10'
                        : 'border-white/10 bg-white/5 hover:border-white/20'
                    ].join(' ')}
                  >
                    <div className="flex w-full items-start justify-between gap-3">
                      <div>
                        <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Rule type</div>
                        <div className="mt-2 text-base font-semibold text-slate-100">{ruleType.rule_type_name}</div>
                        <div className="mt-1 text-xs text-slate-400">{ruleType.rule_type_slug}</div>
                      </div>
                      <span
                        className={[
                          'hud-pill px-3 py-1 text-[10px] uppercase tracking-[0.3em]',
                          isAssigned ? 'sev-info' : 'sev-warning'
                        ].join(' ')}
                      >
                        {isAssigned ? 'Allowed' : 'Blocked'}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400">Model: {ruleType.model_name}</div>
                    <div className="text-xs text-slate-500">Click to {isAssigned ? 'revoke' : 'grant'} access.</div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
