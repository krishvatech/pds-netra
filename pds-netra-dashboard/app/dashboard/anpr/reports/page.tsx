'use client';

import { useEffect, useMemo, useState } from 'react';
import { getUser } from '@/lib/auth';
import { getAnprDailyReport, getGodowns } from '@/lib/api';
import type { AnprDailyReportResponse, GodownListItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Table, THead, TBody, TR, TH, TD } from '@/components/ui/table';
import { ErrorBanner } from '@/components/ui/error-banner';

function toDateStr(d: Date) {
  return d.toISOString().slice(0, 10);
}

export default function AnprReportsPage() {
  const [godownId, setGodownId] = useState('');
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [timezoneName, setTimezoneName] = useState('Asia/Kolkata');
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 6);
    return toDateStr(d);
  });
  const [dateTo, setDateTo] = useState(() => toDateStr(new Date()));

  const [data, setData] = useState<AnprDailyReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const godownOptions = useMemo(() => {
    const opts = godowns.map((g) => ({ label: g.name || g.godown_id, value: g.godown_id }));
    if (godownId && !opts.some((o) => o.value === godownId)) {
      return [{ label: godownId, value: godownId }, ...opts];
    }
    return opts;
  }, [godowns, godownId]);

  useEffect(() => {
    if (!godownId) {
      const user = getUser();
      if (user?.godown_id) setGodownId(String(user.godown_id));
    }
  }, [godownId]);

  useEffect(() => {
    let alive = true;
    async function loadGodowns() {
      try {
        const resp = await getGodowns({});
        const items = Array.isArray(resp) ? resp : resp.items;
        if (alive) setGodowns(items || []);
      } catch {
        // Non-blocking.
      }
    }
    loadGodowns();
    return () => {
      alive = false;
    };
  }, []);

  async function load() {
    if (!godownId || !dateFrom || !dateTo) return;
    try {
      setError(null);
      const resp = await getAnprDailyReport({
        godown_id: godownId,
        timezone_name: timezoneName,
        date_from: dateFrom,
        date_to: dateTo
      });
      setData(resp);
    } catch (e: any) {
      setError(e?.message || 'Failed to load report');
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [godownId, timezoneName, dateFrom, dateTo]);

  const totals = useMemo(() => {
    const rows = data?.rows || [];
    return rows.reduce(
      (acc, r) => {
        acc.planned_items += Number(r.planned_items || 0);
        acc.arrived += Number(r.arrived || 0);
        acc.delayed += Number(r.delayed || 0);
        acc.no_show += Number(r.no_show || 0);
        acc.cancelled += Number(r.cancelled || 0);
        return acc;
      },
      { planned_items: 0, arrived: 0, delayed: 0, no_show: 0, cancelled: 0 }
    );
  }, [data]);

  function exportCsv() {
    const rows = data?.rows || [];
    const header = ['date_local', 'expected_count', 'planned_items', 'arrived', 'delayed', 'no_show', 'cancelled'];
    const lines = [header.join(',')];
    for (const r of rows) {
      lines.push(
        [
          r.date_local,
          r.expected_count ?? '',
          r.planned_items ?? 0,
          r.arrived ?? 0,
          r.delayed ?? 0,
          r.no_show ?? 0,
          r.cancelled ?? 0
        ].join(',')
      );
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `anpr_report_${godownId}_${dateFrom}_to_${dateTo}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      <div className="text-xl font-semibold">ANPR Reports</div>
      {error && <ErrorBanner message={error} />}

      <Card>
        <CardHeader>
          <div className="font-medium">Filters</div>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <Label>Godown</Label>
            <Select
              value={godownId}
              onChange={(e) => setGodownId(e.target.value)}
              options={godownOptions}
              placeholder="Select godown..."
            />
          </div>
          <div>
            <Label>Timezone</Label>
            <Input value={timezoneName} onChange={(e) => setTimezoneName(e.target.value)} />
          </div>
          <div>
            <Label>Date From</Label>
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div>
            <Label>Date To</Label>
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div className="flex items-end gap-2">
            <button
              className="rounded-xl px-4 py-2 text-sm border border-white/10 bg-white/5 hover:bg-white/10"
              onClick={load}
            >
              Refresh
            </button>
            <button
              className="rounded-xl px-4 py-2 text-sm border border-white/10 bg-white/5 hover:bg-white/10"
              onClick={exportCsv}
              disabled={!data?.rows?.length}
            >
              Export CSV
            </button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="font-medium">Daily Summary</div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-xs text-slate-300">
            Planned items: {totals.planned_items} • Arrived: {totals.arrived} • Delayed: {totals.delayed} • No show: {totals.no_show} • Cancelled: {totals.cancelled}
          </div>
          <div className="overflow-auto">
            <Table>
              <THead>
                <TR>
                  <TH>Date</TH>
                  <TH>Expected Count</TH>
                  <TH>Planned Items</TH>
                  <TH>Arrived</TH>
                  <TH>Delayed</TH>
                  <TH>No Show</TH>
                  <TH>Cancelled</TH>
                </TR>
              </THead>
              <TBody>
                {(data?.rows || []).length === 0 ? (
                  <TR>
                    <TD colSpan={7} className="text-sm text-slate-500">
                      No rows
                    </TD>
                  </TR>
                ) : (
                  (data?.rows || []).map((r) => (
                    <TR key={r.date_local}>
                      <TD className="font-semibold">{r.date_local}</TD>
                      <TD>{r.expected_count ?? '—'}</TD>
                      <TD>{r.planned_items}</TD>
                      <TD>{r.arrived}</TD>
                      <TD>{r.delayed}</TD>
                      <TD>{r.no_show}</TD>
                      <TD>{r.cancelled}</TD>
                    </TR>
                  ))
                )}
              </TBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
