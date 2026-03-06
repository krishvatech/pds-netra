'use client';

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import { getRuleTypes, getUserRuleTypes, getUsers, setUserRuleTypes } from '@/lib/api';
import { getSessionUser } from '@/lib/auth';
import type { RuleType, User } from '@/lib/types';

function formatName(user: User) {
  const full = `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim();
  return full || user.email || 'Unknown';
}

function Modal({
  open,
  title,
  onClose,
  children
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
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

export default function UsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [ruleTypes, setRuleTypes] = useState<RuleType[]>([]);
  const [userRuleTypeIdsByUserId, setUserRuleTypeIdsByUserId] = useState<Record<string, Set<string>>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rulesError, setRulesError] = useState<string | null>(null);
  const [rulesSuccess, setRulesSuccess] = useState<string | null>(null);
  const [rulesSaving, setRulesSaving] = useState(false);
  const [showRulesModal, setShowRulesModal] = useState(false);
  const [activeRulesUser, setActiveRulesUser] = useState<User | null>(null);
  const [ruleDraft, setRuleDraft] = useState<Set<string>>(new Set());

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
      setError(null);
      setLoading(true);
      try {
        const [usersData, ruleTypesData, userRuleTypesData] = await Promise.all([
          getUsers(),
          getRuleTypes(),
          getUserRuleTypes()
        ]);
        const map: Record<string, Set<string>> = {};
        userRuleTypesData.forEach((item) => {
          if (!map[item.user_id]) map[item.user_id] = new Set();
          map[item.user_id].add(item.rule_type_id);
        });
        setUsers(usersData);
        setRuleTypes(ruleTypesData);
        setUserRuleTypeIdsByUserId(map);
      } catch (err) {
        setError('Unable to load users right now.');
      } finally {
        setLoading(false);
      }
    }
    guardAndLoad();
  }, [router]);

  const activeCount = useMemo(() => users.filter((user) => user.is_active).length, [users]);
  const adminCount = useMemo(() => users.filter((user) => user.is_admin).length, [users]);

  function openRulesModal(user: User) {
    const current = userRuleTypeIdsByUserId[user.id] ?? new Set();
    setActiveRulesUser(user);
    setRuleDraft(new Set(current));
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

  async function handleSaveRules() {
    if (!activeRulesUser || rulesSaving) return;
    setRulesError(null);
    setRulesSuccess(null);
    try {
      setRulesSaving(true);
      const updated = await setUserRuleTypes(activeRulesUser.id, Array.from(ruleDraft));
      setUserRuleTypeIdsByUserId((prev) => ({
        ...prev,
        [activeRulesUser.id]: new Set(updated.map((item) => item.rule_type_id))
      }));
      setRulesSuccess('Rule access updated.');
      setShowRulesModal(false);
    } catch (err) {
      setRulesError('Unable to save rule access.');
    } finally {
      setRulesSaving(false);
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
            Users
          </div>
          <div className="text-sm text-slate-300">Review all registered operators and administrators.</div>
        </div>
        <div className="flex w-full flex-wrap items-center gap-3 lg:w-auto">
          <div className="hud-card w-full px-4 py-2 text-center text-xs text-slate-300 sm:w-auto">
            Active {activeCount} / {users.length}
          </div>
          <div className="hud-card w-full px-4 py-2 text-center text-xs text-slate-300 sm:w-auto">
            Admins {adminCount}
          </div>
        </div>
      </div>

      {error && <AlertBox variant="error">{error}</AlertBox>}

      {loading ? (
        <div className="hud-card p-6 text-sm text-slate-300">Loading users…</div>
      ) : (
        <>
          <div className="space-y-3 md:hidden">
            {users.map((user) => (
              <div key={user.id} className="hud-card p-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="text-xs uppercase tracking-[0.3em] text-slate-500">User</div>
                    <div className="mt-1 text-base font-semibold text-slate-100">{formatName(user)}</div>
                    <div className="text-xs text-slate-400">{user.email}</div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <span className={['hud-pill', user.is_admin ? 'sev-warning' : 'sev-info'].join(' ')}>
                      {user.is_admin ? 'Admin' : 'Operator'}
                    </span>
                    <span className={['hud-pill', user.is_active ? 'sev-info' : 'sev-warning'].join(' ')}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  <span>
                    Rules: {userRuleTypeIdsByUserId[user.id]?.size ?? 0}
                  </span>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    className="btn-outline rounded-full px-4 py-2 text-xs font-semibold text-slate-900"
                    onClick={() => openRulesModal(user)}
                  >
                    Manage rules
                  </button>
                  <button
                    type="button"
                    className="btn-outline rounded-full px-4 py-2 text-xs font-semibold text-slate-900"
                    onClick={() => router.push(`/dashboard/users/${user.id}`)}
                  >
                    View user
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="hidden md:block table-shell table-shell-no-scroll">
            <table className="w-full table-fixed text-sm">
              <thead>
                <tr>
                  <th className="text-left px-6 w-[22%]">Name</th>
                  <th className="text-left px-6 w-[26%]">Email</th>
                  <th className="text-left px-6 w-[12%]">Role</th>
                  <th className="text-left px-6 w-[12%]">Status</th>
                  <th className="text-left px-6 w-[18%]">Rule types</th>
                  <th className="text-right px-6 w-[10%]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td className="px-6 font-medium text-slate-100 w-[22%]">{formatName(user)}</td>
                    <td className="px-6 text-slate-400 w-[26%]">{user.email}</td>
                    <td className="px-6 w-[12%]">
                      <span className={['hud-pill w-full justify-center', user.is_admin ? 'sev-warning' : 'sev-info'].join(' ')}>
                        {user.is_admin ? 'Admin' : 'Operator'}
                      </span>
                    </td>
                    <td className="px-6 w-[12%]">
                      <span className={['hud-pill w-full justify-center', user.is_active ? 'sev-info' : 'sev-warning'].join(' ')}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-6 text-slate-300 w-[18%]">
                      <button
                        type="button"
                        className="btn-outline rounded-full px-3 py-2 text-xs font-semibold text-slate-900"
                        onClick={() => openRulesModal(user)}
                      >
                        Manage ({userRuleTypeIdsByUserId[user.id]?.size ?? 0})
                      </button>
                    </td>
                    <td className="px-6 text-right w-[10%]">
                      <button
                        type="button"
                        className="btn-outline rounded-full px-4 py-2 text-xs font-semibold text-slate-900"
                        onClick={() => router.push(`/dashboard/users/${user.id}`)}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <Modal
        open={showRulesModal}
        title={activeRulesUser ? `Rules for ${formatName(activeRulesUser)}` : 'Manage rule access'}
        onClose={closeRulesModal}
      >
        <div className="space-y-4">
          {rulesError && <AlertBox variant="error">{rulesError}</AlertBox>}
          {rulesSuccess && <AlertBox variant="success">{rulesSuccess}</AlertBox>}
          {ruleTypes.length === 0 ? (
            <div className="text-sm text-slate-400">No rule types configured.</div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {ruleTypes.map((ruleType) => {
                const isSelected = ruleDraft.has(ruleType.id);
                return (
                  <label
                    key={ruleType.id}
                    className={[
                      'flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3 text-sm transition',
                      isSelected
                        ? 'border-emerald-400/50 bg-emerald-400/10 text-slate-100'
                        : 'border-white/10 bg-white/5 text-slate-300 hover:border-white/20'
                    ].join(' ')}
                  >
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4 rounded border-white/30 bg-white/10"
                      checked={isSelected}
                      onChange={() => toggleRuleDraft(ruleType.id)}
                    />
                    <span>
                      <div className="font-semibold">{ruleType.rule_type_name}</div>
                      <div className="text-xs text-slate-400">{ruleType.rule_type_slug}</div>
                    </span>
                  </label>
                );
              })}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="btn-primary rounded-full px-4 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
              onClick={handleSaveRules}
              disabled={rulesSaving}
            >
              {rulesSaving ? 'Saving…' : 'Save access'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
