'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertBox } from '@/components/ui/alert-box';
import { getEdgeDevices } from '@/lib/api';
import { getSessionUser } from '@/lib/auth';
import type { EdgeDevice } from '@/lib/types';

function formatDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export default function MyEdgesPage() {
  const router = useRouter();
  const [edges, setEdges] = useState<EdgeDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function guardAndLoad() {
      const sessionUser = await getSessionUser();
      if (!sessionUser) {
        router.replace('/auth/login');
        return;
      }
      if (sessionUser.is_admin) {
        router.replace('/dashboard/edge-devices');
        return;
      }
      await loadEdges();
    }
    guardAndLoad();
  }, [router]);

  async function loadEdges() {
    setLoading(true);
    setError(null);
    try {
      const data = await getEdgeDevices();
      setEdges(data);
    } catch (err) {
      setError('Unable to load edge devices right now.');
    } finally {
      setLoading(false);
    }
  }

  const totalCount = useMemo(() => edges.length, [edges]);
  const activeCount = useMemo(() => edges.filter((edge) => edge.is_active).length, [edges]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">
            <span className="pulse-dot pulse-info" />
            Fleet Live
          </div>
          <div className="text-3xl sm:text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            My Edges
          </div>
          <div className="text-sm text-slate-300">Monitor the edge gateways assigned to your cameras.</div>
        </div>
        <div className="flex w-full flex-wrap items-center gap-3 lg:w-auto">
          <div className="hud-card w-full px-4 py-2 text-center text-xs text-slate-300 sm:w-auto">
            Active {activeCount} / {totalCount}
          </div>
        </div>
      </div>

      {error && <AlertBox variant="error">{error}</AlertBox>}

      {loading ? (
        <div className="hud-card p-6 text-sm text-slate-300">Loading edge devices…</div>
      ) : edges.length === 0 ? (
        <div className="hud-card p-6">
          <div className="text-lg font-semibold font-display">No edges assigned yet</div>
          <div className="text-sm text-slate-400 mt-2">
            Your cameras will appear here once an edge device is assigned.
          </div>
        </div>
      ) : (
        <div className="table-shell table-shell-no-scroll hidden md:block">
          <table className="w-full table-fixed text-sm">
            <thead>
              <tr>
                <th className="text-left px-6 w-[22%]">Name</th>
                <th className="text-left px-6 w-[18%]">IP</th>
                <th className="text-left px-6 w-[26%]">Location</th>
                <th className="text-left px-6 w-[16%]">Status</th>
                <th className="text-right px-6 w-[18%]">Created</th>
              </tr>
            </thead>
            <tbody>
              {edges.map((edge) => (
                <tr key={edge.id}>
                  <td className="px-6 font-medium text-slate-100 w-[22%]">{edge.name}</td>
                  <td className="px-6 text-slate-400 w-[18%]">{edge.ip}</td>
                  <td className="px-6 text-slate-400 w-[26%]">{edge.location}</td>
                  <td className="px-6 w-[16%]">
                    <span className={['hud-pill w-full justify-center', edge.is_active ? 'sev-info' : 'sev-warning'].join(' ')}>
                      {edge.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 text-right text-slate-400 w-[18%]">{formatDate(edge.created_at)}</td>
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
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span className={['hud-pill', edge.is_active ? 'sev-info' : 'sev-warning'].join(' ')}>
                    {edge.is_active ? 'Active' : 'Inactive'}
                  </span>
                  <span className="text-xs text-slate-500">Created {formatDate(edge.created_at)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
