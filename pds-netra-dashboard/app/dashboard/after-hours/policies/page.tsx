'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { getAfterHoursPolicies, getAfterHoursPolicyAudit, getGodowns } from '@/lib/api';
import type { AfterHoursPolicy, AfterHoursPolicyAudit, GodownListItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { ErrorBanner } from '@/components/ui/error-banner';
import { formatUtc } from '@/lib/formatters';
import { friendlyErrorMessage } from '@/lib/friendly-error';

export default function AfterHoursPoliciesPage() {
  const [policies, setPolicies] = useState<AfterHoursPolicy[]>([]);
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [auditItems, setAuditItems] = useState<AfterHoursPolicyAudit[]>([]);
  const [selectedGodown, setSelectedGodown] = useState('');
  const [loading, setLoading] = useState(true);
  const [auditLoading, setAuditLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [policiesResp, godownResp] = await Promise.all([
          getAfterHoursPolicies(),
          getGodowns()
        ]);
        if (!mounted) return;
        const godownItems = Array.isArray(godownResp) ? godownResp : godownResp.items ?? [];
        setGodowns(godownItems);
        const allowedIds = new Set(godownItems.map((g) => g.godown_id));
        const policyItems = (policiesResp.items ?? []).filter((p) => allowedIds.has(p.godown_id));
        setPolicies(policyItems);
        if (!selectedGodown && policyItems.length > 0) {
          setSelectedGodown(policyItems[0].godown_id);
        }
      } catch (e) {
        if (mounted)
          setError(
            friendlyErrorMessage(
              e,
              'Unable to load after-hours policies. Check your connection or refresh.'
            )
          );
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    if (!selectedGodown) {
      setAuditItems([]);
      return;
    }
    (async () => {
      setAuditLoading(true);
      try {
        const resp = await getAfterHoursPolicyAudit(selectedGodown, { limit: 100 });
        if (!mounted) return;
        setAuditItems(resp.items ?? []);
      } catch (e) {
        if (mounted)
          setError(
            friendlyErrorMessage(
              e,
              'Unable to load the audit log for that godown. Please try again or select another one.'
            )
          );
      } finally {
        if (mounted) setAuditLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [selectedGodown]);

  const godownOptions = useMemo(() => {
    const options = godowns.map((g) => ({
      label: `${g.name ?? g.godown_id} (${g.godown_id})`,
      value: g.godown_id
    }));
    return [{ label: 'Select godown', value: '' }, ...options];
  }, [godowns]);

  const nameById = useMemo(() => {
    const map = new Map<string, string>();
    godowns.forEach((g) => map.set(g.godown_id, g.name ?? g.godown_id));
    return map;
  }, [godowns]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <div className="hud-pill">After-hours policies</div>
          <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
            Policy Overrides & Audit
          </div>
          <div className="text-sm text-slate-300">Review and audit after-hours policy overrides by godown.</div>
        </div>
        <div className="flex gap-2">
          <Link href="/dashboard/after-hours" className="text-sm text-amber-300 hover:underline">Back to alerts</Link>
          <Link href="/dashboard/rules" className="text-sm text-amber-300 hover:underline">Edit policy</Link>
        </div>
      </div>

      {error && <ErrorBanner message={error} onRetry={() => window.location.reload()} />}

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Override list</div>
          <div className="text-sm text-slate-600">Only godowns with explicit overrides appear here.</div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-sm text-slate-600">Loading...</div>
          ) : (
            <div className="table-shell overflow-auto">
              <table className="min-w-[720px] text-sm">
                <thead>
                  <tr className="text-left text-slate-400">
                    <th className="py-2 pr-3">Godown</th>
                    <th className="py-2 pr-3">Window</th>
                    <th className="py-2 pr-3">Cooldown</th>
                    <th className="py-2 pr-3">Presence allowed</th>
                    <th className="py-2 pr-3">Enabled</th>
                    <th className="py-2 pr-3">Updated</th>
                    <th className="py-2 pr-3">Audit</th>
                  </tr>
                </thead>
                <tbody>
                  {policies.map((p) => (
                    <tr key={p.godown_id} className="border-t border-white/10">
                      <td className="py-2 pr-3">
                        <div className="font-medium">{nameById.get(p.godown_id) ?? p.godown_id}</div>
                        <div className="text-xs text-slate-500">{p.godown_id}</div>
                      </td>
                      <td className="py-2 pr-3">{p.day_start} - {p.day_end}</td>
                      <td className="py-2 pr-3">{p.cooldown_seconds}s</td>
                      <td className="py-2 pr-3">{p.presence_allowed ? 'Yes' : 'No'}</td>
                      <td className="py-2 pr-3">{p.enabled ? 'Enabled' : 'Disabled'}</td>
                      <td className="py-2 pr-3">{formatUtc(p.updated_at ?? p.created_at ?? '')}</td>
                      <td className="py-2 pr-3">
                        <Button variant="outline" onClick={() => setSelectedGodown(p.godown_id)}>
                          View audit
                        </Button>
                      </td>
                    </tr>
                  ))}
                  {policies.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-6 text-center text-slate-500">
                        No overrides yet. Defaults apply statewide.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="hud-card">
        <CardHeader>
          <div className="text-lg font-semibold font-display">Audit log</div>
          <div className="text-sm text-slate-600">Per-godown policy change history.</div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
            <div>
              <div className="text-xs text-slate-600 mb-1">Godown</div>
              <Select value={selectedGodown} onChange={(e) => setSelectedGodown(e.target.value)} options={godownOptions} />
            </div>
          </div>
          {auditLoading ? (
            <div className="text-sm text-slate-600">Loading...</div>
          ) : (
            <div className="table-shell overflow-auto">
              <table className="min-w-[720px] text-sm">
                <thead>
                  <tr className="text-left text-slate-400">
                    <th className="py-2 pr-3">Time</th>
                    <th className="py-2 pr-3">Actor</th>
                    <th className="py-2 pr-3">Changes</th>
                  </tr>
                </thead>
                <tbody>
                  {auditItems.map((item) => (
                    <tr key={item.id} className="border-t border-white/10">
                      <td className="py-2 pr-3">{formatUtc(item.created_at ?? '')}</td>
                      <td className="py-2 pr-3">{item.actor ?? 'system'}</td>
                      <td className="py-2 pr-3">
                        {Object.entries(item.changes ?? {}).map(([k, v]) => (
                          <div key={k} className="text-xs text-slate-500">
                            {k}: {String((v as any).from)} {'→'} {String((v as any).to)}
                          </div>
                        ))}
                      </td>
                    </tr>
                  ))}
                  {auditItems.length === 0 && (
                    <tr>
                      <td colSpan={3} className="py-6 text-center text-slate-500">
                        No audit entries for this godown.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
