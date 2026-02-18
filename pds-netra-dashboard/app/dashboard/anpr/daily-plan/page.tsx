'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { getUser } from '@/lib/auth';
import {
  addAnprDailyPlanItem,
  deleteAnprDailyPlanItem,
  getAnprDailyPlan,
  getGodowns,
  importAnprDailyPlanItemsCsv,
  upsertAnprDailyPlan,
  updateAnprDailyPlanItem
} from '@/lib/api';
import type { AnprDailyPlanItem, AnprDailyPlanResponse, CsvImportSummary, GodownListItem } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, THead, TBody, TR, TH, TD } from '@/components/ui/table';
import { ErrorBanner } from '@/components/ui/error-banner';

const statusOptions = [
  { label: 'PLANNED', value: 'PLANNED' },
  { label: 'ARRIVED', value: 'ARRIVED' },
  { label: 'DELAYED', value: 'DELAYED' },
  { label: 'CANCELLED', value: 'CANCELLED' },
  { label: 'NO_SHOW', value: 'NO_SHOW' },
];

const IST_TZ = 'Asia/Kolkata';

function formatIstDateTime(value?: string | Date | null) {
  if (!value) return 'N/A';
  const d = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return 'N/A';
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: IST_TZ,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  }).format(d);
}

type PlanCsvPreviewRow = {
  plate_text: string;
  expected_by_local?: string;
  status?: string;
  notes?: string;
  error?: string;
};

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === ',' && !inQuotes) {
      out.push(cur);
      cur = '';
      continue;
    }
    cur += ch;
  }
  out.push(cur);
  return out;
}

function parseCsv(text: string): PlanCsvPreviewRow[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== '');
  if (lines.length === 0) return [];
  const header = parseCsvLine(lines[0]).map((h) => h.trim().toLowerCase());
  const rows: PlanCsvPreviewRow[] = [];
  for (let i = 1; i < lines.length; i += 1) {
    const values = parseCsvLine(lines[i]);
    const row: Record<string, string> = {};
    header.forEach((key, idx) => {
      row[key] = (values[idx] ?? '').trim();
    });
    const plate_text =
      row['plate_text'] || row['plate'] || row['plate_no'] || row['plate_number'] || '';
    const preview: PlanCsvPreviewRow = {
      plate_text,
      expected_by_local: row['expected_by_local'] || row['expected_by'] || '',
      status: row['status'] || '',
      notes: row['notes'] || ''
    };
    if (!plate_text.trim()) {
      preview.error = 'plate_text required';
    }
    rows.push(preview);
  }
  return rows;
}

function hhmm(v?: string | null) {
  if (!v) return '';
  // "HH:MM:SS" -> "HH:MM"
  return String(v).slice(0, 5);
}

function statusBadge(s: string) {
  const v = (s || '').toUpperCase();
  if (v === 'ARRIVED') return <Badge className="bg-green-100 text-green-800 border border-green-200">ARRIVED</Badge>;
  if (v === 'DELAYED') return <Badge className="bg-amber-100 text-amber-800 border border-amber-200">DELAYED</Badge>;
  if (v === 'NO_SHOW') return <Badge className="bg-red-100 text-red-800 border border-red-200">NO SHOW</Badge>;
  if (v === 'CANCELLED') return <Badge className="bg-slate-100 text-slate-700 border border-slate-200">CANCELLED</Badge>;
  return <Badge className="bg-slate-100 text-slate-800 border border-slate-200">PLANNED</Badge>;
}

export default function AnprDailyPlanPage() {
  const [godownId, setGodownId] = useState('');
  const [godowns, setGodowns] = useState<GodownListItem[]>([]);
  const [timezoneName, setTimezoneName] = useState('Asia/Kolkata');
  const [dateLocal, setDateLocal] = useState(() => new Date().toISOString().slice(0, 10)); // YYYY-MM-DD

  const [expectedCount, setExpectedCount] = useState<string>('');
  const [cutoffTime, setCutoffTime] = useState<string>('18:00');
  const [planSettingsDirty, setPlanSettingsDirty] = useState(false);

  const [addPlate, setAddPlate] = useState('');
  const [addExpectedBy, setAddExpectedBy] = useState('');
  const [addStatus, setAddStatus] = useState('PLANNED');
  const [addNotes, setAddNotes] = useState('');

  const [data, setData] = useState<AnprDailyPlanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importRows, setImportRows] = useState<PlanCsvPreviewRow[]>([]);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<CsvImportSummary | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const plannedRef = useRef<HTMLDivElement | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

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
    if (!godownId || !dateLocal) return;
    try {
      setError(null);
      const resp = await getAnprDailyPlan({
        godown_id: godownId,
        date: dateLocal,
        timezone_name: timezoneName
      });
      setData(resp);
      if (!planSettingsDirty) {
        setExpectedCount(
          resp.plan.expected_count === null || resp.plan.expected_count === undefined ? '' : String(resp.plan.expected_count)
        );
        setCutoffTime(hhmm(resp.plan.cutoff_time_local) || '18:00');
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to load daily plan');
    }
  }

  useEffect(() => {
    setPlanSettingsDirty(false);
  }, [godownId, dateLocal]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [godownId, dateLocal, timezoneName]);

  const planId = data?.plan?.id || '';
  const items: AnprDailyPlanItem[] = data?.items || [];

  const summary = useMemo(() => {
    const c = { ARRIVED: 0, DELAYED: 0, NO_SHOW: 0, CANCELLED: 0, PLANNED: 0 };
    for (const it of items) {
      const s = String(it.effective_status || 'PLANNED').toUpperCase();
      if (s in c) (c as any)[s] += 1;
      else c.PLANNED += 1;
    }
    return c;
  }, [items]);

  async function onSavePlan() {
    if (!godownId || !dateLocal) return;
    try {
      setBusy(true);
      setError(null);
      const rawExpected = expectedCount.trim();
      const parsedExpected = rawExpected === '' ? null : Number(rawExpected);
      if (parsedExpected !== null && (!Number.isFinite(parsedExpected) || parsedExpected < 0)) {
        setError('Expected Count must be a valid non-negative number');
        return;
      }
      await upsertAnprDailyPlan({
        godown_id: godownId,
        plan_date: dateLocal,
        timezone_name: timezoneName,
        expected_count: parsedExpected === null ? null : Math.trunc(parsedExpected),
        cutoff_time_local: cutoffTime || null
      });
      setPlanSettingsDirty(false);
      await load();
    } catch (e: any) {
      setError(e?.message || 'Failed to save plan');
    } finally {
      setBusy(false);
    }
  }

  async function onAddItem() {
    if (!planId) return;
    const plate = addPlate.trim();
    if (!plate) return;
    try {
      setBusy(true);
      setError(null);
      await addAnprDailyPlanItem({
        plan_id: planId,
        plate_text: plate,
        expected_by_local: addExpectedBy || null,
        status: addStatus || null,
        notes: addNotes.trim() || null
      });
      setAddPlate('');
      setAddExpectedBy('');
      setAddStatus('PLANNED');
      setAddNotes('');
      await load();
    } catch (e: any) {
      setError(e?.message || 'Failed to add item');
    } finally {
      setBusy(false);
    }
  }

  async function onUpdateStatus(itemId: string, status: string) {
    try {
      setBusy(true);
      setError(null);
      await updateAnprDailyPlanItem(itemId, { status });
      await load();
    } catch (e: any) {
      setError(e?.message || 'Failed to update item');
    } finally {
      setBusy(false);
    }
  }

  async function onUpdateExpectedBy(itemId: string, expectedBy: string) {
    try {
      setBusy(true);
      setError(null);
      await updateAnprDailyPlanItem(itemId, { expected_by_local: expectedBy || null });
      await load();
    } catch (e: any) {
      setError(e?.message || 'Failed to update item');
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(itemId: string) {
    try {
      setBusy(true);
      setError(null);
      await deleteAnprDailyPlanItem(itemId);
      await load();
    } catch (e: any) {
      setError(e?.message || 'Failed to delete item');
    } finally {
      setBusy(false);
    }
  }

  async function onImportFileChange(file: File | null) {
    setImportResult(null);
    setImportError(null);
    setImportRows([]);
    setImportFile(file);
    if (!file) return;
    try {
      const text = await file.text();
      setImportRows(parseCsv(text));
    } catch (e: any) {
      setImportError(e?.message || 'Failed to read CSV file');
    }
  }

  async function onImportCsv() {
    if (!importFile || !godownId || !dateLocal) return;
    try {
      setImportBusy(true);
      setImportError(null);
      const resp = await importAnprDailyPlanItemsCsv({
        godown_id: godownId,
        plan_date: dateLocal,
        timezone_name: timezoneName,
        file: importFile
      });
      setImportResult(resp);
      await load();
      setImportOpen(false);
      setTimeout(() => {
        plannedRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 50);
    } catch (e: any) {
      setImportError(e?.message || 'Failed to import CSV');
    } finally {
      setImportBusy(false);
    }
  }

  return (
    <>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <div className="hud-pill">Daily plan</div>
            <div className="text-4xl font-semibold font-display tracking-tight text-slate-100 drop-shadow">
              ANPR Daily Plan
            </div>
            <div className="text-sm text-slate-300">Plan expected arrivals and track live status updates.</div>
          </div>
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 w-full lg:w-auto">
            <div className="hud-card w-full p-4 sm:min-w-[240px]">
              <div className="hud-label">Summary</div>
              <div className="hud-value">{summary.ARRIVED} / {summary.PLANNED}</div>
              <div className="text-xs text-slate-500">Date: {dateLocal || 'N/A'}</div>
            </div>
            <Button
              className="w-full sm:w-auto rounded-full px-4 py-2 text-xs uppercase tracking-[0.2em] bg-blue-600 hover:bg-blue-700 text-white"
              onClick={() => setImportOpen(true)}
            >
              Bulk Import
            </Button>
          </div>
        </div>

        {error && <ErrorBanner message={error} />}

        {importOpen && (
          <Card className="hud-card">
            <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-xl font-semibold font-display text-white">Import Plan Items (CSV)</div>
                <div className="text-xs text-slate-400">Bulk load planned vehicles for a date.</div>
              </div>
              <Button variant="outline" className="w-full md:w-auto" onClick={() => setImportOpen(false)}>
                Close
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {importError && <ErrorBanner message={importError} />}

              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div>
                  <Label>CSV File</Label>
                  <Input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(e) => onImportFileChange(e.target.files?.[0] || null)}
                  />
                </div>
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
                  <Label>Date</Label>
                  <Input type="date" value={dateLocal} onChange={(e) => setDateLocal(e.target.value)} />
                </div>
                <div className="self-start md:self-end">
                  <Button className="w-full md:w-auto" onClick={onImportCsv} disabled={importBusy || !importFile || !godownId || !dateLocal}>
                    {importBusy ? 'Importing...' : 'Import CSV'}
                  </Button>
                </div>
              </div>

              {importRows.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs text-slate-300">
                    Preview rows: {importRows.length} (errors: {importRows.filter((r) => r.error).length})
                  </div>
                  <div className="table-shell overflow-auto">
                    <Table>
                      <THead>
                        <TR>
                          <TH>Plate</TH>
                          <TH>Expected By</TH>
                          <TH>Status</TH>
                          <TH>Notes</TH>
                          <TH>Issue</TH>
                        </TR>
                      </THead>
                      <TBody>
                        {importRows.map((r, idx) => (
                          <TR key={`${r.plate_text}-${idx}`}>
                            <TD className="font-semibold">{r.plate_text || 'N/A'}</TD>
                            <TD>{r.expected_by_local || 'N/A'}</TD>
                            <TD>{r.status || 'N/A'}</TD>
                            <TD className="max-w-[360px] truncate">{r.notes || 'N/A'}</TD>
                            <TD className="text-xs text-amber-300">{r.error || 'N/A'}</TD>
                          </TR>
                        ))}
                      </TBody>
                    </Table>
                  </div>
                </div>
              )}

              {importResult && (
                <div className="text-xs text-slate-300">
                  Imported: {importResult.total} | Created: {importResult.created} | Updated: {importResult.updated} | Failed: {importResult.failed}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <Card className="hud-card" ref={plannedRef}>
          <CardHeader>
            <div className="text-lg font-semibold font-display">Plan Settings</div>
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
              <Input
                value={timezoneName}
                onChange={(e) => {
                  setTimezoneName(e.target.value);
                  setPlanSettingsDirty(true);
                }}
              />
            </div>
            <div>
              <Label>Date</Label>
              <Input type="date" value={dateLocal} onChange={(e) => setDateLocal(e.target.value)} />
            </div>
            <div>
              <Label>Expected Count</Label>
              <Input
                type="number"
                value={expectedCount}
                onChange={(e) => {
                  setExpectedCount(e.target.value);
                  setPlanSettingsDirty(true);
                }}
              />
            </div>
            <div>
              <Label>Cutoff Time</Label>
              <Input
                type="time"
                value={cutoffTime}
                onChange={(e) => {
                  setCutoffTime(e.target.value);
                  setPlanSettingsDirty(true);
                }}
              />
            </div>
            <div className="md:col-span-5 flex flex-wrap gap-2 items-center">
              <Button onClick={onSavePlan} disabled={busy || !godownId || !dateLocal}>
                Save Plan
              </Button>
              <div className="text-xs text-slate-300">
                Planned: {summary.PLANNED} | Arrived: {summary.ARRIVED} | Delayed: {summary.DELAYED} | No show: {summary.NO_SHOW} | Cancelled: {summary.CANCELLED}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="hud-card">
          <CardHeader>
            <div className="text-lg font-semibold font-display">Add Planned Vehicle</div>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <Label>Plate</Label>
              <Input value={addPlate} onChange={(e) => setAddPlate(e.target.value)} placeholder="e.g. WB23D5690" />
            </div>
            <div>
              <Label>Expected By</Label>
              <Input type="time" value={addExpectedBy} onChange={(e) => setAddExpectedBy(e.target.value)} />
            </div>
            <div>
              <Label>Status</Label>
              <Select value={addStatus} onChange={(e) => setAddStatus(e.target.value)} options={statusOptions} />
            </div>
            <div>
              <Label>Notes</Label>
              <Input value={addNotes} onChange={(e) => setAddNotes(e.target.value)} placeholder="optional" />
            </div>
            <div className="md:col-span-4">
              <Button onClick={onAddItem} disabled={busy || !planId || !addPlate.trim()}>
                Add to Plan
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="hud-card">
          <CardHeader className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div className="text-lg font-semibold font-display">Planned Vehicles</div>
            <div className="hud-pill">Live status</div>
          </CardHeader>
          <CardContent>
            <div className="table-shell overflow-auto">
              <Table className="text-slate-100">
                <THead className="bg-slate-900/80 text-slate-200">
                  <TR>
                    <TH>Plate</TH>
                    <TH>Expected By</TH>
                    <TH>Manual Status</TH>
                    <TH>Effective</TH>
                    <TH>Arrived At (IST)</TH>
                    <TH>Actions</TH>
                  </TR>
                </THead>
                <TBody>
                  {items.length === 0 ? (
                    <TR className="border-white/10 hover:bg-white/0">
                      <TD colSpan={6} className="text-sm text-slate-500">
                        No plan items
                      </TD>
                    </TR>
                  ) : (
                    items.map((it) => (
                      <TR key={it.id} className="border-white/10 hover:bg-white/5">
                        <TD className="font-semibold">{it.plate_raw}</TD>
                        <TD>
                          <Input
                            type="time"
                            value={hhmm(it.expected_by_local)}
                            onChange={(e) => onUpdateExpectedBy(it.id, e.target.value)}
                            disabled={busy}
                          />
                        </TD>
                        <TD>
                          <Select
                            value={(it.status || 'PLANNED').toUpperCase()}
                            onChange={(e) => onUpdateStatus(it.id, e.target.value)}
                            options={statusOptions}
                          />
                        </TD>
                        <TD>{statusBadge(it.effective_status || 'PLANNED')}</TD>
                        <TD className="text-xs">
                          {it.arrived_at_utc ? formatIstDateTime(it.arrived_at_utc) : 'N/A'}
                        </TD>
                        <TD>
                          <Button
                            variant="danger"
                            className="px-3 py-1.5 text-xs"
                            onClick={() => setDeleteTargetId(it.id)}
                            disabled={busy}
                          >
                            Delete
                          </Button>
                        </TD>
                      </TR>
                    ))
                  )}
                </TBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>

      {deleteTargetId && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <button
            className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm"
            onClick={() => setDeleteTargetId(null)}
            aria-label="Close delete confirm"
          />
          <div
            className="modal-shell modal-body relative w-full rounded-2xl border border-white/10 bg-slate-950/95 p-6 shadow-2xl"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-lg font-semibold font-display text-white">Delete Plan Item</div>
            <div className="mt-2 text-sm text-slate-300">Are you sure you want to delete this plan item?</div>
            <div className="mt-5 flex items-center justify-end gap-2">
              <Button variant="outline" onClick={() => setDeleteTargetId(null)} disabled={busy}>
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  const id = deleteTargetId;
                  setDeleteTargetId(null);
                  if (id) onDelete(id);
                }}
                disabled={busy}
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
