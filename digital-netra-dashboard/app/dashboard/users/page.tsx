'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import { getUsers } from '@/lib/api';
import { getSessionUser } from '@/lib/auth';
import type { User } from '@/lib/types';

function formatName(user: User) {
  const full = `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim();
  return full || user.email || 'Unknown';
}

function formatDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export default function UsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        const data = await getUsers();
        setUsers(data);
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
                  <span>Joined {formatDate(user.created_at)}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="hidden md:block table-shell table-shell-no-scroll">
            <table className="w-full table-fixed text-sm">
              <thead>
                <tr>
                  <th className="text-left px-6 w-[25%]">Name</th>
                  <th className="text-left px-6 w-[35%]">Email</th>
                  <th className="text-left px-6 w-[15%]">Role</th>
                  <th className="text-left px-6 w-[15%]">Status</th>
                  <th className="text-right px-6 w-[10%]">Joined</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td className="px-6 font-medium text-slate-100 w-[25%]">{formatName(user)}</td>
                    <td className="px-6 text-slate-400 w-[35%]">{user.email}</td>
                    <td className="px-6 w-[15%]">
                      <span className={['hud-pill w-full justify-center', user.is_admin ? 'sev-warning' : 'sev-info'].join(' ')}>
                        {user.is_admin ? 'Admin' : 'Operator'}
                      </span>
                    </td>
                    <td className="px-6 w-[15%]">
                      <span className={['hud-pill w-full justify-center', user.is_active ? 'sev-info' : 'sev-warning'].join(' ')}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-6 text-right text-slate-400 w-[10%]">{formatDate(user.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
